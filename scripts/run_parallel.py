"""多进程并行跑循环（给高配机器用）。

每个进程用自己的 `--root` 目录，互不干扰（账本是只追加的，共用一个目录会互相覆盖）。

用法：
    python scripts/run_parallel.py --jobs 8 --cycles 20 --lethal
    python scripts/run_parallel.py --jobs 16 --cycles 50 --lethal --algo weighted

输出：每个 job 一行摘要 + 最后汇总均值/最好/最差。
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_one(index: int, base: Path, args: argparse.Namespace) -> dict:
    job_root = base / f"job-{index}"
    job_root.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "lab.cli",
        "--root", str(job_root),
        "auto",
        "--cycles", str(args.cycles),
        "--rounds", str(args.rounds),
        "--episodes", str(args.episodes),
        "--steps", str(args.steps),
        "--eval-count", str(args.eval_count),
        "--hazards", str(args.hazards),
    ]
    if args.lethal:
        command.append("--lethal")
    if args.armor:
        command.append("--armor")
    # 初始化（auto 需要 state 存在与否都能跑，但显式 init 更清楚）
    subprocess.run([sys.executable, "-m", "lab.cli", "--root", str(job_root), "init"],
                   cwd=str(ROOT), capture_output=True, text=True)
    result = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8")

    scores = []
    ledger = job_root / "state" / "ledger.jsonl"
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("event") == "cycle":
                scores.append(float(record["payload"].get("after", 0.0)))
    return {
        "job": index,
        "returncode": result.returncode,
        "cycles": len(scores),
        "last": scores[-1] if scores else None,
        "best": max(scores) if scores else None,
        "root": str(job_root),
        "tail": (result.stdout or "").strip().splitlines()[-1:] or [""],
    }


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="并行跑自驱循环")
    parser.add_argument("--jobs", type=int, default=4, help="并行进程数（建议 = CPU 核数）")
    parser.add_argument("--cycles", type=int, default=10)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--episodes", type=int, default=40)
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--eval-count", type=int, default=20)
    parser.add_argument("--hazards", type=int, default=4)
    parser.add_argument("--lethal", action="store_true")
    parser.add_argument("--armor", action="store_true")
    parser.add_argument("--workdir", default=None, help="并行任务的根目录（默认用临时目录）")
    args = parser.parse_args(argv)

    if args.jobs <= 0:
        print("--jobs 必须是正整数")
        return 2

    base = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="ofsl-parallel-"))
    base.mkdir(parents=True, exist_ok=True)
    print(f"并行 {args.jobs} 个进程，工作目录 {base}")

    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_one, index, base, args) for index in range(args.jobs)]
        results = [future.result() for future in futures]

    for item in results:
        print(f"  job-{item['job']}: cycles={item['cycles']} last={item['last']} best={item['best']} "
              f"exit={item['returncode']}")

    finals = [item["last"] for item in results if item["last"] is not None]
    if finals:
        print()
        print(f"汇总：均值 {statistics.mean(finals):+.3f}，"
              f"最好 {max(finals):+.3f}，最差 {min(finals):+.3f}")
    failed = [item["job"] for item in results if item["returncode"] != 0]
    if failed:
        print(f"有 {len(failed)} 个进程失败：{failed}（看各自目录下的输出）")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
