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
ARMOR_MAX = 1.0
ARMOR_HIT_COST = 0.4      # 有甲时，一次中毒先扣甲
ARMOR_REGEN = 0.01        # 没受伤时每步回一点甲
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
        lethal: bool = False,
        armor: bool = False,
        size: int = SIZE,
        layout: str = "random",
        slippery: float = 0.0,
        hazard_drift: int = 0,
        one_hit: bool = False,
        starve_ends: bool = False,
    ) -> None:
        rng = random.Random(seed)
        self.size = int(size)
        self.layout = str(layout)
        self.slippery = max(0.0, min(1.0, float(slippery)))
        self.rng = rng
        self.hazard_drift = int(hazard_drift)
        self.one_hit = bool(one_hit)
        self.starve_ends = bool(starve_ends)
        self.steps_taken = 0
        cells = [(x, y) for x in range(self.size) for y in range(self.size)]
        rng.shuffle(cells)

        self.agent: Tuple[int, int] = (0, 0)
        self.steps = 0
        self.energy = ENERGY_MAX
        self.damage = 0.0
        self.lethal = bool(lethal)
        self.dead = False
        self.has_armor = bool(armor)
        self.armor = ARMOR_MAX if armor else 0.0
        self.hazards_blocked = 0     # 被护甲挡下的中毒次数（可观测行为）
        # 致命模式下中毒两次即死（每次 0.5）；非致命模式仍是一次 0.25
        self.hazard_damage = 0.5 if self.lethal else HAZARD_DAMAGE

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

        if self.layout == "rooms":
            # 房间式（v0.50）：一横一竖两面墙，每面留两个门，保证可通行
            self.walls = set()
            line = max(2, self.size // 2)
            doors = {rng.randrange(1, self.size - 1), rng.randrange(1, self.size - 1)}
            for k in range(self.size):
                if k not in doors:
                    self.walls.add((line, k))
                    self.walls.add((k, line))
            reserved |= self.walls
        elif self.layout == "corridor":
            # 走廊式（v0.25 改为稀疏隔断）：奇数行是隔断，每行留 2 个缺口 → 需要绕行但不至于走不通
            gap_pool = list(range(1, self.size - 1))
            self.walls = set()
            for row_index, y in enumerate(range(1, self.size, 2)):
                gaps = {gap_pool[(row_index * 2) % len(gap_pool)], gap_pool[(row_index * 2 + 3) % len(gap_pool)]}
                for x in range(self.size):
                    if x not in gaps:
                        self.walls.add((x, y))
            reserved |= self.walls
        else:
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
            "armor": round(self.armor, 4),
            "food_left": float(len(self.food)),
            "alive": 0.0 if self.dead or self.energy <= 0 else 1.0,
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

    def _drift_hazards(self) -> None:
        """每隔 hazard_drift 步把危险区挪到新的空位（v0.31：分布漂移）。"""
        if self.hazard_drift <= 0:
            return
        self.steps_taken += 1
        if self.steps_taken % self.hazard_drift != 0:
            return
        free = [
            (x, y)
            for x in range(self.size)
            for y in range(self.size)
            if (x, y) not in self.walls and (x, y) not in self.food and (x, y) != self.agent
        ]
        self.rng.shuffle(free)
        self.hazards = set(free[: len(self.hazards)])

    def step(self, action: str) -> Dict[str, object]:
        if self.slippery > 0.0 and self.rng.random() < self.slippery:
            action = self.rng.choice(["up", "down", "left", "right"])   # 打滑：动作被替换
        self._drift_hazards()
        x, y = self._target(action)
        blocked = not (0 <= x < self.size and 0 <= y < self.size) or (x, y) in self.walls
        if not blocked:
            self.agent = (x, y)

        ate = False
        if self.agent in self.food:
            self.food.discard(self.agent)
            self.energy = min(ENERGY_MAX, self.energy + FOOD_GAIN)
            ate = True

        hurt = False
        if self.agent in self.hazards:
            if self.armor > 0:
                self.armor = max(0.0, self.armor - ARMOR_HIT_COST)
                self.hazards_blocked += 1
                hurt = False          # 甲挡住了，不受伤
            else:
                self.damage = min(DAMAGE_MAX, self.damage + self.hazard_damage)
                hurt = True

        if self.has_armor and self.armor < ARMOR_MAX:
            self.armor = min(ARMOR_MAX, self.armor + ARMOR_REGEN)
        self.energy = max(0.0, self.energy - ENERGY_COST_PER_STEP)
        if self.starve_ends and self.energy <= 0.0:
            self.dead = True            # v0.43：饿死也算结束（否则"不动"永远是划算的）
        if self.one_hit and hurt:
            self.dead = True          # v0.35：碰一下即结束
        elif self.lethal and self.damage >= DAMAGE_MAX:
            self.dead = True
            self.energy = 0.0
        self.steps += 1

        return {
            "step": self.steps,
            "action": action,
            "blocked": blocked,
            "ate": ate,
            "hurt": hurt,
            "armor_blocked": bool(self.armor > 0 and self.agent in self.hazards),
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
            if not (0 <= nxt[0] < env.size and 0 <= nxt[1] < env.size):
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
