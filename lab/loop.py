"""自驱循环的一轮：评测 → 训练 → 再评测 → 变差就回滚（v0.4）。

这是"自我进化"最容易被造假的地方，所以规则写死：

1. 每一轮**先量再学**：训练前留出分数（`before`）是唯一参照。
2. 学完再量（`after`），**只有 `after > before` 才保存策略**，否则回滚到旧参数。
3. 每轮都写账本 `cycle` 事件；分数、轮数、更新次数全部留痕。
4. 评测永远用 `eval_seeds`，训练永远用 `train_seeds`，两段不重叠（`assert_disjoint` 守着）。

它不保证越练越强。它保证的是：**变强了有记录，变差了会回滚，且任何人能复算。**
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .agent import QLearningAgent
from .linear import LinearQAgent
from .ledger import Ledger
from .tasks import assert_disjoint, baseline_score, eval_seeds, evaluate, train, train_seeds


def cycle(
    *,
    policy_path: Path,
    ledger: Ledger,
    ts: str,
    rounds: int = 3,
    episodes_per_round: int = 30,
    steps: int = 60,
    eval_count: int = 20,
    epsilon: float = 0.25,
    hazards: int = 4,
    algo: str = "tabular",
) -> Dict[str, Any]:
    if rounds <= 0 or episodes_per_round <= 0 or steps <= 0 or eval_count <= 0:
        raise ValueError("rounds / episodes_per_round / steps / eval_count 都必须是正整数")

    assert_disjoint()
    make_agent = LinearQAgent if algo == "linear" else QLearningAgent
    agent = make_agent(policy_path).load()
    evaluation = eval_seeds(eval_count)

    before = evaluate(agent, evaluation, steps, hazards=hazards)
    train_stats: List[Dict[str, Any]] = []
    for _ in range(rounds):
        train_stats.append(train(agent, train_seeds(episodes_per_round), steps, epsilon=epsilon, hazards=hazards))
    after = evaluate(agent, evaluation, steps, hazards=hazards)
    baseline = baseline_score(evaluation, steps, hazards=hazards)

    improved = after["mean_return"] > before["mean_return"]
    if improved:
        agent.save()
    else:
        # 回滚：重新从磁盘读旧参数，丢掉本轮训练结果
        agent = make_agent(policy_path).load()

    delta = round(after["mean_return"] - before["mean_return"], 4)
    record = ledger.append(
        "cycle",
        {
            "before": before["mean_return"],
            "after": after["mean_return"],
            "baseline": baseline["mean_return"],
            "delta": delta,
            "improved": improved,
            "rounds": rounds,
            "episodes_per_round": episodes_per_round,
            "updates": train_stats[-1].get("episodes", 0) if train_stats else 0,
            "states": len(agent.table),
            "hazards": hazards,
        "algo": algo,
            "algo": algo,
        },
        ts,
    )
    return {
        "before": before,
        "after": after,
        "baseline": baseline,
        "delta": delta,
        "improved": improved,
        "states": len(agent.table),
        "record_seq": record["seq"],
        "hazards": hazards,
        "algo": algo,
    }


def format_cycle(result: Dict[str, Any]) -> str:
    verdict = "保留新策略" if result["improved"] else "回滚到旧策略（没变好）"
    gap = result["after"]["mean_return"] - result["baseline"]["mean_return"]
    lines = [
        f"训练前留出分数：{result['before']['mean_return']:+.3f}"
        f"（吃到 {result['before']['ate']}，受伤 {result['before']['hurt']}）",
        f"训练后留出分数：{result['after']['mean_return']:+.3f}"
        f"（吃到 {result['after']['ate']}，受伤 {result['after']['hurt']}）",
        f"变化 {result['delta']:+.3f} → {verdict}",
        f"BFS 基线 {result['baseline']['mean_return']:+.3f}，"
        f"当前策略与之差 {gap:+.3f}（负数表示还没追上）",
        f"难度（危险区数量）{result['hazards']}，Q 表状态数 {result['states']}，账本记录 #{result['record_seq']}",
    ]
    return "\n".join(lines)
