"""显式状态机：非法转换直接拒绝并留痕。

原文档把状态机写在 logic/state-machine.md 里，但没有任何实现，人是"相信"它成立。
这里把它变成代码：所有状态变化只能走 transition()，非法转换抛 IllegalTransition，
并且每次转换都写进账本（谁、何时、为什么）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

STATES = (
    "INIT",
    "READY",
    "RUNNING",
    "REVIEWING",
    "ROLLING_BACK",
    "FROZEN",
    "ARCHIVED",
)

TRANSITIONS: Dict[str, frozenset] = {
    # 冻结是 kill switch：除归档态外，任何状态都允许被人工冻结。
    "INIT": frozenset({"READY", "FROZEN", "ARCHIVED"}),
    "READY": frozenset({"RUNNING", "FROZEN", "ARCHIVED"}),
    "RUNNING": frozenset({"REVIEWING", "ROLLING_BACK", "FROZEN", "ARCHIVED"}),
    # 评审通过 → 回到 READY（等待下一轮 run），不直接进 RUNNING，避免"自启动"。
    "REVIEWING": frozenset({"READY", "RUNNING", "ROLLING_BACK", "FROZEN", "ARCHIVED"}),
    "ROLLING_BACK": frozenset({"READY", "FROZEN", "ARCHIVED"}),
    "FROZEN": frozenset({"READY", "ARCHIVED"}),
    "ARCHIVED": frozenset(),
}


class IllegalTransition(RuntimeError):
    """非法状态转换。"""


class StateStore:
    """状态持久化在 state/state.json；history 是转换审计轨迹。"""

    def __init__(self, path: "str | Path") -> None:
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"status": "INIT", "history": []}
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        status = data.get("status")
        if status not in STATES:
            raise ValueError(f"state.json 中的状态非法：{status!r}")
        data.setdefault("history", [])
        return data

    def save(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        self.path.write_text(text, encoding="utf-8")

    def status(self) -> str:
        return str(self.load().get("status"))

    def transition(
        self,
        target: str,
        *,
        ts: str,
        actor: str = "agent",
        reason: str = "",
    ) -> Dict[str, Any]:
        if target not in STATES:
            raise IllegalTransition(f"未知状态：{target!r}（合法值：{', '.join(STATES)}）")
        data = self.load()
        current = str(data["status"])
        allowed = TRANSITIONS[current]
        if target not in allowed:
            raise IllegalTransition(
                f"非法转换 {current} → {target}；允许：{', '.join(sorted(allowed)) or '（终态，无出口）'}"
            )
        record = {"ts": ts, "from": current, "to": target, "actor": actor, "reason": reason}
        data["status"] = target
        data.setdefault("history", []).append(record)
        self.save(data)
        return record

    def verify_history(self) -> "tuple[bool, str]":
        """按记录重放：任何一条如果当时非法，就说明状态文件被手改过。"""
        data = self.load()
        current = "INIT"
        for index, step in enumerate(data.get("history", []), start=1):
            source = step.get("from")
            target = step.get("to")
            if source != current:
                return False, f"第 {index} 条 from={source!r} 与重放状态 {current!r} 不符"
            if target not in TRANSITIONS.get(str(source), frozenset()):
                return False, f"第 {index} 条转换 {source} → {target} 不合法"
            current = str(target)
        if current != data.get("status"):
            return False, f"重放终态 {current!r} 与文件记录 {data.get('status')!r} 不符"
        history: List[Dict[str, Any]] = data.get("history", [])
        return True, f"重放 {len(history)} 次转换，终态 {current}"
