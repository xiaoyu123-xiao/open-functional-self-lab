"""可学习策略（v0.4 的第一块，也是这个项目第一次"真的会变强"）。

为什么必须做这件事：v0.1–v0.3 的系统能力上限是固定的 BFS 基线。
不管读多少论文、记多少账，行为都不会变——那叫记录，不叫进化。

这里用最小可学策略（表格 Q-learning，纯标准库、纯 CPU）：
    state  = (相对最近食物的方向, 能量档, 损伤档)
    action = 5 个网格动作
    参数   = Q 表，存 state/policy.json

三条纪律：
1. **训练集与评测集严格不重叠**（seed 段分离），否则"变强"是背答案。
2. 评测用固定 seed、固定步数，任何人可复算同一个分数。
3. 学不动就如实报告：`train()` 不保证变好，`loop` 会在变差时回滚策略。
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .env import ACTIONS, GridWorld

ALPHA = 0.2          # 学习率
GAMMA = 0.95         # 折扣
EPSILON_START = 0.35
EPSILON_END = 0.05
SHAPING = 0.10       # 靠近食物给一点奖励，让稀疏奖励能学起来

TRAIN_SEED_RANGE = (1000, 1999)
EVAL_SEED_RANGE = (9000, 9999)   # 与训练段**永不重叠**


def _bucket_energy(value: float) -> int:
    if value < 0.3:
        return 0
    if value < 0.6:
        return 1
    return 2


def _bucket_damage(value: float) -> int:
    return 0 if value < 0.5 else 1


def _food_direction(env: GridWorld) -> str:
    if not env.food:
        return "none"
    ax, ay = env.agent
    tx, ty = min(env.food, key=lambda cell: abs(cell[0] - ax) + abs(cell[1] - ay))
    dx, dy = tx - ax, ty - ay
    horizontal = "R" if dx > 0 else ("L" if dx < 0 else "=")
    vertical = "U" if dy > 0 else ("D" if dy < 0 else "=")
    return horizontal + vertical


def _bucket_distance(env: GridWorld) -> int:
    """0 = 就在脚下 / 1 = 一步 / 2 = 两三步 / 3 = 更远。"""
    distance = _distance_to_food(env)
    if distance <= 0:
        return 0
    if distance == 1:
        return 1
    if distance <= 3:
        return 2
    return 3


# 负结果（实验 0002）：把"四方向墙体"加进状态后，状态数从 126 涨到 948，
# 同样 320 回合训练下留出分数从 +2.6 掉到 -0.4。表格法在样本有限时会被状态爆炸拖死。
# 结论：加特征不是免费的；要加就先换函数逼近（见 docs/experiments/0002-feature-bloat.md）。


def _wall_code(env: GridWorld) -> str:
    """四个方向能不能走（上下左右，1=能走）。只在 state_mode="walls" 时进入状态。"""
    x, y = env.agent
    code = []
    for dx, dy in ((0, 1), (0, -1), (-1, 0), (1, 0)):
        nx, ny = x + dx, y + dy
        legal = 0 <= nx < env.size and 0 <= ny < env.size and (nx, ny) not in env.walls
        code.append("1" if legal else "0")
    return "".join(code)


def _hazard_bucket(env: GridWorld) -> str:
    """"任务身份"：危险区密度分档。没有它，同一观测在不同任务下会互相干扰（实验 0006）。"""
    count = len(env.hazards)
    if count <= 2:
        return "h0"
    if count <= 5:
        return "h1"
    if count <= 8:
        return "h2"
    return "h3"


def state_of(env: GridWorld, with_walls: bool = False) -> str:
    """状态 =（食物方向 | 距离档 | 能量档 | 损伤档）。

    v0.5 试过加入"四方向墙体"，结果状态数 126→948、留出分数 +2.6→-0.4，已撤回。
    要加特征必须先换函数逼近，否则是被状态爆炸拖死，不是"更聪明"。
    """
    observation = env.observe()
    parts = [
        _food_direction(env),
        str(_bucket_distance(env)),
        str(_bucket_energy(observation["energy"])),
        str(_bucket_damage(observation["damage"])),
    ]
    if with_walls:
        parts.append(_wall_code(env))
    parts.append(_hazard_bucket(env))     # v0.13：任务身份，让多任务不再互相干扰
    return "|".join(parts)


def _distance_to_food(env: GridWorld) -> int:
    if not env.food:
        return 0
    ax, ay = env.agent
    return min(abs(cell[0] - ax) + abs(cell[1] - ay) for cell in env.food)


class QLearningAgent:
    """表格 Q-learning。参数可存盘，因此"它学到的东西"是可审计的。"""

    def __init__(self, path: "str | Path | None" = None, seed: int = 0) -> None:
        self.path = Path(path) if path else None
        self.rng = random.Random(seed)
        self.table: Dict[str, Dict[str, float]] = {}
        self.updates = 0

    # ---------- 参数 ----------

    def q(self, state: str) -> Dict[str, float]:
        row = self.table.get(state)
        if row is None:
            row = {action: 0.0 for action in ACTIONS}
            self.table[state] = row
        return row

    def best_action(self, state: str) -> str:
        row = self.q(state)
        best = max(row.values())
        candidates = [action for action, value in row.items() if value == best]
        return self.rng.choice(candidates)      # 并列随机，避免固定偏向某个方向

    def act(self, state: str, epsilon: float = 0.0) -> str:
        if epsilon > 0 and self.rng.random() < epsilon:
            return self.rng.choice(list(ACTIONS))
        return self.best_action(state)

    def update(self, state: str, action: str, reward: float, next_state: str) -> None:
        row = self.q(state)
        future = max(self.q(next_state).values())
        # 学习率随更新次数衰减（1/sqrt）：继续训练时不会把已经学好的策略冲垮。
        # 这是 v0.5 的修复：不加衰减时，第二轮训练会让留出分数从 +1.3 掉到 -0.1。
        alpha = ALPHA / math.sqrt(1.0 + self.updates / 500.0)
        row[action] += alpha * (reward + GAMMA * future - row[action])
        self.updates += 1

    # ---------- 存取 ----------

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "states": len(self.table), "updates": self.updates, "table": self.table}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    def load(self) -> "QLearningAgent":
        if self.path is None or not self.path.exists():
            return self
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.table = {state: {action: float(value) for action, value in row.items()} for state, row in payload.get("table", {}).items()}
        self.updates = int(payload.get("updates", 0))
        return self


def reward_of(previous_distance: int, env: GridWorld, outcome: Dict[str, Any]) -> float:
    """奖励设计：吃到 +1、受伤 -1、每步小惩罚、靠近食物给 shaping。"""
    reward = -0.01
    if outcome.get("ate"):
        reward += 1.0
    if outcome.get("hurt"):
        reward -= 1.0
    current = _distance_to_food(env)
    reward += SHAPING * (previous_distance - current)
    return reward
