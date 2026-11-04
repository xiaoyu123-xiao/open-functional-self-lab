"""只追加的哈希链账本（audit ledger）。

为什么不是普通日志：S/AGENTS 要求"日志不可删除、可审计"，而普通 jsonl 可以
被改写后无痕。这里每条记录带前一条的 hash，改动任何一条都会在 verify() 处断链。

记录结构（每行一个 JSON 对象）：
    seq       1 起连续编号
    ts        UTC ISO 8601
    event     事件名，如 init / step / transition / budget / alert
    actor     agent / human / system
    payload   事件内容
    prev_hash 上一条的 hash（首条为 64 个 0）
    hash      本条（不含 hash 字段）的规范 JSON 的 sha256
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

GENESIS = "0" * 64


def canonical(obj: Any) -> str:
    """规范 JSON：键排序、无空格、不转义中文，保证哈希稳定。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class Ledger:
    """账本：append 只写不覆盖，verify 逐条校验。"""

    def __init__(self, path: "str | Path") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    # ---------- 写 ----------

    def append(
        self,
        event: str,
        payload: Dict[str, Any],
        ts: str,
        *,
        actor: str = "agent",
    ) -> Dict[str, Any]:
        if not event or not isinstance(event, str):
            raise ValueError("event 必须是非空字符串")
        last = self.last()
        seq = 1 if last is None else int(last["seq"]) + 1
        prev_hash = GENESIS if last is None else str(last["hash"])
        record: Dict[str, Any] = {
            "seq": seq,
            "ts": ts,
            "event": event,
            "actor": actor,
            "payload": payload,
            "prev_hash": prev_hash,
        }
        record["hash"] = self.digest(record)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical(record) + "\n")
        return record

    # ---------- 读 ----------

    def read(self) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def last(self) -> "Dict[str, Any] | None":
        last: "Dict[str, Any] | None" = None
        for record in self.read():
            last = record
        return last

    def events(self, name: "str | None" = None) -> List[Dict[str, Any]]:
        return [r for r in self.read() if name is None or r.get("event") == name]

    # ---------- 校验 ----------

    @staticmethod
    def digest(record: Dict[str, Any]) -> str:
        body = {k: v for k, v in record.items() if k != "hash"}
        return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()

    def verify(self) -> Tuple[bool, str]:
        records = self.read()
        prev = GENESIS
        for index, record in enumerate(records, start=1):
            if int(record.get("seq", -1)) != index:
                return False, f"第 {index} 条 seq 不连续：{record.get('seq')!r}"
            if record.get("prev_hash") != prev:
                return False, f"第 {index} 条 prev_hash 断链"
            if record.get("hash") != self.digest(record):
                return False, f"第 {index} 条内容被改写（hash 不匹配）"
            prev = str(record["hash"])
        return True, f"{len(records)} 条记录，哈希链完整"
