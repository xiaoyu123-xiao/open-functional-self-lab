"""把仓库里的 your-org 占位符换成真实 GitHub 用户名/组织名。

用法：
    python scripts/set_owner.py --owner hexingyu
    python scripts/set_owner.py --owner my-org --name "何兴宇" --email "me@example.com"
    python scripts/set_owner.py --owner my-org --remote-url https://github.com/my-org/open-functional-self-lab.git

做三件事（都可单独关掉）：
    1. 替换文档与模板里的占位符（不含 docs/publish.md，那是通用 runbook）
    2. 可选：改写最近一次 commit 的作者（仓库还没 push 时才建议这么做）
    3. 可选：设置/更新 origin remote

幂等：已经替换过的文件不会二次改动。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 普通 URL 里的 <your-org>
URL_FILES = (
    "README.md",
    "CONTRIBUTING.md",
    "docs/tools.md",
    "CITATION.cff",
    ".github/ISSUE_TEMPLATE/config.yml",
)

# CODEOWNERS 里是 @your-org/maintainers 这种"团队"写法，要换成 @用户名
CODEOWNERS = ".github/CODEOWNERS"

PLACEHOLDER = re.compile(r"<?your-org>?")


def rewrite_text(text: str, owner: str) -> str:
    # 先处理团队写法：@your-org/maintainers -> @owner
    text = re.sub(r"@your-org/[A-Za-z0-9_.-]+", f"@{owner}", text)
    text = text.replace("<your-org>", owner).replace("your-org", owner)
    # 同一行里 "@owner @owner"（maintainers 与 founder 都指向个人时）去重
    text = re.sub(r"(@[A-Za-z0-9_.-]+)(?:\s+\1)+", r"\1", text)
    return text


def patch_files(owner: str) -> list[tuple[str, int]]:
    changed: list[tuple[str, int]] = []
    for name in URL_FILES + (CODEOWNERS,):
        path = ROOT / name
        if not path.exists():
            print(f"[SKIP] {name}（不存在）")
            continue
        before = path.read_text(encoding="utf-8")
        after = rewrite_text(before, owner)
        if after != before:
            path.write_text(after, encoding="utf-8")
            changed.append((name, sum(1 for a, b in zip(before.splitlines(), after.splitlines()) if a != b)))
    return changed


def git(*args: str) -> subprocess.CompletedProcess:
    # errors="replace"：Windows 上 git 的本地化输出不一定是 UTF-8，不能因为解码失败就崩
    return subprocess.run(
        ["git", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="替换占位符 / 设置作者 / 配置 remote")
    parser.add_argument("--owner", required=True, help="GitHub 用户名或组织名")
    parser.add_argument("--name", default=None, help="commit 作者名（可选）")
    parser.add_argument("--email", default=None, help="commit 作者邮箱（可选）")
    parser.add_argument("--remote-url", default=None, help="origin 的 URL（可选）")
    parser.add_argument("--skip-files", action="store_true", help="不改文件")
    args = parser.parse_args(argv)

    owner = args.owner.strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", owner):
        print(f"用户名不合法：{owner!r}（GitHub 用户名只含字母数字与连字符，且不以连字符开头/结尾）")
        return 2

    if not args.skip_files:
        changed = patch_files(owner)
        if changed:
            for name, lines in changed:
                print(f"[OK] {name}：{lines} 行已替换")
        else:
            print("[OK] 无需替换（已经是目标值）")

    if args.name and args.email:
        # 先设 config，再 --reset-author：这样 author 和 committer 一起改成真人
        git("config", "user.name", args.name)
        git("config", "user.email", args.email)
        result = git("commit", "--amend", "--no-edit", "--reset-author")
        if result.returncode != 0:
            print(f"[FAIL] 改作者失败：{(result.stderr or result.stdout).strip()[:300]}")
            return 1
        shown = git("log", "-1", "--pretty=%an <%ae> / committer %cn <%ce>").stdout.strip()
        print(f"[OK] 最近一次 commit → {shown}")
        print("     注意：amend 会改 commit 哈希，需重新打 tag：")
        print('     git tag -d v0.1.0 && git tag -a v0.1.0 -m "v0.1.0 控制面 MVP"')

    if args.remote_url:
        existing = git("remote").stdout.strip().splitlines()
        action = "set-url" if "origin" in existing else "add"
        result = git("remote", action, "origin", args.remote_url)
        if result.returncode != 0:
            print(f"[FAIL] 设置 remote 失败：{(result.stderr or result.stdout).strip()[:300]}")
            return 1
        print(f"[OK] remote origin → {args.remote_url}")

    print()
    print("下一步：")
    print("  git status --short          # 看改了哪些文件")
    print("  git add -A && git commit -m \"chore: 替换占位符为真实仓库地址\"")
    print("  git push -u origin main && git push origin v0.1.0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
