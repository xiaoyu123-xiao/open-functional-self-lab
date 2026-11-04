"""通知机制（Issue 0019）。

要解决的不是"发一条消息"，而是三个会真正坑人的问题（对应 notify/README.md）：

1. **谁来判定"值得提示"** → 规则判定，不是模型自己说"我有重大发现"。
2. **重复提示怎么办** → 同一 `(kind, dedupe_key)` 24 小时内只发一次；状态变化才再发。
3. **一直没人回应怎么办** → 记回应率；低于 50% 自动发一条"你的告警可能在失效"。

设计取舍：**不联网**。渠道只有终端 + 账本 + `state/notify.jsonl`。
webhook / 邮件属于以后的事（要保持"默认离线"这条承诺，见 SECURITY.md 第 3 节）。
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .clock import parse_iso
from .ledger import Ledger

LEVELS = ("high", "medium", "low")
LEVEL_LABELS = {"high": "高", "medium": "中", "low": "低"}
DEDUPE_HOURS = 24
RESPONSE_WINDOW_DAYS = 7
RESPONSE_RATE_THRESHOLD = 0.5
MIN_SAMPLE = 3          # 少于 3 条告警时不评判回应率：一条没回就报"告警失效"是噪音
ACK_ACTIONS = ("pause", "rollback", "freeze", "continue", "unfreeze", "ignore")


class Notifier:
    def __init__(self, ledger: Ledger, clock: Any, state_dir: Path, echo: bool = True) -> None:
        self.ledger = ledger
        self.clock = clock
        self.state_dir = Path(state_dir)
        self.echo = echo

    # ---------- 读 ----------

    def _alerts(self) -> List[Dict[str, Any]]:
        return [record for record in self.ledger.read() if record.get("event") == "alert"]

    def _acked_seqs(self) -> "set[int]":
        return {
            int(record.get("payload", {}).get("target_seq", -1))
            for record in self.ledger.read()
            if record.get("event") == "ack"
        }

    def _recent_same(self, kind: str, dedupe_key: str, ts: str) -> "Dict[str, Any] | None":
        now = parse_iso(ts)
        for record in reversed(self._alerts()):
            payload = record.get("payload", {})
            if payload.get("kind") != kind or payload.get("dedupe_key") != dedupe_key:
                continue
            try:
                then = parse_iso(str(record.get("ts", "")))
            except ValueError:
                continue
            if (now - then) < _dt.timedelta(hours=DEDUPE_HOURS):
                return record
        return None

    # ---------- 发 ----------

    def emit(
        self,
        level: str,
        kind: str,
        message: str,
        *,
        dedupe_key: str = "",
        needs_action: bool = True,
    ) -> "Dict[str, Any] | None":
        if level not in LEVELS:
            raise ValueError(f"未知级别：{level!r}（合法值：{', '.join(LEVELS)}）")
        ts = self.clock.now_iso()

        if dedupe_key:
            duplicate = self._recent_same(kind, dedupe_key, ts)
            if duplicate is not None:
                return None

        record = self.ledger.append(
            "alert",
            {
                "level": level,
                "kind": kind,
                "message": message,
                "dedupe_key": dedupe_key,
                "needs_action": needs_action,
            },
            ts,
        )
        self._append_channel_file(record)
        if self.echo:
            self._print(record)
        return record

    def _append_channel_file(self, record: Dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        line = {
            "seq": record["seq"],
            "ts": record["ts"],
            "level": record["payload"]["level"],
            "kind": record["payload"]["kind"],
            "message": record["payload"]["message"],
            "needs_action": record["payload"]["needs_action"],
        }
        with (self.state_dir / "notify.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")

    def _print(self, record: Dict[str, Any]) -> None:
        payload = record["payload"]
        label = LEVEL_LABELS[payload["level"]]
        print(f"[{label}] #{record['seq']} {payload['kind']}：{payload['message']}")
        if payload["needs_action"]:
            print(f"      需要回应：python -m lab.cli ack {record['seq']} --action pause")

    # ---------- 回应 ----------

    def ack(self, target_seq: int, action: str, by: str = "human", note: str = "") -> Dict[str, Any]:
        if action not in ACK_ACTIONS:
            raise ValueError(f"未知动作：{action!r}（合法值：{', '.join(ACK_ACTIONS)}）")
        alerts = {int(record["seq"]): record for record in self._alerts()}
        if int(target_seq) not in alerts:
            raise KeyError(f"没有编号为 #{target_seq} 的告警")
        record = self.ledger.append(
            "ack",
            {"target_seq": int(target_seq), "action": action, "by": by, "note": note},
            self.clock.now_iso(),
            actor=f"human:{by}",
        )
        if self.echo:
            print(f"已回应 #{target_seq}：{action}" + (f"（{note}）" if note else ""))
        return record

    # ---------- 统计 ----------

    def pending(self) -> List[Dict[str, Any]]:
        acked = self._acked_seqs()
        return [
            record
            for record in self._alerts()
            if record["payload"].get("needs_action") and int(record["seq"]) not in acked
        ]

    def _window_counts(self) -> "tuple[int, int]":
        """最近 N 天里（需要回应的告警数, 其中已回应的数量）。"""
        now = parse_iso(self.clock.now_iso())
        start = now - _dt.timedelta(days=RESPONSE_WINDOW_DAYS)
        acked = self._acked_seqs()
        total = 0
        acked_count = 0
        for record in self._alerts():
            if not record["payload"].get("needs_action"):
                continue
            if record["payload"].get("kind") == "notify-health":
                continue      # 健康提醒不参与自身分母，否则会自我放大（越提醒越低）
            try:
                ts = parse_iso(str(record.get("ts", "")))
            except ValueError:
                continue
            if not (start <= ts <= now):
                continue
            total += 1
            if int(record["seq"]) in acked:
                acked_count += 1
        return total, acked_count

    def response_rate(self) -> float:
        """最近 N 天需要回应的告警里，被回应过的比例。没有告警时返回 1.0。"""
        total, acked_count = self._window_counts()
        if total == 0:
            return 1.0
        return round(acked_count / total, 4)

    def digest(self) -> str:
        pending = self.pending()
        lines = ["# 未回应的告警", ""]
        lines.append(f"> 回应率（最近 {RESPONSE_WINDOW_DAYS} 天）：{self.response_rate()*100:.0f}%"
                     f"　阈值 {RESPONSE_RATE_THRESHOLD*100:.0f}%")
        lines.append("")
        if not pending:
            lines.append("_没有待回应的告警。_")
            return "\n".join(lines) + "\n"
        lines.append("| 编号 | 时间 | 级别 | 类型 | 内容 |")
        lines.append("|---|---|---|---|---|")
        for record in pending:
            payload = record["payload"]
            lines.append(
                f"| #{record['seq']} | `{record['ts']}` | {LEVEL_LABELS.get(payload['level'], payload['level'])} "
                f"| `{payload['kind']}` | {payload['message']} |"
            )
        lines.append("")
        lines.append("回应一条：`python -m lab.cli ack <编号> --action pause|freeze|continue|ignore`")
        return "\n".join(lines) + "\n"

    def check_health(self) -> "Dict[str, Any] | None":
        """回应率过低时，发一条"通知系统自身可能失效"的提醒（带 24h 去重）。"""
        total, _ = self._window_counts()
        if total < MIN_SAMPLE:
            return None          # 样本太小，不下结论
        rate = self.response_rate()
        if rate >= RESPONSE_RATE_THRESHOLD:
            return None
        return self.emit(
            "medium",
            "notify-health",
            f"最近告警回应率只有 {rate*100:.0f}%（阈值 {RESPONSE_RATE_THRESHOLD*100:.0f}%）："
            "要么告警太多，要么没人看——建议复核通知策略",
            dedupe_key="notify-health",
            needs_action=False,      # 健康提醒本身不需要"回应"：它只是提示，否则会自我放大
        )
