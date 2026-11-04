"""预算硬闸门。

原方案里 budget 只是一张表格（docs/budget.md），没有任何一行代码阻止超支。
这里把上限做成会抛异常的闸门：超了就是超了，不会"先跑完再说"。

口径：
- day   按 UTC 日期统计（ts 前 10 位）
- month 按 UTC 年月统计（ts 前 7 位）
- run   只统计当前 run_id
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .ledger import Ledger

DEFAULT_CAPS: Dict[str, float] = {
    "search_requests_per_day": 200.0,
    "gpu_hours_per_month": 10.0,
    "wall_clock_hours_per_run": 2.0,
    "steps_per_run": 1000.0,
    # v0.1.4 新增：原来只有"单次上限"，可以无限次 run，等于没有总量约束
    "steps_per_day": 5000.0,
}

WINDOWS: Dict[str, str] = {
    "search_requests_per_day": "day",
    "gpu_hours_per_month": "month",
    "wall_clock_hours_per_run": "run",
    "steps_per_run": "run",
    "steps_per_day": "day",
}


class BudgetExceeded(RuntimeError):
    """超预算：调用方必须停止，不允许 catch 后继续。"""


class Budget:
    def __init__(
        self,
        caps: Optional[Dict[str, float]],
        ledger: Ledger,
        ts: str,
        run_id: Optional[str] = None,
    ) -> None:
        self.caps: Dict[str, float] = dict(DEFAULT_CAPS)
        if caps:
            for key, value in caps.items():
                if key not in DEFAULT_CAPS:
                    raise KeyError(f"未知预算类别：{key!r}")
                self.caps[key] = float(value)
        self.ledger = ledger
        self.ts = ts
        self.run_id = run_id

    # ---------- 统计 ----------

    def _effective_run_id(self) -> "str | None":
        """没显式给 run_id 时（例如仪表盘/status），回落到账本里最近一次 run。

        修的是 v0.1.3 的一个显示错误：run 结束后所有 run 窗口都显示 0/1000，
        看板永远像"没花过钱"。
        """
        if self.run_id:
            return self.run_id
        for record in reversed(self.ledger.events("budget")):
            candidate = record.get("payload", {}).get("run_id")
            if candidate:
                return str(candidate)
        return None

    def used(self, kind: str) -> float:
        if kind not in self.caps:
            raise KeyError(f"未知预算类别：{kind!r}")
        window = WINDOWS[kind]
        run_scope = self._effective_run_id()
        total = 0.0
        for record in self.ledger.events("budget"):
            payload = record.get("payload", {})
            if payload.get("kind") != kind:
                continue
            ts = str(record.get("ts", ""))
            if window == "day" and ts[:10] != self.ts[:10]:
                continue
            if window == "month" and ts[:7] != self.ts[:7]:
                continue
            if window == "run" and run_scope is not None and payload.get("run_id") != run_scope:
                continue
            total += float(payload.get("amount", 0.0))
        return total

    def remaining(self, kind: str) -> float:
        return self.caps[kind] - self.used(kind)

    def check(self, kind: str, amount: float = 0.0) -> None:
        cap = self.caps[kind]
        used = self.used(kind)
        if used + float(amount) > cap:
            raise BudgetExceeded(
                f"{kind} 超限：已用 {used:g} + 本次 {float(amount):g} > 上限 {cap:g}"
                f"（窗口={WINDOWS[kind]}）。请先改 lab.config.json 并走审批矩阵。"
            )

    # ---------- 记账 ----------

    def charge(self, kind: str, amount: float) -> Dict[str, Any]:
        self.check(kind, amount)
        record = self.ledger.append(
            "budget",
            {"kind": kind, "amount": float(amount), "run_id": self.run_id},
            self.ts,
            actor="system",
        )
        return record

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        return {
            kind: {
                "used": round(self.used(kind), 3),
                "cap": round(self.caps[kind], 3),
                "remaining": round(self.remaining(kind), 3),
            }
            for kind in self.caps
        }
