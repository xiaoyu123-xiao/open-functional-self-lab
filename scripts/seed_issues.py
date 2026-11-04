"""把 issues/issues.json 建成 GitHub Issue。

用法：
    python scripts/seed_issues.py --dry-run   # 生成 body 文件并打印命令，不联网
    python scripts/seed_issues.py             # 需要已 gh auth login

为什么用 --body-file 而不是 --body：Windows 单条命令上限 8191 字符，
带换行的长正文会被截断；写文件再引用可以避开这个坑。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "issues" / "issues.json"
BODY_DIR = ROOT / "state" / "issue-bodies"


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def build_body(issue: dict) -> str:
    return "\n".join(
        [
            f"**任务编号**：{issue['id']}　**状态**：{issue['status']}",
            "",
            "## 目标",
            issue["goal"],
            "",
            "## 验收标准",
            issue["acceptance"],
            "",
            "## 安全约束",
            issue["safety"],
            "",
            "## 资源预算",
            issue["budget"],
            "",
            "## 复现方式",
            "```bash",
            issue["reproduce"],
            "```",
            "",
            "---",
            "_本 Issue 由 `scripts/seed_issues.py` 从 issues/issues.json 生成；"
            "认领前请读 SECURITY.md 与 ETHICS.md。_",
            "",
        ]
    )


def write_body(issue: dict) -> Path:
    BODY_DIR.mkdir(parents=True, exist_ok=True)
    target = BODY_DIR / f"{issue['id']}.md"
    target.write_text(build_body(issue), encoding="utf-8")
    return target


def command(issue: dict, body: Path) -> list[str]:
    return [
        "gh",
        "issue",
        "create",
        "--title",
        f"[{issue['id']}] {issue['title']}",
        "--body-file",
        body.relative_to(ROOT).as_posix(),
        "--label",
        ",".join(issue.get("labels", [])),
    ]


def shell_line(parts: list[str]) -> str:
    def quote(token: str) -> str:
        if any(ch in token for ch in " \"'()[]{}:，"):
            return '"' + token.replace('"', '\\"') + '"'
        return token

    return " ".join(quote(part) for part in parts)


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="创建任务 Issue")
    parser.add_argument("--dry-run", action="store_true", help="只生成正文与命令，不联网")
    parser.add_argument("--only", default=None, help="只处理某一个编号，如 0001")
    args = parser.parse_args(argv)

    if not DATA.exists():
        print(f"找不到 {DATA}")
        return 1

    data = load()
    issues = data["issues"]
    if args.only:
        issues = [issue for issue in issues if issue["id"] == args.only]
        if not issues:
            print(f"没有编号 {args.only}")
            return 1

    gh = shutil.which("gh")
    lines: list[str] = []
    for issue in issues:
        body = write_body(issue)
        cmd = command(issue, body)
        if args.dry_run or not gh:
            lines.append(shell_line(cmd))
            continue
        result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            print(f"[FAIL] {issue['id']} {(result.stderr or result.stdout).strip()[:300]}")
        else:
            print(f"[OK] {issue['id']} {result.stdout.strip()}")

    if lines:
        script = BODY_DIR.parent / "seed_issues.sh"
        script.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"正文已写入 {BODY_DIR.relative_to(ROOT).as_posix()}/（{len(issues)} 个 .md）")
        print(f"命令已写入 {script.relative_to(ROOT).as_posix()}（bash 可直接执行）")
        print()
        for line in lines[:2]:
            print(line)
        if len(lines) > 2:
            print(f"...（共 {len(lines)} 条）")
        if not gh:
            print()
            print("未找到 gh CLI：命令已存盘，装上 gh 并 gh auth login 后执行该脚本即可。")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
