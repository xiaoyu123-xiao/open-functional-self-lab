"""权限申请 / 批准（人机协作里的"要权限"环节）。

核心想法（来自用户）：**它不该被写死"访问不了"，而应该能开口要；批不批在人。**

流程：
    ask   → 人在终端看到请求（资源、理由、时间）
    grant → 人批准，写明"批准范围"（例如只读、一次性、限某域名）
    deny  → 人拒绝，理由写进账本
    check → 代码在真正访问前调用它；没有批准就不许动

三条底线（不是谨慎，是可验证性）：
1. 每次申请/批准/拒绝都进账本，事后可审计。
2. 批准有效期可设（默认 24 小时），过期自动失效——避免"一次批准，永久通行"。
3. **真实凭证本身不进系统**：批准的是"这个能力可以做"，不是"把私钥交出来"。
"""

from __future__ import annotations

import json
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .clock import parse_iso, to_iso

DEFAULT_TTL_HOURS = 24
DEFAULT_AUTONOMY_DAYS = 90
LEVELS = ("locked", "supervised", "full")


class Permissions:
    def __init__(self, path: "str | Path") -> None:
        self.path = Path(path)

    # ---------- 存取 ----------

    def level(self) -> str:
        """当前自主级别：locked / supervised / full。"""
        data = self._load()
        return str(data.get("level", "supervised"))

    def set_level(self, ledger: Any, ts: str, level: str, by: str, capabilities: List[str], days: int) -> Dict[str, Any]:
        """一次性授权：给一个长期"标准授权"，而不是逐条批。"""
        if level not in LEVELS:
            raise ValueError(f"level 只能是 {LEVELS}")
        data = self._load()
        data["level"] = level
        granted: List[Dict[str, Any]] = []
        if level == "full":
            expires = to_iso(parse_iso(ts) + timedelta(days=int(days)))
            data["grants"] = [g for g in data["grants"] if g.get("scope") != "standing"]
            for capability in capabilities:
                grant = {
                    "request_id": "standing",
                    "resource": capability,
                    "scope": "standing",
                    "by": by,
                    "granted_at": ts,
                    "expires_at": expires,
                }
                data["grants"].append(grant)
                granted.append(grant)
        self._save(data)
        ledger.append(
            "autonomy",
            {"level": level, "by": by, "capabilities": capabilities if level == "full" else [], "days": int(days)},
            ts,
            actor=f"human:{by}",
        )
        return {"level": level, "granted": granted}

    def revoke_all(self, ledger: Any, ts: str, by: str) -> int:
        """一键收回所有标准授权，并降回 supervised。"""
        data = self._load()
        before = len(data["grants"])
        data["grants"] = []
        data["level"] = "supervised"
        self._save(data)
        ledger.append("autonomy", {"level": "supervised", "by": by, "revoked": before}, ts, actor=f"human:{by}")
        return before

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"requests": [], "grants": []}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data.setdefault("requests", [])
        data.setdefault("grants", [])
        return data

    def _save(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # ---------- 申请 ----------

    def request(self, ledger: Any, ts: str, resource: str, reason: str) -> Dict[str, Any]:
        data = self._load()
        request_id = "req-" + secrets.token_hex(3)
        entry = {"id": request_id, "resource": resource, "reason": reason, "status": "pending", "asked_at": ts}
        data["requests"].append(entry)
        self._save(data)
        ledger.append("perm_request", entry, ts, actor="agent")
        return entry

    # ---------- 批准 / 拒绝 ----------

    def grant(self, ledger: Any, ts: str, request_id: str, scope: str, by: str, ttl_hours: int = DEFAULT_TTL_HOURS) -> Dict[str, Any]:
        data = self._load()
        target = next((item for item in data["requests"] if item["id"] == request_id), None)
        if target is None:
            raise KeyError(f"没有这个申请：{request_id}")
        if target["status"] != "pending":
            raise ValueError(f"这条申请已经是 {target['status']}，不能重复处理")
        expires = to_iso(parse_iso(ts) + timedelta(hours=int(ttl_hours)))
        grant = {
            "request_id": request_id,
            "resource": target["resource"],
            "scope": scope,
            "by": by,
            "granted_at": ts,
            "expires_at": expires,
        }
        target["status"] = "granted"
        data["grants"].append(grant)
        self._save(data)
        ledger.append("perm_grant", grant, ts, actor=f"human:{by}")
        return grant

    def deny(self, ledger: Any, ts: str, request_id: str, by: str, reason: str = "") -> Dict[str, Any]:
        data = self._load()
        target = next((item for item in data["requests"] if item["id"] == request_id), None)
        if target is None:
            raise KeyError(f"没有这个申请：{request_id}")
        target["status"] = "denied"
        record = {"request_id": request_id, "resource": target["resource"], "by": by, "reason": reason}
        self._save(data)
        ledger.append("perm_deny", record, ts, actor=f"human:{by}")
        return record

    # ---------- 检查 ----------

    def check(self, resource: str, now: str, scope: Optional[str] = None) -> bool:
        data = self._load()
        moment = parse_iso(now)
        for grant in data["grants"]:
            if grant["resource"] != resource and grant["resource"] != "*":
                continue
            # standing 授权覆盖任意 scope；逐条授权要求 scope 对得上
            if scope is not None and grant.get("scope") not in ("standing", scope):
                continue
            if parse_iso(grant["expires_at"]) < moment:
                continue
            return True
        return False

    def pending(self) -> List[Dict[str, Any]]:
        return [item for item in self._load()["requests"] if item.get("status") == "pending"]

    def describe(self, now: str) -> str:
        data = self._load()
        lines = [f"自主级别：{self.level()}（locked=只本地 / supervised=逐条批 / full=标准授权）"]
        lines.append(f"申请 {len(data['requests'])} 条，其中待批 {len(self.pending())} 条；已批准 {len(data['grants'])} 条")
        for item in data["requests"]:
            if item.get("status") == "pending":
                lines.append(f"  待批 {item['id']}：{item['resource']}（{item['reason']}）")
        for grant in data["grants"]:
            alive = parse_iso(grant["expires_at"]) >= parse_iso(now)
            lines.append(
                f"  已批 {grant['resource']}（{grant['scope']}，{grant['by']}，{'有效' if alive else '已过期'}，到期 {grant['expires_at']}）"
            )
        return "\n".join(lines)
