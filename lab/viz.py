"""仪表盘生成器：把状态、预算、最近事件渲染成一份静态 markdown。

原方案只有 viz/dashboard.md 的"显示项清单"，没有任何生成物，人还是得自己去翻日志。
这里直接产出 viz/status.md，可被 CI 或 cron 覆盖更新。
"""

from __future__ import annotations

from typing import Any, Dict, List

from .budget import WINDOWS, Budget
from .ledger import Ledger
from .state import TRANSITIONS, StateStore

RECENT_LIMIT = 8
DIFFICULTY_LABELS = {
    "INIT": "未初始化",
    "READY": "就绪",
    "RUNNING": "运行中",
    "REVIEWING": "评审中",
    "ROLLING_BACK": "回滚中",
    "FROZEN": "已冻结（需人工解冻）",
    "ARCHIVED": "已归档",
}


def _event_summary(record: Dict[str, Any]) -> str:
    payload = record.get("payload", {})
    if record.get("event") == "step":
        return (
            f"步 {payload.get('step')}：动作 {payload.get('action')}，"
            f"预测误差 {payload.get('prediction_error')}"
        )
    if record.get("event") == "budget":
        return f"{payload.get('kind')} +{payload.get('amount')}"
    if record.get("event") == "transition":
        return f"{payload.get('from')} → {payload.get('to')}（{payload.get('reason') or '无备注'}）"
    return ", ".join(f"{k}={v}" for k, v in list(payload.items())[:3]) or "—"


def _mermaid(store: StateStore) -> str:
    current = store.status()
    lines = ["```mermaid", "stateDiagram-v2", f"    [*] --> INIT"]
    for source, targets in TRANSITIONS.items():
        for target in sorted(targets):
            lines.append(f"    {source} --> {target}")
    lines.append(f"    note right of {current} : 当前状态")
    lines.append("```")
    return "\n".join(lines)


def render(store: StateStore, ledger: Ledger, budget: Budget, generated_at: str) -> str:
    data = store.load()
    current = str(data["status"])
    records = ledger.read()
    history: List[Dict[str, Any]] = data.get("history", [])
    rollbacks = sum(1 for step in history if step.get("to") == "ROLLING_BACK")
    alerts = [r for r in records if r.get("event") == "alert"]
    acked = sum(1 for r in records if r.get("event") == "ack")

    out: List[str] = []
    out.append("# 实验台仪表盘")
    out.append("")
    out.append("> 本文件由 `python -m lab.cli viz` 自动生成，请勿手改。")
    out.append(f"> 生成时间：`{generated_at}`　当前状态：**{current}**（{DIFFICULTY_LABELS[current]}）")
    out.append("")
    out.append("## 1. 概览")
    out.append("")
    out.append("| 指标 | 值 |")
    out.append("|---|---|")
    out.append(f"| 账本事件数 | {len(records)} |")
    out.append(f"| 状态转换次数 | {len(history)} |")
    out.append(f"| 回滚次数 | {rollbacks} |")
    out.append(f"| 告警数 / 已回应 | {len(alerts)} / {acked} |")
    steps = [r for r in records if r.get("event") == "step"]
    out.append(f"| 已执行步数 | {len(steps)} |")
    if steps:
        last = steps[-1]["payload"]
        out.append(f"| 最近一步预测误差 | {last.get('prediction_error')} |")
    out.append("")

    out.append("## 2. 预算")
    out.append("")
    out.append("| 类别 | 已用 | 上限 | 余量 | 窗口 |")
    out.append("|---|---|---|---|---|")
    for kind, row in budget.snapshot().items():
        out.append(
            f"| `{kind}` | {row['used']:g} | {row['cap']:g} | {row['remaining']:g} | {WINDOWS[kind]} |"
        )
    out.append("")

    out.append("## 3. 最近事件")
    out.append("")
    if records:
        out.append("| seq | 时间 | 事件 | 摘要 |")
        out.append("|---|---|---|---|")
        for record in records[-RECENT_LIMIT:]:
            out.append(
                f"| {record.get('seq')} | `{record.get('ts')}` | `{record.get('event')}` | "
                f"{_event_summary(record)} |"
            )
    else:
        out.append("_暂无事件，先执行 `python -m lab.cli init && python -m lab.cli run --steps 20`。_")
    out.append("")

    out.append("## 4. 状态机")
    out.append("")
    out.append(_mermaid(store))
    out.append("")
    return "\n".join(out)
