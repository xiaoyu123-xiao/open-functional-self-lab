"""通用核心：把任何环境 + 任何策略装进审计/预算/回滚的外壳里（v0.18）。

这是这个仓库对"用户"最有用的部分——不是它自带的 8×8 网格，而是这套外壳：

    你有一个环境（env）和一个策略（policy）→ 20 行接进来 → 立刻获得：
        账本（每步留痕）· 预算闸门（超限即停）· 留出评测 · 回滚点

约定（刻意保持最小，方便你接自己的东西）：

    env.reset() -> observation                  每回合开始时调用一次
    env.step(action) -> dict                    至少含 "observation"；可选 "reward"/"done"/"info"
    policy.act(observation) -> action           任何可哈希对象都行

不要求继承任何基类——鸭子类型就够，这样你可以直接包别人的库。
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, runtime_checkable


@runtime_checkable
class Env(Protocol):
    def reset(self) -> Any: ...
    def step(self, action: Any) -> Dict[str, Any]: ...


@runtime_checkable
class Policy(Protocol):
    def act(self, observation: Any) -> Any: ...


class GenericRunError(RuntimeError):
    """环境或策略不符合约定的最小接口。"""


def load_object(spec: str) -> Any:
    """把 `module.path:attr` 或 `path/to/file.py:attr` 变成对象。"""
    if ":" not in spec:
        raise ValueError(f"需要 `模块:属性` 形式，收到 {spec!r}")
    target, attr = spec.rsplit(":", 1)
    if target.endswith(".py") or "/" in target or "\\" in target:
        path = Path(target)
        if not path.exists():
            raise FileNotFoundError(f"找不到文件：{path}")
        module_name = path.stem
        import importlib.util

        spec_obj = importlib.util.spec_from_file_location(module_name, path)
        if spec_obj is None or spec_obj.loader is None:
            raise ImportError(f"无法加载 {path}")
        module = importlib.util.module_from_spec(spec_obj)
        spec_obj.loader.exec_module(module)
    else:
        module = importlib.import_module(target)
    if not hasattr(module, attr):
        raise AttributeError(f"{target} 里没有 {attr}")
    return getattr(module, attr)


def check_interfaces(env: Any, policy: Any) -> None:
    missing_env = [name for name in ("reset", "step") if not hasattr(env, name)]
    if missing_env:
        raise GenericRunError(f"环境缺少方法：{missing_env}（需要 reset/step）")
    if not hasattr(policy, "act"):
        raise GenericRunError("策略缺少 act(observation) 方法")


def run_generic_episode(
    *,
    env: Any,
    policy: Any,
    steps: int,
    ledger: Any,
    ts_of: Any,
    budget_charge: Optional[Any] = None,
    record_event: str = "gstep",
    run_id: str = "generic-001",
) -> Dict[str, Any]:
    """跑一回合：每步记账 + 扣预算；策略/环境出错时记一条 alert 并停。"""
    check_interfaces(env, policy)
    if steps <= 0:
        raise ValueError("steps 必须是正整数")

    observation = env.reset()
    total_reward = 0.0
    executed = 0
    done = False

    for index in range(1, steps + 1):
        if budget_charge is not None:
            budget_charge("steps_per_run", 1)      # 超限会抛 BudgetExceeded，由调用方决定如何处置
        try:
            action = policy.act(observation)
            outcome = env.step(action)
        except Exception as error:                  # 用户代码出错时不能把账本写坏
            ledger.append(
                "alert",
                {"level": "high", "kind": "generic-run", "detail": f"{type(error).__name__}: {error}"},
                ts_of(),
            )
            raise GenericRunError(f"第 {index} 步失败：{type(error).__name__}: {error}") from error

        if "observation" not in outcome:
            raise GenericRunError("env.step() 必须返回包含 'observation' 的字典")

        reward = float(outcome.get("reward", 0.0))
        total_reward += reward
        done = bool(outcome.get("done", False))
        ledger.append(
            record_event,
            {
                "run_id": run_id,
                "step": index,
                "action": str(action),
                "reward": round(reward, 6),
                "done": done,
            },
            ts_of(),
        )
        executed += 1
        observation = outcome["observation"]
        if done:
            break

    return {
        "run_id": run_id,
        "steps": executed,
        "total_reward": round(total_reward, 6),
        "done": done,
    }


def evaluate_policy(
    *,
    make_env: Any,
    policy: Any,
    episodes: int,
    steps: int,
    seeds: Sequence[int] = (),
) -> Dict[str, Any]:
    """留出评测：每个 seed 造一个新环境，跑固定步数，取平均回报。"""
    if episodes <= 0:
        raise ValueError("episodes 必须是正整数")
    totals: List[float] = []
    for index in range(episodes):
        seed = seeds[index] if index < len(seeds) else index
        env = make_env(seed) if callable(make_env) else make_env
        observation = env.reset()
        total = 0.0
        for _ in range(steps):
            action = policy.act(observation)
            outcome = env.step(action)
            total += float(outcome.get("reward", 0.0))
            observation = outcome["observation"]
            if outcome.get("done"):
                break
        totals.append(total)
    return {
        "episodes": episodes,
        "steps": steps,
        "mean_return": round(sum(totals) / len(totals), 6),
        "best": round(max(totals), 6),
        "worst": round(min(totals), 6),
    }
