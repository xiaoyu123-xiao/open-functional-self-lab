"""8×8 网格环境（Issue 0001）。

这是一个**玩具环境**，不是模型：它只做三件事——让你看得见状态、能量会掉、踩到危险区会受伤。
存在的意义是让 `lab run` 不再输出编造的数字，而是跑一个真有内部状态、真会失败的闭环。

设计约束（来自 docs/gap-analysis.md C4：普通电脑也要能跑）：
- 纯标准库，零依赖，CPU 上每秒数千步
- 同一 seed 下**逐字节可复现**（测试里有断言）
- 不联网、不读文件、不含随机外部性
"""

from __future__ import annotations

import random
from typing import Dict, List, Tuple

SIZE = 8
ACTIONS = ("up", "down", "left", "right", "rest")

ENERGY_MAX = 1.0
ENERGY_COST_PER_STEP = 0.02
FOOD_GAIN = 0.20
HAZARD_DAMAGE = 0.25
DAMAGE_MAX = 1.0
FOOD_COUNT = 5
HAZARD_COUNT = 4
WALL_COUNT = 6


class GridWorld:
    """确定性网格世界：状态全在对象里，step() 只前进不回头。"""

    def __init__(
        self,
        seed: int = 0,
        *,
        walls: int = WALL_COUNT,
        food: int = FOOD_COUNT,
        hazards: int = HAZARD_COUNT,
    ) -> None:
        rng = random.Random(seed)
        cells = [(x, y) for x in range(SIZE) for y in range(SIZE)]
        rng.shuffle(cells)

        self.agent: Tuple[int, int] = (0, 0)
        self.steps = 0
        self.energy = ENERGY_MAX
        self.damage = 0.0

        reserved = {self.agent}
        def take(count: int) -> List[Tuple[int, int]]:
            picked: List[Tuple[int, int]] = []
            for cell in cells:
                if len(picked) >= count:
                    break
                if cell in reserved:
                    continue
                picked.append(cell)
                reserved.add(cell)
            return picked

        self.walls = set(take(int(walls)))
        self.food = set(take(int(food)))
        self.hazards = set(take(int(hazards)))

    # ---------- 观测 ----------

    def observe(self) -> Dict[str, float]:
        """agent 能看到的东西（不含隐藏状态）。"""
        return {
            "x": float(self.agent[0]),
            "y": float(self.agent[1]),
            "energy": round(self.energy, 4),
            "damage": round(self.damage, 4),
            "food_left": float(len(self.food)),
            "alive": 1.0 if self.energy > 0 else 0.0,
        }

    def homeostatic_error(self) -> float:
        """内感受：偏离"活得舒服"的区间有多远（0 表示舒服）。"""
        low_energy = max(0.0, 0.30 - self.energy)
        high_damage = max(0.0, self.damage - 0.50)
        return round(low_energy + high_damage, 4)

    # ---------- 动作 ----------

    def _target(self, action: str) -> Tuple[int, int]:
        x, y = self.agent
        if action == "up":
            y += 1
        elif action == "down":
            y -= 1
        elif action == "left":
            x -= 1
        elif action == "right":
            x += 1
        elif action == "rest":
            pass
        else:
            raise ValueError(f"未知动作：{action!r}（合法值：{', '.join(ACTIONS)}）")
        return x, y

    def step(self, action: str) -> Dict[str, object]:
        x, y = self._target(action)
        blocked = not (0 <= x < SIZE and 0 <= y < SIZE) or (x, y) in self.walls
        if not blocked:
            self.agent = (x, y)

        ate = False
        if self.agent in self.food:
            self.food.discard(self.agent)
            self.energy = min(ENERGY_MAX, self.energy + FOOD_GAIN)
            ate = True

        hurt = False
        if self.agent in self.hazards:
            self.damage = min(DAMAGE_MAX, self.damage + HAZARD_DAMAGE)
            hurt = True

        self.energy = max(0.0, self.energy - ENERGY_COST_PER_STEP)
        self.steps += 1

        return {
            "step": self.steps,
            "action": action,
            "blocked": blocked,
            "ate": ate,
            "hurt": hurt,
            "observation": self.observe(),
            "homeostatic_error": self.homeostatic_error(),
        }


def greedy_action(env: GridWorld) -> str:
    """最笨的基线策略：用 BFS 朝最近的食物走一步；没有食物就原地休息。

    刻意保持"笨"：它的作用是对照，不是变聪明。任何更聪明的策略都应该
    在 docs/metrics.md 定义的指标上打败它，否则说明指标有问题。
    它不知道危险区在哪（所以会受伤），也不记忆走过的路。
    """
    if not env.food:
        return "rest"

    from collections import deque  # 局部导入：环境模块保持零顶层依赖

    moves = {"up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0)}
    start = env.agent
    previous: Dict[Tuple[int, int], Tuple[Tuple[int, int], str]] = {}
    seen = {start}
    queue = deque([start])
    found: "Tuple[int, int] | None" = None

    while queue:
        current = queue.popleft()
        if current in env.food and current != start:
            found = current
            break
        for action in ("up", "down", "left", "right"):
            dx, dy = moves[action]
            nxt = (current[0] + dx, current[1] + dy)
            if nxt in seen or nxt in env.walls:
                continue
            if not (0 <= nxt[0] < SIZE and 0 <= nxt[1] < SIZE):
                continue
            seen.add(nxt)
            previous[nxt] = (current, action)
            queue.append(nxt)

    if found is None:
        return "rest"

    # 从食物倒推回起点，取第一步动作
    node = found
    first_action = "rest"
    while node in previous and previous[node][0] != start:
        node, first_action = previous[node][0], previous[node][1]
    if node in previous:
        first_action = previous[node][1]
    return first_action


def persistence_error(previous: Dict[str, float], current: Dict[str, float], keys: Tuple[str, ...]) -> float:
    """朴素预测基线：假设"下一步和上一步一样"，误差就是偏离程度。

    对应 docs/metrics.md 里"与朴素基线（上一步重复）对比"的要求。
    """
    total = 0.0
    for key in keys:
        total += abs(float(current.get(key, 0.0)) - float(previous.get(key, 0.0)))
    return round(total / max(1, len(keys)), 4)
