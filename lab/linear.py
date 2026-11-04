"""线性 Q 函数逼近（v0.6）。

为什么换：表格法在状态数涨到 948 时直接崩了（实验 0002-A），因为每个状态几乎没被访问过。
线性逼近把"没见过但相似"的状态映射到同一组权重上，所以样本效率高得多。

    Q(s, a) = w[a] · φ(s)

φ(s) 从既有的状态字符串里解析，所以不需要改环境、不需要改评测：
    [bias, 食物在右, 食物在左, 食物在上, 食物在下, 距离档(4), 能量档(3), 损伤档]  = 13 维

权重存 `state/policy.json`（与表格法同文件不同结构，靠 `algo` 字段区分）。
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any, Dict, List, Sequence

from .env import ACTIONS

STATE_DIM = 21          # 13 基础 + 4 墙体位 + 4 危险区分档（无信息时补 0）
STATE_DIM_WITH_WALLS = STATE_DIM


def featurize(state: str) -> List[float]:
    """把 `方向|距离档|能量档|损伤档` 变成固定长度向量。未知值一律 0，不抛异常。"""
    parts = state.split("|")
    direction = parts[0] if len(parts) > 0 else "none"
    distance = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 3
    energy = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 2
    damage = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0

    vector = [1.0]                                   # bias
    vector += [1.0 if direction[0:1] == "R" else 0.0]   # 食物在右
    vector += [1.0 if direction[0:1] == "L" else 0.0]   # 食物在左
    vector += [1.0 if direction[1:2] == "U" else 0.0]   # 食物在上
    vector += [1.0 if direction[1:2] == "D" else 0.0]   # 食物在下
    vector += [1.0 if distance == bucket else 0.0 for bucket in range(4)]   # 距离档 one-hot
    vector += [1.0 if energy == bucket else 0.0 for bucket in range(3)]     # 能量档 one-hot
    vector += [1.0 if damage == 1 else 0.0]                                 # 损伤档
    walls = ""
    hazard = ""
    for token in parts[4:]:
        if len(token) == 4 and set(token) <= {"0", "1"}:
            walls = token
        elif len(token) == 2 and token.startswith("h") and token[1].isdigit():
            hazard = token[1]
    vector += [1.0 if walls[index:index + 1] == "1" else 0.0 for index in range(4)]
    vector += [1.0 if hazard == str(bucket) else 0.0 for bucket in range(4)]
    if len(vector) not in (STATE_DIM, STATE_DIM_WITH_WALLS):
        raise ValueError(f"特征维度异常：{len(vector)}")
    return vector


class LinearQAgent:
    """线性 Q-learning。接口与表格版一致，可直接替换（tasks/loop 靠鸭子类型）。"""

    algo = "linear"

    def __init__(self, path: "str | Path | None" = None, seed: int = 0) -> None:
        self.path = Path(path) if path else None
        self.rng = random.Random(seed)
        self.w: Dict[str, List[float]] = {action: [0.0] * STATE_DIM_WITH_WALLS for action in ACTIONS}
        self.updates = 0

    # ---------- 内部 ----------

    def _dot(self, action: str, features: Sequence[float]) -> float:
        weights = self.w[action]
        for index, value in enumerate(features):
            if index >= len(weights):
                weights.append(0.0)
        return sum(weight * value for weight, value in zip(weights, features))

    def value(self, state: str) -> Dict[str, float]:
        phi = featurize(state)
        return {action: self._dot(action, phi) for action in ACTIONS}

    # ---------- 策略 ----------

    def best_action(self, state: str) -> str:
        values = self.value(state)
        best = max(values.values())
        candidates = [action for action, value in values.items() if value == best]
        return self.rng.choice(candidates)

    def act(self, state: str, epsilon: float = 0.0) -> str:
        if epsilon > 0 and self.rng.random() < epsilon:
            return self.rng.choice(list(ACTIONS))
        return self.best_action(state)

    def update(self, state: str, action: str, reward: float, next_state: str) -> None:
        phi = featurize(state)
        target = reward + 0.95 * max(self.value(next_state).values())
        error = target - self._dot(action, phi)
        # 学习率随更新次数衰减，避免持续训练把已学好的权重冲掉（实验 0002-B 的教训）
        alpha = 0.02 / math.sqrt(1.0 + self.updates / 500.0)
        weights = self.w[action]
        for index, feature in enumerate(phi):
            if index >= len(weights):
                weights.append(0.0)
            if feature:
                weights[index] += alpha * error * feature
        self.updates += 1

    # ---------- 存取 ----------

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 2, "algo": self.algo, "updates": self.updates, "weights": self.w}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    def load(self) -> "LinearQAgent":
        if self.path is None or not self.path.exists():
            return self
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("algo") != self.algo:
            return self          # 文件是表格法存的：不兼容就从头开始，绝不混用
        weights = payload.get("weights", {})
        for action in ACTIONS:
            row = weights.get(action)
            if isinstance(row, list) and len(row) in (STATE_DIM, STATE_DIM_WITH_WALLS):
                self.w[action] = [float(value) for value in row]
        self.updates = int(payload.get("updates", 0))
        return self

    def describe(self) -> str:
        top = max(ACTIONS, key=lambda action: sum(abs(v) for v in self.w[action]))
        return f"linear（{STATE_DIM} 维权重 × {len(ACTIONS)} 动作，更新 {self.updates} 次，权重最大在 {top}）"
