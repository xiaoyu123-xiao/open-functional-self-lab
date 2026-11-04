"""检查源码是否兼容 Python 3.10（CI 的 py3.10 / py3.11 会跑）。

为什么需要它：3.12 起允许 f-string 里复用同种引号（PEP 701），
但 3.10/3.11 会直接 SyntaxError——本地用 3.13 跑测试完全发现不了。
这个脚本用正则近似地抓这类写法，并作为发布前检查的一部分。

用法：
    python scripts/check_py310.py            # 只报告
    python scripts/check_py310.py --strict   # 有命中返回 1（接进 preflight）
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

SKIP_DIRS = {".git", "state", "__pycache__", ".venv", "node_modules", "deploy"}

# f"..." 内部出现 [" 或 f'...' 内部出现 [' —— 3.12 之前都是语法错误
DOUBLE_PATTERN = re.compile(r'f"[^"]*\{[^}]*\["')
SINGLE_PATTERN = re.compile(r"f'[^']*\{[^}]*\['")


def scan(root: pathlib.Path) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, start=1):
            if DOUBLE_PATTERN.search(line) or SINGLE_PATTERN.search(line):
                hits.append((path.relative_to(root).as_posix(), number, line.strip()[:110]))
    return hits


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="检查 Python 3.10 语法兼容性")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    hits = scan(pathlib.Path(__file__).resolve().parents[1])
    if not hits:
        print("3.10 兼容性检查：通过（没有 f-string 同引号嵌套）")
        return 0
    print(f"3.10 兼容性检查：{len(hits)} 处风险（3.10/3.11 会 SyntaxError）")
    for rel, number, text in hits:
        print(f"  {rel}:{number}  {text}")
    print("改法：f-string 内部改用另一种引号，或先取到变量再格式化。")
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
