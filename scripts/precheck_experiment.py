"""发布前的实验凭据检查（教训 L01 的执行位置）。

为什么要单独一个脚本：教训写在文档里不会拦人，写在测试里也不一定被跑到——
这个脚本进 `preflight`，每次发布前都会执行。

用法：
    python scripts/precheck_experiment.py                    # 自检：教训库是否完整
    python scripts/precheck_experiment.py --repeats 10 --ci 0.2 0.9 --metric ate
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab.lessons import LESSONS, ExperimentReport, check_experiment  # noqa: E402


def missing_enforcements() -> list[str]:
    """每条教训都必须指向一个真实存在的执行位置。"""
    problems: list[str] = []
    for lesson in LESSONS:
        kind, _, target = lesson.enforcement.partition(":")
        if kind == "test":
            tests = (ROOT / "tests" / "test_lab.py").read_text(encoding="utf-8")
            if f"def {target}(" not in tests:
                problems.append(f"{lesson.lesson_id} 指向的测试不存在：{target}")
        elif kind in {"script", "doc"}:
            path = ROOT / target
            if not path.exists():
                problems.append(f"{lesson.lesson_id} 指向的{kind}不存在：{target}")
        else:
            problems.append(f"{lesson.lesson_id} 执行位置类型未知：{lesson.enforcement}")
    return problems


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="实验凭据检查")
    parser.add_argument("--repeats", type=int, default=None)
    parser.add_argument("--ci", type=float, nargs=2, default=None, metavar=("LOW", "HIGH"))
    parser.add_argument("--metric", default="mean_return")
    parser.add_argument("--reward-changed", action="store_true")
    parser.add_argument("--same-reward-baseline", action="store_true")
    parser.add_argument("--idle-control", action="store_true")
    parser.add_argument("--facts", nargs="*", default=None, metavar="FID", help="引用的已核实事实编号")
    args = parser.parse_args(argv)

    problems = missing_enforcements()
    if problems:
        print(f"教训库自检失败：{len(problems)} 条没有执行位置")
        for item in problems:
            print(f"  - {item}")
        return 1

    if args.repeats is None:
        print(f"教训库自检通过：{len(LESSONS)} 条教训全部有执行位置")
        return 0

    report = ExperimentReport(
        name="precheck",
        repeats=args.repeats,
        diff_ci=(args.ci[0], args.ci[1]) if args.ci else None,
        primary_metric=args.metric,
        same_reward_baseline=args.same_reward_baseline,
        reward_changed=args.reward_changed,
        idle_control=args.idle_control,
        cited_facts=list(args.facts or []),
    )
    violations = check_experiment(report)
    if violations:
        print(f"这份结果违背 {len(violations)} 条教训：")
        for item in violations:
            print(f"  - {item}")
        return 1
    print("凭据齐全：可以下结论")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
