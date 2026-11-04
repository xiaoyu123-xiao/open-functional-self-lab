"""示例 2：包一个"模型"——先扣预算、非法输出降级、调用进账本。

这里用 MockModel 代替真实 LLM（离线可跑）；换成任何 OpenAI 兼容客户端只改 3 行。

跑法：
    python examples/llm_wrapper.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lab.budget import Budget, BudgetExceeded  # noqa: E402
from lab.core import run_generic_episode  # noqa: E402
from lab.ledger import Ledger  # noqa: E402

ACTIONS = ("up", "down", "left", "right", "rest")


class MockModel:
    """假装是一个语言模型：大部分时候输出合法动作，偶尔输出一段废话。"""

    def __init__(self, seed: int = 0, noise: float = 0.2) -> None:
        self.rng = random.Random(seed)
        self.noise = noise

    def chat(self, prompt: str) -> str:
        if self.rng.random() < self.noise:
            return "我觉得应该向左走三步，然后再观察一下。"   # 非法输出
        return self.rng.choice(ACTIONS)


class ModelPolicy:
    """把模型包成策略：扣预算 → 调用 → 校验 → 降级。"""

    def __init__(self, model: MockModel, budget: Budget) -> None:
        self.model = model
        self.budget = budget
        self.calls = 0
        self.illegal = 0

    def act(self, observation):
        self.budget.charge("search_requests_per_day", 1)   # 先付钱，再调用
        self.calls += 1
        reply = self.model.chat(f"state={observation}")
        action = reply.strip().lower()
        if action not in ACTIONS:
            self.illegal += 1
            return "rest"                                   # 非法输出一律降级，不猜
        return action


class TinyWorld:
    """最简单的一个环境：三个位置，走到最右边算成功。"""

    def __init__(self) -> None:
        self.position = 0

    def reset(self):
        self.position = 0
        return self.position

    def step(self, action):
        if action == "right":
            self.position += 1
        elif action == "left":
            self.position = max(0, self.position - 1)
        done = self.position >= 2
        return {"observation": self.position, "reward": 1.0 if done else 0.0, "done": done}


def demo(cap: float = 8.0, workdir: Path | None = None) -> dict:
    base = Path(workdir) if workdir else Path("state")
    base.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(base / "demo-ledger.jsonl")
    budget = Budget({"search_requests_per_day": cap}, ledger, "2026-01-01T00:00:00Z", run_id="demo-llm")
    policy = ModelPolicy(MockModel(seed=3), budget)
    env = TinyWorld()

    print(f"预算上限：{cap} 次调用")
    try:
        result = run_generic_episode(
            env=env,
            policy=policy,
            steps=20,
            ledger=ledger,
            ts_of=lambda: "2026-01-01T00:00:00Z",
            budget_charge=lambda kind, amount: budget.charge(kind, amount),
            run_id="demo-llm",
        )
        print(f"结果：{result['steps']} 步，总回报 {result['total_reward']:+.1f}")
        stopped = "跑满"
    except BudgetExceeded as error:
        print(f"预算拦截（这是设计）：{error}")
        stopped = "预算拦截"

    print(f"模型调用 {policy.calls} 次，其中非法输出 {policy.illegal} 次（已降级为 rest）")
    print("每步都写进了 state/demo-ledger.jsonl，可用 `python -m lab.cli verify` 校验格式。")
    return {"calls": policy.calls, "illegal": policy.illegal, "stopped": stopped}


if __name__ == "__main__":
    demo()
