"""预算闸门回归：确认超限时真的返回 3 并回滚，而不是"警告后继续跑"。

用法： python scripts/budget_regression.py
退出码：0 = 符合预期，1 = 回归失败（CI 会红）。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "lab.config.json").write_text(
            json.dumps({"version": 1, "budget": {"steps_per_run": 3}}, ensure_ascii=False),
            encoding="utf-8",
        )
        command = [sys.executable, "-m", "lab.cli", "--root", str(root), "run", "--steps", "9"]
        result = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8")
        print(result.stdout.strip())
        if result.returncode != 3:
            print(f"回归失败：期望退出码 3，实际 {result.returncode}")
            print(result.stderr.strip())
            return 1
        state = json.loads((root / "state" / "state.json").read_text(encoding="utf-8"))
        if state["status"] != "READY":
            print(f"回归失败：回滚后状态应为 READY，实际 {state['status']}")
            return 1
        if "ROLLING_BACK" not in [step["to"] for step in state["history"]]:
            print("回归失败：历史里没有 ROLLING_BACK")
            return 1
    print("预算闸门回归：通过（退出码 3 + 回滚到 READY）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
