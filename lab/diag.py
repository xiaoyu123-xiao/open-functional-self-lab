"""诊断：这个策略到底学到了什么，还是只在抄手写规则？

为什么需要它（v0.28）：
实验 0015 把"该往哪走"塞进了特征，走廊分数立刻转正。但有个更根本的问题——
**如果策略只是逐步复制 BFS，那它就没有存在价值：直接用 BFS 更快、更省。**

所以要能回答两件事：
    1. 它与 BFS 的动作一致率是多少（1.0 = 完全照抄）
    2. 在不一致的地方，它是更好还是更差（用分数与吃到份数佐证）
"""

from __future__ import annotations

from typing import Any, Dict, Sequence

from .agent import _next_step, reward_of, state_of, _distance_to_food
from .env import ACTIONS, GridWorld

# _next_step 的编码：n1=上 n2=下 n3=左 n4=右 n0=原地
_CODE_TO_ACTION = {"n1": "up", "n2": "down", "n3": "left", "n4": "right", "n0": "rest"}


def bfs_action(env: GridWorld) -> str:
    """BFS 认为该走的动作（与特征同源，仅用于对照）。"""
    return _CODE_TO_ACTION.get(_next_step(env), "rest")


def measure_agreement(
    agent: Any,
    seeds: Sequence[int],
    steps: int,
    *,
    hazards: int = 4,
    lethal: bool = False,
    armor: bool = False,
    size: int = 8,
    layout: str = "random",
    with_path: bool = False,
) -> Dict[str, Any]:
    """跑一批回合，统计"智能体动作 == BFS 动作"的比例。"""
    total = 0
    agree = 0
    score = 0.0
    ate = 0
    for seed in seeds:
        env = GridWorld(seed, hazards=hazards, lethal=lethal, armor=armor, size=size, layout=layout)
        state = state_of(env, with_path=with_path)
        previous = _distance_to_food(env)
        for _ in range(steps):
            if env.dead:
                break
            learned = agent.best_action(state) if hasattr(agent, "best_action") else agent.act(state)
            expected = bfs_action(env)
            total += 1
            if learned == expected:
                agree += 1
            before_food = len(env.food)
            outcome = env.step(learned)
            reward = reward_of(previous, env, outcome)
            score += reward
            ate += max(0, before_food - len(env.food))
            if hasattr(agent, "update"):
                following = state_of(env, with_path=with_path)
                agent.update(state, learned, reward, following)
                state = following
            previous = _distance_to_food(env)
            if env.dead:
                break
    return {
        "steps": total,
        "agree": agree,
        "agreement": round(agree / total, 4) if total else 0.0,
        "mean_return": round(score / len(seeds), 4) if seeds else 0.0,
        "ate": ate,
    }


def compare(agent: Any, seeds: Sequence[int], steps: int, **kwargs: Any) -> str:
    stats = measure_agreement(agent, seeds, steps, **kwargs)
    return (
        f"与 BFS 动作一致率 {stats['agreement'] * 100:.0f}%（{stats['agree']}/{stats['steps']} 步），"
        f"均分 {stats['mean_return']:+.3f}，吃到 {stats['ate']} 份"
    )
