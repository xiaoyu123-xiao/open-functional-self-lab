"""周报生成器。

对应 viz/reports.md 的模板与 notify 的低优先级 digest：
从账本里统计最近 7×24h 的事件，不需要人工回忆"这周干了什么"。
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List

from .clock import parse_iso
from .ledger import Ledger

WINDOW_DAYS = 7


def _bucket(records: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for record in records:
        name = str(record.get("event", "unknown"))
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def render(ledger: Ledger, now_iso: str, title: str = "周报") -> str:
    now = parse_iso(now_iso)
    start = now - _dt.timedelta(days=WINDOW_DAYS)
    records = ledger.read()
    window: List[Dict[str, Any]] = []
    for record in records:
        try:
            ts = parse_iso(str(record.get("ts", "")))
        except ValueError:
            continue
        if start <= ts <= now:
            window.append(record)

    counts = _bucket(window)
    steps = counts.get("step", 0)
    transitions = counts.get("transition", 0)
    rollbacks = sum(
        1
        for r in window
        if r.get("event") == "transition" and r.get("payload", {}).get("to") == "ROLLING_BACK"
    )
    budget_total: Dict[str, float] = {}
    for record in window:
        if record.get("event") != "budget":
            continue
        payload = record.get("payload", {})
        kind = str(payload.get("kind"))
        budget_total[kind] = round(budget_total.get(kind, 0.0) + float(payload.get("amount", 0.0)), 3)
    alerts = counts.get("alert", 0)

    out: List[str] = []
    out.append(f"# {title}（{start.strftime('%Y-%m-%d')} → {now.strftime('%Y-%m-%d')}）")
    out.append("")
    out.append(f"> 由 `python -m lab.cli report` 自动生成；数据源 `state/ledger.jsonl`。")
    out.append("")
    out.append("## 本周进展")
    out.append("")
    out.append("| 项 | 数量 |")
    out.append("|---|---|")
    out.append(f"| 执行步数 | {steps} |")
    out.append(f"| 状态转换 | {transitions} |")
    out.append(f"| 回滚 | {rollbacks} |")
    out.append(f"| 告警 | {alerts} |")
    out.append(f"| 账本事件合计 | {len(window)} |")
    out.append("")
    out.append("## 预算消耗")
    out.append("")
    if budget_total:
        out.append("| 类别 | 用量 |")
        out.append("|---|---|")
        for kind, amount in sorted(budget_total.items()):
            out.append(f"| `{kind}` | {amount:g} |")
    else:
        out.append("_本周无消耗记录。_")
    out.append("")
    out.append("## 事件分布")
    out.append("")
    if counts:
        out.append("| 事件 | 次数 |")
        out.append("|---|---|")
        for name, count in counts.items():
            out.append(f"| `{name}` | {count} |")
    else:
        out.append("_本周无事件。_")
    out.append("")
    out.append("## 风险与待办")
    out.append("")
    risks: List[str] = []
    if rollbacks:
        risks.append(f"- 本周发生 {rollbacks} 次回滚，需要复核触发指标（见 logic/README.md 状态机）。")
    if alerts:
        risks.append(f"- 有 {alerts} 条告警，请确认是否已 `/ack`（见 notify/README.md）。")
    if not risks:
        risks.append("- 无异常。")
    out.extend(risks)
    out.append("")
    out.append("## 写下你的部分")
    out.append("")
    out.append("- 人学到了什么：")
    out.append("- 系统改进/退步了什么：")
    out.append("- 下周计划（对应 issues/ 中任务编号）：")
    out.append("")
    return "\n".join(out)
