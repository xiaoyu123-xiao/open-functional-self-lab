"""跨任务迁移实验（v0.12）。

问题：现在每一次"变强"都只在**一个任务配置**上成立（例如 hazards=4 且致命）。
换个配置，那些 Q 值就作废。这叫"记住了"，不叫"学会了"。

做法：
    训练配置 A：（hazards=4，致命）（hazards=6，致命）（hazards=4，非致命）
    留出配置 B：（hazards=8，致命）（hazards=10，致命）   ← 训练时从未出现

对比三种情况，只看留出配置 B 上的分数：
    1. BFS 手写规则
    2. 单任务策略（只在 hazards=4 致命上训练）
    3. 多任务策略（在 A 上轮流训练）

判定（写死，不许事后改）：多任务在留出配置上的分数 **≥ 单任务 × 1.05**，
才算"迁移带来了好处"。达不到就如实写"迁移失败"。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .agent import QLearningAgent
from .linear import LinearQAgent, MultiHeadLinearQAgent
from .tasks import baseline_score, eval_seeds, evaluate, train, train_seeds

TRAIN_CONFIGS: Tuple[Dict[str, Any], ...] = (
    {"hazards": 4, "lethal": True},
    {"hazards": 6, "lethal": True},
    {"hazards": 4, "lethal": False},
)
HELDOUT_CONFIGS: Tuple[Dict[str, Any], ...] = (
    {"hazards": 8, "lethal": True},
    {"hazards": 10, "lethal": True},
)


def train_multi(
    agent: QLearningAgent,
    configs: Sequence[Dict[str, Any]],
    rounds: int,
    episodes: int,
    steps: int,
    epsilon: float = 0.25,
) -> int:
    """在多个配置上轮流训练。返回训练总回合数。"""
    total = 0
    for _ in range(rounds):
        for config in configs:
            train(agent, train_seeds(episodes), steps, epsilon=epsilon, **config)
            total += episodes
    return total


def evaluate_configs(
    agent: QLearningAgent,
    configs: Iterable[Dict[str, Any]],
    seeds: Sequence[int],
    steps: int,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for config in configs:
        learned = evaluate(agent, seeds, steps, **config)
        baseline = baseline_score(seeds, steps, **config)
        rows.append(
            {
                "config": config,
                "learned": learned["mean_return"],
                "baseline": baseline["mean_return"],
                "ate": learned["ate"],
                "hurt": learned["hurt"],
            }
        )
    return rows


def run(
    *,
    rounds: int = 4,
    episodes: int = 50,
    steps: int = 60,
    eval_count: int = 20,
    algo: str = "tabular",
) -> Dict[str, Any]:
    seeds = eval_seeds(eval_count)
    if algo == "linear":
        make_agent = lambda: LinearQAgent(seed=11)
    elif algo == "multihead":
        make_agent = lambda: MultiHeadLinearQAgent(seed=11)
    else:
        make_agent = lambda: QLearningAgent(seed=11)

    single = make_agent()
    single_episodes = train_multi(single, [TRAIN_CONFIGS[0]], rounds, episodes, steps)
    single_rows = evaluate_configs(single, HELDOUT_CONFIGS, seeds, steps)

    multi = make_agent()
    multi_episodes = train_multi(multi, TRAIN_CONFIGS, rounds, episodes, steps)
    multi_rows = evaluate_configs(multi, HELDOUT_CONFIGS, seeds, steps)

    single_mean = sum(row["learned"] for row in single_rows) / len(single_rows)
    multi_mean = sum(row["learned"] for row in multi_rows) / len(multi_rows)
    ratio = (multi_mean / single_mean) if abs(single_mean) > 1e-9 else float("inf")

    return {
        "algo": algo,
        "seeds": list(seeds),
        "steps": steps,
        "single": {"episodes": single_episodes, "rows": single_rows, "mean": round(single_mean, 4)},
        "multi": {"episodes": multi_episodes, "rows": multi_rows, "mean": round(multi_mean, 4)},
        "ratio": round(ratio, 4) if abs(ratio) != float("inf") else None,
        "transfer_helped": bool(multi_mean >= single_mean * 1.05) if single_mean > 0 else False,
    }


def format_report(summary: Dict[str, Any]) -> str:
    lines = ["留出配置（训练时从未出现）："]
    for row in summary["multi"]["rows"]:
        config = row["config"]
        lines.append(
            f"  hazards={config['hazards']} lethal={config['lethal']}："
            f"BFS {row['baseline']:+.3f}　多任务 {row['learned']:+.3f}"
        )
    lines.append("")
    lines.append(f"单任务策略（只在 hazards=4 致命上训练，{summary['single']['episodes']} 回合）："
                 f"留出均分 {summary['single']['mean']:+.3f}")
    lines.append(f"多任务策略（三个配置轮流，{summary['multi']['episodes']} 回合）："
                 f"留出均分 {summary['multi']['mean']:+.3f}")
    if summary["ratio"] is None:
        lines.append("比值：单任务均分接近 0，无法比较（说明单任务在留出配置上全崩了）")
    else:
        verdict = "迁移有帮助" if summary["transfer_helped"] else "迁移没有带来好处"
        lines.append(f"比值 {summary['ratio']:.2f} → {verdict}（判据：≥ 1.05）")
    return "\n".join(lines)
