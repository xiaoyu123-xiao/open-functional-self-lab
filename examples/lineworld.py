"""示例：把你自己的世界接进来（20 行）。

场景：一条数轴，位置 0..9。走到 9 得 +1，走过头掉出边界得 −1。
这跟 8×8 网格完全无关，但用的是同一个审计外壳。

跑法：
    python -m lab.cli generic --env examples/lineworld.py:make_env \
                              --policy examples/lineworld.py:RightPolicy \
                              --steps 12
"""

from __future__ import annotations

import random


class LineWorld:
    """最小环境：只要求 reset() 和 step(action)。"""

    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)
        self.position = 0
        self.done = False

    def reset(self):
        self.position = 0
        self.done = False
        return self.position

    def step(self, action):
        if self.done:
            return {"observation": self.position, "reward": 0.0, "done": True}
        if action == "right":
            self.position += 1
        elif action == "left":
            self.position = max(0, self.position - 1)
        reward = 0.0
        if self.position >= 9:
            reward = 1.0
            self.done = True
        return {"observation": self.position, "reward": reward, "done": self.done}


class RightPolicy:
    """最笨的策略：一直往右。用它验证外壳能跑通你自己的东西。"""

    def act(self, observation):
        return "right"


class RandomPolicy:
    def act(self, observation):
        return "right" if observation < 9 else "left"


def make_env(seed: int = 0) -> LineWorld:
    return LineWorld(seed)


def make_policy() -> RightPolicy:
    return RightPolicy()
