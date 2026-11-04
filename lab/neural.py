"""神经策略：纯 Python 的单隐层 MLP（v0.24）。

为什么要它：线性和表格在"需要绕行"的任务（走廊地图）上都卡住了。
它们的共同点是**只用线性组合**，表达不了"如果左边是墙且食物在右，就先向下"这种条件。

这里用 25 → 16 → 5 的 MLP（tanh 隐层），手写反向传播，纯标准库：

    Q(s, a) = W2[a] · tanh(W1 · φ(s) + b1) + b2[a]

为什么不用 torch：
- 这台机器装不了（也不该为了跑通一个玩具任务去下 2GB）
- 纯 Python 在这个规模下够快（单步约 480 次乘加）
- 真要上 GPU 时，接口不变，只换实现（见 `docs/EXTENDING-THE-POLICY.md`）

它仍然受同一套约束：训练/留出 seed 分离、变差回滚、账本记录。
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any, Dict, List, Sequence

from .env import ACTIONS
from .linear import featurize

HIDDEN = 16
LR = 0.002   # 实测：0.02/0.01 会发散；0.002 稳定（见 docs/experiments/0012）
GAMMA = 0.95


class NeuralQAgent:
    """单隐层 MLP 的 Q 函数。接口与表格/线性版一致（鸭子类型）。"""

    algo = "neural"

    def __init__(self, path: "str | Path | None" = None, seed: int = 0, hidden: int = HIDDEN) -> None:
        self.path = Path(path) if path else None
        self.rng = random.Random(seed)
        self.hidden = hidden
        self.updates = 0

        dim = len(featurize("=U|2|2|0|h1|s0"))
        self.dim = dim
        scale = 1.0 / math.sqrt(dim)
        self.w1: List[List[float]] = [[self.rng.uniform(-scale, scale) for _ in range(dim)] for _ in range(hidden)]
        self.b1: List[float] = [0.0] * hidden
        self.w2: List[List[float]] = [[self.rng.uniform(-scale, scale) for _ in range(hidden)] for _ in ACTIONS]
        self.b2: List[float] = [0.0] * len(ACTIONS)

    # ---------- 前向 ----------

    def _hidden(self, phi: Sequence[float]) -> List[float]:
        hidden = []
        for row in self.w1:
            total = 0.0
            for weight, value in zip(row, phi):
                total += weight * value
            hidden.append(math.tanh(total + 0.0))
        return hidden

    def value(self, state: str) -> Dict[str, float]:
        phi = featurize(state)
        hidden = self._hidden(phi)
        out = {}
        for action, row, bias in zip(ACTIONS, self.w2, self.b2):
            total = 0.0
            for weight, value in zip(row, hidden):
                total += weight * value
            out[action] = total + bias
        return out

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

    # ---------- 反向传播 ----------

    def update(self, state: str, action: str, reward: float, next_state: str) -> None:
        phi = featurize(state)
        hidden = self._hidden(phi)
        target = reward + GAMMA * max(self.value(next_state).values())
        index = ACTIONS.index(action)
        predicted = sum(w * h for w, h in zip(self.w2[index], hidden)) + self.b2[index]
        error = target - predicted

        lr = LR / math.sqrt(1.0 + self.updates / 500.0)
        # 只对选中的动作回传（Q-learning 的标准做法）
        for j, value in enumerate(hidden):
            self.w2[index][j] += lr * error * value
        self.b2[index] += lr * error

        # 隐层梯度：dL/dh_j = error * w2[idx][j]，再乘 tanh 导数
        for j in range(self.hidden):
            d_hidden = error * self.w2[index][j] * (1.0 - hidden[j] ** 2)
            if d_hidden == 0.0:
                continue
            row = self.w1[j]
            for i, feature in enumerate(phi):
                if feature:
                    row[i] += lr * d_hidden * feature
        self.updates += 1

    # ---------- 存取 ----------

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 4,
            "algo": self.algo,
            "hidden": self.hidden,
            "dim": self.dim,
            "updates": self.updates,
            "w1": self.w1,
            "b1": self.b1,
            "w2": self.w2,
            "b2": self.b2,
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    def load(self) -> "NeuralQAgent":
        if self.path is None or not self.path.exists():
            return self
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("algo") != self.algo or int(payload.get("dim", 0)) != self.dim:
            return self                       # 不兼容就从头开始，绝不混用
        self.hidden = int(payload.get("hidden", self.hidden))
        self.w1 = [[float(v) for v in row] for row in payload["w1"]]
        self.b1 = [float(v) for v in payload["b1"]]
        self.w2 = [[float(v) for v in row] for row in payload["w2"]]
        self.b2 = [float(v) for v in payload["b2"]]
        self.updates = int(payload.get("updates", 0))
        return self

    def describe(self) -> str:
        return f"neural（{self.dim}→{self.hidden}→{len(ACTIONS)}，更新 {self.updates} 次）"
