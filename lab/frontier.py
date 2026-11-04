"""预算前沿（v0.47）：把"谁更强"换成"在哪个预算下更强"。

背景（事实 F14）：ref-1 上最优策略随受伤预算变化——
预算宽松时 BFS 吃满，零损伤时只有安全规划能站住。

用法：
    lab frontier --budgets 0,5,10,15
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Sequence, Tuple

CODE = {"n1": "up", "n2": "down", "n3": "left", "n4": "right", "n0": "rest"}


class PlannerPolicy:
    """按状态的下一跳方向行动（不学习）。"""

    def act(self, observation: Any, epsilon: float = 0.0) -> str:
        return "rest"

    def best_action(self, state: str) -> str:
        for token in state.split("|"):
            if token.startswith("n") and token[1:].isdigit():
                return CODE.get(token, "rest")
        return "rest"

    def update(self, *args: Any, **kwargs: Any) -> None:
        pass


@dataclass(frozen=True)
class Candidate:
    name: str
    kind: str          # "planner" 或 "learner"
    shield: bool


CANDIDATES: Sequence[Candidate] = (
    Candidate("BFS/规划器", "planner", False),
    Candidate("规划器+护栏", "planner", True),
    Candidate("学习器", "learner", False),
    Candidate("学习器+护栏", "learner", True),
)


def _measure(candidate: Candidate, seeds: Sequence[int], repeats: int, base: Dict[str, Any]) -> Tuple[float, float]:
    """返回 (吃到均值, 受伤均值)。学习器取 repeats 组平均，规划器是确定性的。"""
    from .linear import WeightedMultiHeadAgent
    from .tasks import evaluate, run_episode, train, train_seeds

    if candidate.kind == "planner":
        episode_kwargs = {k: v for k, v in base.items() if k != "steps"}
        rows = [
            run_episode(PlannerPolicy(), seed, base["steps"], train=False,
                        shield=candidate.shield, **episode_kwargs)
            for seed in seeds
        ]
        return sum(r["ate"] for r in rows) / len(seeds), sum(r["hurt"] for r in rows) / len(seeds)

    ates: List[float] = []
    hurts: List[float] = []
    for index in range(repeats):
        agent = WeightedMultiHeadAgent(seed=index)
        episode_kwargs = {k: v for k, v in base.items() if k != "steps"}
        for _ in range(2):
            train(agent, train_seeds(15), base["steps"], epsilon=0.25, **episode_kwargs)
        stats = evaluate(agent, seeds, base["steps"], shield=candidate.shield, **episode_kwargs)
        ates.append(stats["ate"] / len(seeds))
        hurts.append(stats["hurt"] / len(seeds))
    return sum(ates) / len(ates), sum(hurts) / len(hurts)


def run(budgets: Sequence[float], repeats: int = 6, base: Dict[str, Any] | None = None) -> Dict[str, Any]:
    from .tasks import eval_seeds

    base = dict(base or {})
    base.update({"steps": base.get("steps", 120), "size": 10, "layout": "corridor",
                 "hazards": 6, "lethal": False, "hurt_penalty": -1.0,
                 "shaping": "legacy", "with_path": True})
    seeds = eval_seeds(6)

    points: List[Dict[str, Any]] = []
    for candidate in CANDIDATES:
        ate, hurt = _measure(candidate, seeds, repeats, base)
        points.append({"name": candidate.name, "ate": round(ate, 2), "hurt": round(hurt, 2)})

    picks: List[Dict[str, Any]] = []
    for budget in budgets:
        feasible = [p for p in points if p["hurt"] <= budget]
        if not feasible:
            picks.append({"budget": budget, "name": "（无可行策略）", "ate": None, "hurt": None})
            continue
        best = max(feasible, key=lambda p: p["ate"])
        picks.append({"budget": budget, **best})

    return {"points": points, "picks": picks, "repeats": repeats}


def format_report(result: Dict[str, Any]) -> str:
    lines = ["候选策略（ref-1，6 个评测 seed，单位：份/回合、次/回合）："]
    for point in result["points"]:
        lines.append(f"  {point['name']:<12} 吃 {point['ate']:5.2f}　伤 {point['hurt']:5.2f}")
    lines.append("")
    lines.append("按受伤预算选：")
    for pick in result["picks"]:
        if pick["ate"] is None:
            lines.append(f"  预算 ≤ {pick['budget']:<4} → （无可行策略）")
        else:
            lines.append(f"  预算 ≤ {pick['budget']:<4} → {pick['name']}（吃 {pick['ate']:.2f}，伤 {pick['hurt']:.2f}）")
    return "\n".join(lines)
