"""训练 / 评测的分离与课程（v0.4 第二块）。

没有这一层，"变强"就是背答案。规则只有两条，但都是硬规矩：

1. **训练 seed 与评测 seed 永不重叠**（1000–1999 vs 9000–9999）。
2. 评测跑固定步数、固定 seed，**任何人复算必须得到同一个分数**。

课程：同一批 seed 下，若成功率超过阈值，下一轮把步数上限调高（任务变难），
否则会一直停在"简单任务刷分"上。
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

from .agent import (
    EVAL_SEED_RANGE,
    TRAIN_SEED_RANGE,
    QLearningAgent,
    _distance_to_food,
    reward_of,
    state_of,
)
from .env import GridWorld, greedy_action


def train_seeds(count: int) -> Tuple[int, ...]:
    if count <= 0:
        raise ValueError("count 必须是正整数")
    start, stop = TRAIN_SEED_RANGE
    return tuple(range(start, start + count)) if start + count - 1 <= stop else tuple(
        range(start, stop + 1)
    )


def eval_seeds(count: int) -> Tuple[int, ...]:
    if count <= 0:
        raise ValueError("count 必须是正整数")
    start, stop = EVAL_SEED_RANGE
    return tuple(range(start, start + count)) if start + count - 1 <= stop else tuple(
        range(start, stop + 1)
    )


def assert_disjoint() -> None:
    if set(train_seeds(1000)) & set(eval_seeds(1000)):
        raise AssertionError("训练与评测 seed 重叠：这会让所有'变强'的结论失效")


def run_episode(
    agent: QLearningAgent,
    seed: int,
    steps: int,
    *,
    train: bool,
    epsilon: float = 0.0,
    hazards: int = 4,
    with_walls: bool = False,
    lethal: bool = False,
    armor: bool = False,
    size: int = 8,
    layout: str = "random",
    with_path: bool = False,
    slippery: float = 0.0,
    hazard_drift: int = 0,
    hurt_penalty: float = -1.0,
    one_hit: bool = False,
    survival_bonus: float = 0.0,
    death_penalty: float = -5.0,
    bonus_requires_progress: bool = False,
) -> Dict[str, Any]:
    environment = GridWorld(seed, hazards=hazards, lethal=lethal, armor=armor, size=size, layout=layout, slippery=slippery, hazard_drift=hazard_drift, one_hit=one_hit)
    state = state_of(environment, with_walls=with_walls, with_path=with_path)
    total_reward = 0.0
    ate = hurt = 0
    for _ in range(steps):
        action = agent.act(state, epsilon=epsilon) if train else agent.best_action(state)
        previous_distance = _distance_to_food(environment)
        outcome = environment.step(action)
        following = state_of(environment, with_walls=with_walls, with_path=with_path)
        reward = reward_of(
            previous_distance, environment, outcome,
            hurt_penalty=hurt_penalty, survival_bonus=survival_bonus,
        )
        if bonus_requires_progress and survival_bonus != 0.0:
            # "按劳分配"：只有真的靠近了食物，才拿存活奖励（对应实验 0025 的 workfare 组）
            if _distance_to_food(environment) >= previous_distance:
                reward -= survival_bonus
        total_reward += reward
        ate += 1 if outcome.get("ate") else 0
        hurt += 1 if outcome.get("hurt") else 0
        died = bool(environment.dead)
        if died:
            reward += death_penalty             # 死亡惩罚（v0.36 起可调，默认 -5）
        if train:
            agent.update(state, action, reward, following)
        state = following
        if died:
            break
    return {
        "seed": seed,
        "steps": steps,
        "return": round(total_reward, 4),
        "ate": ate,
        "hurt": hurt,
        "energy": environment.energy,
        "damage": environment.damage,
        "dead": bool(environment.dead),
    }


def train(
    agent: QLearningAgent,
    seeds: Sequence[int],
    steps: int,
    epsilon: float = 0.3,
    hazards: int = 4,
    with_walls: bool = False,
    lethal: bool = False,
    armor: bool = False,
    size: int = 8,
    layout: str = "random",
    with_path: bool = False,
    slippery: float = 0.0,
    hazard_drift: int = 0,
    hurt_penalty: float = -1.0,
    one_hit: bool = False,
    survival_bonus: float = 0.0,
    death_penalty: float = -5.0,
    bonus_requires_progress: bool = False,
) -> Dict[str, Any]:
    results = [
        run_episode(
            agent, seed, steps, train=True, epsilon=epsilon, hazards=hazards, with_walls=with_walls,
            lethal=lethal, armor=armor, size=size, layout=layout, with_path=with_path,
            slippery=slippery, hazard_drift=hazard_drift, hurt_penalty=hurt_penalty, one_hit=one_hit,
            survival_bonus=survival_bonus, death_penalty=death_penalty,
        )
        for seed in seeds
    ]
    return {
        "episodes": len(results),
        "mean_return": round(sum(item["return"] for item in results) / len(results), 4),
        "ate": sum(item["ate"] for item in results),
        "hurt": sum(item["hurt"] for item in results),
    }


def evaluate(agent: QLearningAgent, seeds: Sequence[int], steps: int, hazards: int = 4, with_walls: bool = False, lethal: bool = False, armor: bool = False, size: int = 8, layout: str = "random", with_path: bool = False, slippery: float = 0.0, hazard_drift: int = 0, hurt_penalty: float = -1.0, one_hit: bool = False, survival_bonus: float = 0.0, death_penalty: float = -5.0, bonus_requires_progress: bool = False) -> Dict[str, Any]:
    """固定 seed、固定步数、**不学习**。这是唯一被允许用来宣称"变强了"的分数。"""
    results = [run_episode(agent, seed, steps, train=False, hazards=hazards, with_walls=with_walls, lethal=lethal, armor=armor, size=size, layout=layout, with_path=with_path, slippery=slippery, hazard_drift=hazard_drift, hurt_penalty=hurt_penalty, one_hit=one_hit, survival_bonus=survival_bonus, death_penalty=death_penalty, bonus_requires_progress=bonus_requires_progress) for seed in seeds]
    return {
        "episodes": len(results),
        "mean_return": round(sum(item["return"] for item in results) / len(results), 4),
        "ate": sum(item["ate"] for item in results),
        "hurt": sum(item["hurt"] for item in results),
        "seeds": list(seeds),
    }


def baseline_score(seeds: Sequence[int], steps: int, hazards: int = 4, lethal: bool = False, armor: bool = False, size: int = 8, layout: str = "random", with_path: bool = False, slippery: float = 0.0, hazard_drift: int = 0, hurt_penalty: float = -1.0, one_hit: bool = False, survival_bonus: float = 0.0, death_penalty: float = -5.0, bonus_requires_progress: bool = False) -> Dict[str, Any]:
    """对照组：BFS 贪心基线（就是 v0.1–v0.3 用的那个）。"""
    total = 0.0
    ate = hurt = 0
    for seed in seeds:
        environment = GridWorld(seed, hazards=hazards, lethal=lethal, armor=armor, size=size, layout=layout, slippery=slippery, hazard_drift=hazard_drift, one_hit=one_hit)
        previous_distance = _distance_to_food(environment)
        for _ in range(steps):
            previous_distance = _distance_to_food(environment)
            outcome = environment.step(greedy_action(environment))
            total += reward_of(previous_distance, environment, outcome, hurt_penalty=hurt_penalty, survival_bonus=survival_bonus)
            ate += 1 if outcome.get("ate") else 0
            hurt += 1 if outcome.get("hurt") else 0
            if environment.dead:
                total -= 5.0
                break
    return {
        "episodes": len(seeds),
        "mean_return": round(total / max(1, len(seeds)), 4),
        "ate": ate,
        "hurt": hurt,
        "seeds": list(seeds),
    }
