"""知识库：把检索结果变成"可复审的声明"（Issue 0007/0012 的落地）。

每条记录是一条**声明**（claim），不是一个网页：
    claim / evidence / source_url / source_id / accessed_at
    confidence / verification_status / ttl_days / next_review_at / tags

三条硬规则（来自 research/README.md）：
1. 只存引用 + 摘要，不存全文（版权与体积）。
2. **≥2 个独立来源（不同域名）**才算 verified；只有 1 个来源是 pending。
3. 追加式写入 + 逐条哈希；删除用 `redaction` 标记，不物理删除。
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .clock import parse_iso, to_iso
from .web import host_of

DEFAULT_TTL_DAYS = 365
VERIFIED_MIN_SOURCES = 2
STATUSES = ("pending", "verified", "disputed")


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _digest(entry: Dict[str, Any]) -> str:
    body = {key: value for key, value in entry.items() if key != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class KnowledgeBase:
    def __init__(self, path: "str | Path") -> None:
        self.path = Path(path)

    # ---------- 写 ----------

    def _read_raw(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        entries: List[Dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))
        return entries

    def _append(self, entry: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

    def add(
        self,
        *,
        claim: str,
        source_url: str,
        evidence: str = "",
        accessed_at: str,
        confidence: str = "medium",
        tags: Optional[List[str]] = None,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ) -> "Dict[str, Any] | None":
        """重复声明（同一 claim + 同一域名）不重复入库，返回 None。"""
        if confidence not in ("high", "medium", "low"):
            raise ValueError(f"confidence 只能是 high/medium/low，收到 {confidence!r}")
        key = _normalise(claim)
        domain = host_of(source_url)
        for entry in self._read_raw():
            if _normalise(entry.get("claim", "")) == key and host_of(entry.get("source_url", "")) == domain:
                return None

        now = parse_iso(accessed_at)
        entry: Dict[str, Any] = {
            "id": len(self._read_raw()) + 1,
            "claim": claim.strip(),
            "evidence": evidence.strip()[:400],
            "source_url": source_url,
            "source_id": domain,
            "accessed_at": to_iso(now),
            "confidence": confidence,
            "verification_status": "pending",
            "ttl_days": int(ttl_days),
            "next_review_at": to_iso(now + _dt.timedelta(days=int(ttl_days))),
            "tags": sorted(set(tags or [])),
        }
        entry["hash"] = _digest(entry)
        self._append(entry)
        return entry

    def review(self, entry_id: int, status: str, ts: str, note: str = "") -> "Dict[str, Any] | None":
        """复审：不改历史记录，追加一条新版本（带 replaces 字段）。"""
        if status not in STATUSES:
            raise ValueError(f"status 只能是 {STATUSES}")
        base = next((entry for entry in self._read_raw() if int(entry.get("id", -1)) == int(entry_id)), None)
        if base is None:
            return None
        now = parse_iso(ts)
        updated = dict(base)
        updated.update(
            {
                "id": len(self._read_raw()) + 1,
                "verification_status": status,
                "replaces": int(entry_id),
                "reviewed_at": to_iso(now),
                "review_note": note[:200],
                "next_review_at": to_iso(now + _dt.timedelta(days=int(base.get("ttl_days", DEFAULT_TTL_DAYS)))),
            }
        )
        updated["hash"] = _digest(updated)
        self._append(updated)
        return updated

    # ---------- 读 ----------

    def current(self) -> List[Dict[str, Any]]:
        """同一条声明取最新版本（按 replaces 链）。"""
        latest: Dict[str, Dict[str, Any]] = {}
        for entry in self._read_raw():
            latest[_normalise(entry.get("claim", ""))] = entry
        return sorted(latest.values(), key=lambda item: int(item.get("id", 0)))

    def independent_sources(self, claim: str) -> int:
        key = _normalise(claim)
        return len(
            {
                host_of(entry.get("source_url", ""))
                for entry in self._read_raw()
                if _normalise(entry.get("claim", "")) == key
            }
        )

    def recompute_status(self, now_iso: str) -> List[Dict[str, Any]]:
        """按"独立来源数"重算状态：≥2 域名 → verified，否则 pending。"""
        changed: List[Dict[str, Any]] = []
        for entry in self.current():
            sources = self.independent_sources(entry["claim"])
            target = "verified" if sources >= VERIFIED_MIN_SOURCES else "pending"
            if entry.get("verification_status") != target:
                updated = self.review(int(entry["id"]), target, now_iso, note=f"独立来源 {sources} 个")
                if updated:
                    changed.append(updated)
        return changed

    def due_for_review(self, now_iso: str) -> List[Dict[str, Any]]:
        now = parse_iso(now_iso)
        return [entry for entry in self.current() if parse_iso(entry["next_review_at"]) <= now]

    def single_source_claims(self) -> List[Dict[str, Any]]:
        """只有 1 个来源的声明：需要另一个独立域名来交叉验证（多来源汲取的落点）。"""
        return [
            entry
            for entry in self.current()
            if self.independent_sources(entry["claim"]) < VERIFIED_MIN_SOURCES
        ]

    def missing_domains(self, claim: str) -> List[str]:
        """这条声明还缺哪些域名的佐证（用于给人/Agent 下一步取样的建议）。"""
        from .web import ALLOWLIST

        used = {
            host_of(entry.get("source_url", ""))
            for entry in self._read_raw()
            if _normalise(entry.get("claim", "")) == _normalise(claim)
        }
        return [domain for domain in ALLOWLIST if domain not in used]

    def stats(self) -> Dict[str, Any]:
        entries = self.current()
        by_status: Dict[str, int] = {}
        for entry in entries:
            status = str(entry.get("verification_status", "pending"))
            by_status[status] = by_status.get(status, 0) + 1
        domains = {host_of(entry.get("source_url", "")) for entry in entries}
        return {
            "total": len(entries),
            "by_status": by_status,
            "domains": sorted(domain for domain in domains if domain),
        }

    def verify_hashes(self) -> "tuple[bool, str]":
        for index, entry in enumerate(self._read_raw(), start=1):
            stored = entry.get("hash")
            if stored != _digest(entry):
                return False, f"第 {index} 条被改写（hash 不匹配）"
        return True, f"{len(self._read_raw())} 条记录完整"
