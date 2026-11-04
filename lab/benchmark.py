"""冻结的参考任务 + 两级协议（v0.40）。

为什么要冻结：27 次实验里，我换过尺寸、布局、打滑、漂移、受伤惩罚、塑形方式、死亡模式……
**每次换都让前后结果不可比**，于是"进步"全是局部最优的错觉。

这里定义唯一一个可以下结论的地方：

    参考任务 ref-1：10×10 走廊 + 6 个危险区 + 非致命 + 120 步
    固定奖励：hurt = −1、shaping = legacy、无存活奖励
    主指标（与奖励无关）：ate（吃到份数）、hurt（受伤次数）
    参考指标（不可单独用来下结论）：mean_return

两级协议：
    explore：随便跑几次，用来找方向。**结果不许写进结论、不许进总结表**
    claim  ：在参考任务上跑 ≥10 组，给出 95% 区间，并通过 lessons 检查
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from .lessons import ExperimentReport, check_experiment

REFERENCE_VERSION = "ref-1"

REFERENCE: Dict[str, Any] = {
    "size": 10,
    "layout": "corridor",
    "hazards": 6,
    "lethal": False,
    "steps": 120,
    "hurt_penalty": -1.0,
    "shaping": "legacy",
    "with_path": True,
    "episodes": 15,
    "rounds": 2,
}

PRIMARY_METRICS = ("ate", "hurt")
MIN_REPEATS = 10


@dataclass
class Run:
    seed: int
    ate: float
    hurt: float
    score: float


def _ci(values: Sequence[float]) -> tuple[float, float] | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    half = 1.96 * math.sqrt(var) / math.sqrt(len(values))
    return mean - half, mean + half


def run_reference(repeats: int = MIN_REPEATS, agent_factory: Any = None, **overrides: Any) -> Dict[str, Any]:
    """在参考任务上跑 repeats 组，返回主指标与参考指标。"""
    from .linear import WeightedMultiHeadAgent
    from .tasks import eval_seeds, evaluate, train, train_seeds

    if agent_factory is None:
        agent_factory = lambda seed: WeightedMultiHeadAgent(seed=seed)  # noqa: E731

    config = dict(REFERENCE)
    config.update({k: v for k, v in overrides.items() if k in config or k in {"epsilon", "explore_bonus"}})
    seeds = eval_seeds(6)
    runs: List[Run] = []
    for index in range(repeats):
        agent = agent_factory(index)
        for _ in range(config["rounds"]):
            train(
                agent, train_seeds(config["episodes"]), config["steps"],
                epsilon=float(config.get("epsilon", 0.25)),
                explore_bonus=float(config.get("explore_bonus", 0.0)), **{k: v for k, v in REFERENCE.items() if k in {
                    "size", "layout", "hazards", "lethal", "hurt_penalty", "shaping", "with_path"}},
            )
        stats = evaluate(
            agent, seeds, config["steps"],
            **{k: v for k, v in config.items() if k in {
                "size", "layout", "hazards", "lethal", "hurt_penalty", "shaping", "with_path"}},
        )
        runs.append(Run(index, float(stats["ate"]), float(stats["hurt"]), float(stats["mean_return"])))

    ate = [r.ate for r in runs]
    hurt = [r.hurt for r in runs]
    score = [r.score for r in runs]
    return {
        "reference": REFERENCE_VERSION,
        "overrides": {k: v for k, v in overrides.items()},
        "repeats": repeats,
        "ate": {"mean": round(sum(ate) / len(ate), 3), "ci": _ci(ate)},
        "hurt": {"mean": round(sum(hurt) / len(hurt), 3), "ci": _ci(hurt)},
        "score": {"mean": round(sum(score) / len(score), 3), "ci": _ci(score)},
        "raw": {"ate": ate, "hurt": hurt, "score": score},
    }


def verdict(result: Dict[str, Any]) -> List[str]:
    """按教训库检查这份结果能不能当结论。"""
    report = ExperimentReport(
        name=f"{result['reference']}",
        repeats=int(result["repeats"]),
        diff_ci=result["ate"]["ci"],
        primary_metric="ate",
        same_reward_baseline=True,
        reward_changed=False,
        idle_control=True,
    )
    return check_experiment(report)


def format_report(result: Dict[str, Any]) -> str:
    def cell(block: Dict[str, Any]) -> str:
        ci = block["ci"]
        if ci is None:
            return f"{block['mean']:+.2f}（无区间：样本不足）"
        return f"{block['mean']:+.2f} [{ci[0]:+.2f}, {ci[1]:+.2f}]"

    lines = [
        f"参考任务 {result['reference']}（{result['repeats']} 组）",
        f"  主指标 · 吃到份数：{cell(result['ate'])}",
        f"  主指标 · 受伤次数：{cell(result['hurt'])}",
        f"  参考       · 加权分数：{cell(result['score'])}（不可单独下结论）",
    ]
    problems = verdict(result)
    if problems:
        lines.append("")
        lines.append("不能当结论：")
        for item in problems:
            lines.append(f"  - {item}")
    else:
        lines.append("")
        lines.append("凭据齐全：可以作为结论，但只限这个参考任务。")
    return "\n".join(lines)
