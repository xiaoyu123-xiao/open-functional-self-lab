"""一条命令跑完全部自检，替代在四个文件里各贴一遍的"四条命令"。

    python scripts/preflight.py            # 发布前跑这个
    python scripts/preflight.py --quick    # 跳过端到端 run（只跑 doctor/tests/lint）

退出码：0 = 全绿；1 = 有失败项（会明确指出是哪一步）。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(name: str, args: list[str]) -> tuple[str, bool, str]:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (result.stdout or "").strip()
    stderr_lines = [line for line in (result.stderr or "").strip().splitlines() if line.strip()]
    # unittest -q 把结论写到 stderr：优先取 OK / FAILED 那一行
    markers = [line for line in stderr_lines if line.startswith(("OK", "FAILED"))]
    if markers:
        tail = markers[-1][:120]
    elif output:
        tail = output.splitlines()[-1][:120]
    else:
        tail = stderr_lines[-1][:120] if stderr_lines else "(无输出)"
    return name, result.returncode == 0, tail


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="发布前自检")
    parser.add_argument("--quick", action="store_true", help="跳过 end-to-end run")
    args = parser.parse_args(argv)

    steps: list[tuple[str, list[str]]] = [
        ("环境与仓库自检", ["-m", "lab.cli", "doctor"]),
        ("单元测试", ["-m", "unittest", "discover", "-s", "tests", "-q"]),
        ("红线扫描", ["-m", "lab.cli", "lint"]),
    ]
    if not args.quick:
        steps += [
            ("预算闸门回归", ["scripts/budget_regression.py"]),
            ("账本/状态机校验", ["-m", "lab.cli", "verify"]),
        ]

    failures = 0
    for name, command in steps:
        _, ok, detail = run(name, command)
        print(f"[{'OK  ' if ok else 'FAIL'}] {name:<12} {detail}")
        if not ok:
            failures += 1

    print()
    if failures:
        print(f"结果：{failures} 项失败。先修好再发布，不要用 --no-verify 之类的办法跳过。")
        return 1
    print("结果：全部通过，可以去 docs/publish.md 的第 2 步了。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
