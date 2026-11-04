"""示例 1：拿它当"评测台"——给你自己的模型算留出分数。

场景：一个二分类器。特征是一维数值，标签由阈值决定（>0.5 为 1）。
你会看到：训练集上调阈值 → 留出集上报分数 → 与"随机猜"对比。

跑法：
    python examples/eval_harness.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lab.core import evaluate_policy  # noqa: E402


class PointEnv:
    """一个"回合"就是一道题：给一个特征，猜标签。"""

    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)
        self.done = False

    def reset(self):
        self.value = round(self.rng.random(), 4)
        self.label = 1 if self.value > 0.5 else 0
        self.done = False
        return self.value

    def step(self, action):
        correct = int(action) == self.label
        self.done = True
        return {"observation": self.value, "reward": 1.0 if correct else 0.0, "done": True}


class ThresholdPolicy:
    """最笨的分类器：value > threshold 判 1。阈值在训练集上调出来。"""

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold

    def act(self, observation):
        return 1 if observation > self.threshold else 0


class RandomPolicy:
    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)

    def act(self, observation):
        return self.rng.randint(0, 1)


def train_threshold(seeds, steps=1) -> float:
    """在训练 seed 上扫阈值，取准确率最高者。"""
    best_threshold, best_score = 0.5, -1.0
    for candidate in [round(0.1 * i, 1) for i in range(2, 10)]:
        stats = evaluate_policy(
            make_env=PointEnv, policy=ThresholdPolicy(candidate), episodes=len(seeds), steps=steps, seeds=seeds
        )
        if stats["mean_return"] > best_score:
            best_threshold, best_score = candidate, stats["mean_return"]
    return best_threshold


def demo() -> dict:
    train_seeds = list(range(1000, 1020))
    holdout_seeds = list(range(9000, 9020))

    threshold = train_threshold(train_seeds)
    learned = evaluate_policy(
        make_env=PointEnv, policy=ThresholdPolicy(threshold), episodes=len(holdout_seeds), steps=1, seeds=holdout_seeds
    )
    chance = evaluate_policy(
        make_env=PointEnv, policy=RandomPolicy(7), episodes=len(holdout_seeds), steps=1, seeds=holdout_seeds
    )
    print(f"训练集上调出的阈值：{threshold}")
    print(f"留出集准确率：{learned['mean_return']:.3f}（20 题）")
    print(f"随机猜的准确率：{chance['mean_return']:.3f}")
    print("注意：留出 seed 与训练 seed 完全不重叠，这是这套评测唯一有意义的地方。")
    return {"threshold": threshold, "learned": learned["mean_return"], "chance": chance["mean_return"]}


if __name__ == "__main__":
    demo()
