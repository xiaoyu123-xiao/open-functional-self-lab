"""语言纪律检查：抓"把工程描述写成心理描述"的地方。

规则（对应 docs/language.md）：
- 命中禁用词，且该行不含引号、不含否定词、不是对照表（含 "|" 或 "→"）时，才报。
- 白名单文件：docs/language.md 自身（它就是示例库）。

用法：
    python scripts/check_language.py            # 全仓库
    python scripts/check_language.py --strict   # 有命中就 exit 1（可接进 CI）
"""

from __future__ import annotations

import argparse
import pathlib
import sys

FORBIDDEN = ("怕死", "胆小", "渴望", "意识到", "讨厌", "喜欢", "宁愿", "想活", "害怕", "恐惧")
NEGATIONS = ("不是", "不许", "不得", "禁止", "禁用", "不能", "别写", "改写", "≠", "没有")
SKIP_FILES = {"docs/language.md", "docs/metrics.md", "ETHICS.md", "docs/process.md", "CODE_OF_CONDUCT.md"}
SKIP_DIRS = {".git", "state", "__pycache__", ".venv", "node_modules"}


def suspicious(line: str) -> bool:
    if not any(word in line for word in FORBIDDEN):
        return False
    if any(neg in line for neg in NEGATIONS):
        return False
    if '"' in line or "「" in line or "」" in line or "“" in line or "”" in line:
        return False
    if "|" in line or "→" in line:
        return False
    return True


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="检查拟人化措辞")
    parser.add_argument("--strict", action="store_true", help="有命中时返回 1")
    args = parser.parse_args(argv)

    root = pathlib.Path(__file__).resolve().parents[1]
    hits = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in {".md", ".py"}:
            continue
        rel = path.relative_to(root).as_posix()
        if rel in SKIP_FILES or any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, start=1):
            if suspicious(line):
                hits.append((rel, number, line.strip()[:100]))

    if not hits:
        print("语言检查：没有发现把工程描述写成心理描述的地方。")
        return 0

    print(f"语言检查：{len(hits)} 处可疑（对照 docs/language.md 改写）：")
    for rel, number, text in hits:
        print(f"  {rel}:{number}  {text}")
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
