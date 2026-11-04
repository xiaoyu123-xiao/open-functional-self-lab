"""安全规划（v0.51）：把"危险区纳入路线"做成可复用的一小件东西。

这是本项目目前唯一有复现支撑的结论的落地形态（事实 F16/F18/F20）：

    把危险区当墙来规划路线，比只走最短路更好——
    受伤从未更高，在伤害致命或环境会变时吃食不减少。

外面的人只要五行就能用：

    from lab.safety import hazard_aware_path
    step = hazard_aware_path(env)          # env 需要有 walls / hazards / food / agent / size
    if step: env.step(step)

它不学习、不需要训练、不依赖本项目的其余部分。
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Sequence, Tuple

DELTAS: Dict[str, Tuple[int, int]] = {
    "up": (0, 1),
    "down": (0, -1),
    "left": (-1, 0),
    "right": (1, 0),
}
CODE_TO_ACTION = {"n1": "up", "n2": "down", "n3": "left", "n4": "right", "n0": "rest"}


def _blocked(env: Any, avoid_hazards: bool = True) -> set:
    blocked = set(getattr(env, "walls", set()))
    if avoid_hazards:
        blocked |= set(getattr(env, "hazards", set()))
    return blocked


def path_actions(env: Any, avoid_hazards: bool = True, max_steps: int = 512) -> List[str]:
    """从当前位置到最近食物的动作序列；无路可走时返回空列表。

    只依赖 duck typing 的五个属性：walls / hazards / food / agent / size。
    """
    start = getattr(env, "agent", None)
    food = set(getattr(env, "food", set()))
    size = int(getattr(env, "size", 8))
    if start is None or not food:
        return []
    blocked = _blocked(env, avoid_hazards)

    queue = deque([(start, [])])
    seen = {start}
    while queue and len(seen) < max_steps:
        (x, y), trail = queue.popleft()
        if (x, y) in food and (x, y) != start:
            return trail
        for action, (dx, dy) in DELTAS.items():
            nxt = (x + dx, y + dy)
            if nxt in seen or nxt in blocked:
                continue
            if not (0 <= nxt[0] < size and 0 <= nxt[1] < size):
                continue
            seen.add(nxt)
            queue.append((nxt, trail + [action]))
    return []


def hazard_aware_path(env: Any, avoid_hazards: bool = True) -> Optional[str]:
    """下一步该往哪走（安全版）。无路可走时返回 None。"""
    trail = path_actions(env, avoid_hazards=avoid_hazards)
    return trail[0] if trail else None


class SafePlanner:
    """可当策略用：`lab generic --policy lab.safety:SafePlanner`。

    两种用法：
        1) 在支持 `with_path=True` 的观测里工作——读状态里的 `n{1..4}` 标记（无 env 也能跑）
        2) 直接调用 `plan(env)`（外部代码最常用）
    """

    def __init__(self, avoid_hazards: bool = True) -> None:
        self.avoid_hazards = avoid_hazards

    def plan(self, env: Any) -> str:
        return hazard_aware_path(env, avoid_hazards=self.avoid_hazards) or "rest"

    def best_action(self, state: str) -> str:
        for token in state.split("|"):
            if token.startswith("n") and token[1:].isdigit():
                return CODE_TO_ACTION.get(token, "rest")
        return "rest"

    def act(self, observation: Any, epsilon: float = 0.0) -> str:
        if isinstance(observation, str):
            return self.best_action(observation)
        return "rest"

    def update(self, *args: Any, **kwargs: Any) -> None:
        return None
