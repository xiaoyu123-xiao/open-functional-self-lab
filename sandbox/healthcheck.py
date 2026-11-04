"""环境自检（零依赖，CPU 机器也返回 0）。

跑法：
    python sandbox/healthcheck.py            # 缺可选组件只提示，不影响退出码
    python sandbox/healthcheck.py --strict   # 缺可选组件也判失败（CI 里别用）

设计取舍：原方案的 healthcheck 只要有一个包没装就 exit 1，导致"第一次 clone 就红"。
这里把「必需」和「可选」分开：必需项（Python 版本、仓库结构、控制面可导入、state 可写）
失败才返回 1。
"""

from __future__ import annotations

import argparse
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED = (
    "README.md",
    "LICENSE",
    "SECURITY.md",
    "AGENTS.md",
    "lab.config.json",
    "lab/cli.py",
    "tests/test_lab.py",
)

OPTIONAL = (
    ("gymnasium", "虚拟身体（Issue 0001 之后才需要）"),
    ("torch", "神经网络后端（可选，CPU 版也行）"),
    ("chromadb", "向量记忆（Issue 0004）"),
    ("sentence_transformers", "向量化（Issue 0004）"),
)


def check_required() -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []

    version_ok = sys.version_info >= (3, 10)
    results.append(("Python ≥ 3.10", version_ok, f"{platform.python_version()} ({platform.platform()})"))

    missing = [name for name in REQUIRED if not (ROOT / name).exists()]
    results.append(("仓库必需文件", not missing, "齐全" if not missing else "缺少：" + ", ".join(missing)))

    try:
        from lab import __version__  # noqa: F401

        results.append(("控制面可导入", True, f"lab {__version__}"))
    except Exception as error:  # pragma: no cover - 只有仓库坏了才走到这
        results.append(("控制面可导入", False, f"{type(error).__name__}: {error}"))

    try:
        state = ROOT / "state"
        state.mkdir(parents=True, exist_ok=True)
        probe = state / ".healthcheck"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        results.append(("state/ 可写", True, str(state)))
    except OSError as error:
        results.append(("state/ 可写", False, str(error)))

    git = shutil.which("git")
    results.append(("git（发布流程用）", bool(git), git or "未找到，仅影响发布"))

    return results


def check_optional() -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    for module, purpose in OPTIONAL:
        try:
            __import__(module)
        except Exception:
            results.append((module, False, f"未安装（可选）：{purpose}"))
        else:
            results.append((module, True, "已安装"))
    return results


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Open Functional Self Lab 环境自检")
    parser.add_argument("--strict", action="store_true", help="可选组件缺失也判失败")
    args = parser.parse_args(argv)

    required = check_required()
    optional = check_optional()

    print("== 必需 ==")
    for name, ok, detail in required:
        print(f"[{'OK  ' if ok else 'FAIL'}] {name:<18} {detail}")
    print("== 可选 ==")
    for name, ok, detail in optional:
        print(f"[{'OK  ' if ok else 'SKIP'}] {name:<18} {detail}")

    failed_required = [name for name, ok, _ in required if not ok]
    failed_optional = [name for name, ok, _ in optional if not ok]

    print()
    if failed_required:
        print(f"结果：必需项失败 → {', '.join(failed_required)}")
        return 1
    if args.strict and failed_optional:
        print(f"结果：--strict 下可选缺失 → {', '.join(failed_optional)}")
        return 1
    print("结果：必需项全部通过（可选组件缺失属正常，v0.1 不需要它们）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
