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
from .linear import LinearQAgent, MultiHeadLinearQAgent, WeightedMultiHeadAgent
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

# v0.21：更宽的任务族（第二个维度是地图尺寸），用于检验"举一反三"是否成立
WIDE_TRAIN_CONFIGS: Tuple[Dict[str, Any], ...] = (
    {"hazards": 4, "lethal": True, "size": 8},
    {"hazards": 6, "lethal": True, "size": 10},
    {"hazards": 4, "lethal": False, "size": 8},
)
WIDE_HELDOUT_CONFIGS: Tuple[Dict[str, Any], ...] = (
    {"hazards": 6, "lethal": True, "size": 12},
    {"hazards": 10, "lethal": True, "size": 10},
)

FAMILIES = {"core": (TRAIN_CONFIGS, HELDOUT_CONFIGS), "wide": (WIDE_TRAIN_CONFIGS, WIDE_HELDOUT_CONFIGS)}


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
    repeats: int = 1,
    family: str = "core",
) -> Dict[str, Any]:
    if family not in FAMILIES:
        raise ValueError(f"family 只能是 {sorted(FAMILIES)}")
    train_configs, heldout_configs = FAMILIES[family]
    seeds = eval_seeds(eval_count)
    if repeats <= 0:
        raise ValueError("repeats 必须是正整数")
    if algo == "linear":
        make_agent = lambda seed: LinearQAgent(seed=seed)
    elif algo == "multihead":
        make_agent = lambda seed: MultiHeadLinearQAgent(seed=seed)
    elif algo == "weighted":
        make_agent = lambda seed: WeightedMultiHeadAgent(seed=seed)
    else:
        make_agent = lambda seed: QLearningAgent(seed=seed)

    single_runs: List[Dict[str, Any]] = []
    multi_runs: List[Dict[str, Any]] = []
    ratios: List[float] = []
    for repeat in range(repeats):
        agent_seed = 11 + repeat
        single = make_agent(agent_seed)
        single_episodes = train_multi(single, [train_configs[0]], rounds, episodes, steps)
        single_rows = evaluate_configs(single, heldout_configs, seeds, steps)

        multi = make_agent(agent_seed)
        multi_episodes = train_multi(multi, train_configs, rounds, episodes, steps)
        multi_rows = evaluate_configs(multi, heldout_configs, seeds, steps)

        single_mean = sum(row["learned"] for row in single_rows) / len(single_rows)
        multi_mean = sum(row["learned"] for row in multi_rows) / len(multi_rows)
        single_runs.append({"seed": agent_seed, "episodes": single_episodes, "rows": single_rows, "mean": round(single_mean, 4)})
        multi_runs.append({"seed": agent_seed, "episodes": multi_episodes, "rows": multi_rows, "mean": round(multi_mean, 4)})
        if abs(single_mean) > 1e-9:
            ratios.append(multi_mean / single_mean)

    single_means = [run["mean"] for run in single_runs]
    multi_means = [run["mean"] for run in multi_runs]
    def _mean(values: List[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0
    def _std(values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        avg = sum(values) / len(values)
        return round((sum((v - avg) ** 2 for v in values) / (len(values) - 1)) ** 0.5, 4)

    diffs = [m - s for s, m in zip(single_means, multi_means)]
    wins = sum(1 for d in diffs if d > 0)
    ratio_mean = _mean(ratios)
    return {
        "algo": algo,
        "family": family,
        "repeats": repeats,
        "seeds": list(seeds),
        "steps": steps,
        "single": {"mean": _mean(single_means), "std": _std(single_means), "runs": single_runs},
        "multi": {"mean": _mean(multi_means), "std": _std(multi_means), "runs": multi_runs},
        "ratio": ratio_mean,
        "ratio_std": _std(ratios),
        "ratios": [round(r, 4) for r in ratios],
        "diff_mean": _mean(diffs),
        "diff_std": _std(diffs),
        "wins": wins,
        "win_rate": round(wins / len(diffs), 4) if diffs else 0.0,
        # 判据 v2（v0.16 修订）：比值受"分母接近 0"影响不稳定，改用配对比较
        "transfer_helped": bool(diffs and (wins / len(diffs) >= 0.8) and (_mean(multi_means) >= _mean(single_means))),
    }


def format_report(summary: Dict[str, Any]) -> str:
    lines = ["留出配置（训练时从未出现）："]
    for row in summary["multi"]["runs"][0]["rows"]:
        config = row["config"]
        lines.append(
            f"  hazards={config['hazards']} lethal={config['lethal']}："
            f"BFS {row['baseline']:+.3f}　多任务 {row['learned']:+.3f}"
        )
    lines.append("")
    lines.append(
        f"单任务策略：留出均分 {summary['single']['mean']:+.3f}"
        f"（{summary['repeats']} 次重复，波动 ±{summary['single']['std']:.3f}）"
    )
    lines.append(
        f"多任务策略：留出均分 {summary['multi']['mean']:+.3f}"
        f"（{summary['repeats']} 次重复，波动 ±{summary['multi']['std']:.3f}）"
    )
    if summary["ratio"] is None:
        lines.append("比值：无法比较（单任务均分接近 0）")
    else:
        verdict = "迁移有帮助" if summary["transfer_helped"] else "迁移没有带来好处"
        lines.append(
            f"配对差（多任务 − 单任务）：{summary['diff_mean']:+.3f} ± {summary['diff_std']:.3f}，"
            f"胜率 {summary['win_rate']*100:.0f}%（{summary['wins']}/{summary['repeats']}）"
        )
        lines.append(
            f"比值 {summary['ratio']:.2f} ± {summary['ratio_std']:.2f}（逐次 {summary['ratios']}）"
            " ← 仅作参考：分母接近 0 时会爆炸"
        )
        lines.append(f"结论：{verdict}（判据 v2：胜率 ≥80% 且均值不下降）")
    return "\n".join(lines)
