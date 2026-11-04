"""持久层：SQLite（标准库，零新依赖）。

为什么加：JSONL 适合审计（只追加、可哈希），但**不适合长期查询与备份**。
真正要"信息不消失"，需要能跨年查询、能热备份、能迁到云数据库的东西。

设计原则：
1. 不替换 JSONL——它是**事实来源**；SQLite 是**索引与备份层**，可随时重建。
2. 同步是幂等的：按 `seq` 去重，重复 sync 不会产生重复行。
3. 用标准库 `sqlite3`，同一条代码路径既能本地跑，也能换成 Postgres（换连接层即可）。
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq        INTEGER PRIMARY KEY,
    ts         TEXT NOT NULL,
    event      TEXT NOT NULL,
    actor      TEXT,
    payload    TEXT,
    prev_hash  TEXT,
    hash       TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_event ON events(event);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);

CREATE TABLE IF NOT EXISTS kv (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class SqliteStore:
    def __init__(self, path: "str | Path") -> None:
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.path))
        try:
            connection.execute("PRAGMA journal_mode=WAL")      # 崩溃后可恢复
            connection.execute("PRAGMA synchronous=NORMAL")
            yield connection
            connection.commit()
        finally:
            connection.close()

    def init(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    # ---------- 同步 ----------

    def sync_ledger(self, ledger: Any) -> Dict[str, int]:
        """把 JSONL 账本镜像进来。幂等：按 seq 主键覆盖。"""
        self.init()
        records = ledger.read()
        inserted = 0
        with self.connect() as connection:
            for record in records:
                payload = json.dumps(record.get("payload", {}), ensure_ascii=False, sort_keys=True)
                cursor = connection.execute(
                    "INSERT OR IGNORE INTO events(seq, ts, event, actor, payload, prev_hash, hash) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        int(record["seq"]),
                        record.get("ts", ""),
                        record.get("event", ""),
                        record.get("actor", ""),
                        payload,
                        record.get("prev_hash", ""),
                        record.get("hash", ""),
                    ),
                )
                inserted += cursor.rowcount if cursor.rowcount > 0 else 0
        return {"ledger_records": len(records), "inserted": inserted}

    def put(self, key: str, value: Any, ts: str) -> None:
        self.init()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO kv(key, value, updated_at) VALUES (?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, json.dumps(value, ensure_ascii=False, sort_keys=True), ts),
            )

    def get(self, key: str) -> Optional[Any]:
        self.init()
        with self.connect() as connection:
            row = connection.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def sync_state(self, ctx: Any, ts: str) -> Dict[str, int]:
        """把状态、自我模型、知识库指针都存一份（可重建，不替代源文件）。"""
        self.init()
        written = 0
        for name, loader in (
            ("state.json", lambda: ctx.store.load()),
            ("self.json", lambda: ctx.self_model().load() if ctx.self_model().exists() else None),
            ("knowledge", lambda: ctx.knowledge().stats()),
        ):
            try:
                value = loader()
            except Exception:
                value = None
            if value is not None:
                self.put(name, value, ts)
                written += 1
        return {"snapshots": written}

    # ---------- 运维 ----------

    def stats(self) -> Dict[str, Any]:
        self.init()
        with self.connect() as connection:
            events = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            kv_rows = connection.execute("SELECT COUNT(*) FROM kv").fetchone()[0]
            first = connection.execute("SELECT MIN(ts) FROM events").fetchone()[0]
            last = connection.execute("SELECT MAX(ts) FROM events").fetchone()[0]
        size = self.path.stat().st_size if self.path.exists() else 0
        return {
            "path": str(self.path),
            "events": events,
            "kv_rows": kv_rows,
            "first_ts": first,
            "last_ts": last,
            "size_kb": round(size / 1024, 1),
        }

    def backup(self, destination: "str | Path") -> str:
        """热备份（SQLite 在线备份 API），不需要停机。"""
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.init()
        with self.connect() as source:
            dest = sqlite3.connect(str(target))
            try:
                source.backup(dest)
            finally:
                dest.close()      # Windows 上不显式 close 会锁住文件，临时目录删不掉
        return str(target)
