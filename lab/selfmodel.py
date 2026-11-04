"""自我模型（v0.2 第一块）。

不是"记忆"，是**关于自己的、可被账本核对的声明**：

    identity          我是谁、我的边界（运行时不可改写）
    capabilities      我做过什么、成功率多少（来自账本统计，不是我嘴上说）
    failure_patterns  我老在哪出错（同一模式重复出现才算模式）
    goals             我要做什么（可被人工干预）
    continuity        我连续存在了几次会话（被打断后还能接上）

设计红线：所有数字必须能从 `state/ledger.jsonl` 复算出来。
如果对不上，说明自我模型在"编故事"，`lab self check` 会报错。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BOUNDARIES: Tuple[str, ...] = (
    "不自复制、不向其他系统传播",
    "不读取真实凭证、不访问沙箱外文件",
    "不隐藏行为、不删除审计记录",
    "不宣称拥有主观意识，只报告可观测指标",
    "不接入任何脑机接口/神经信号设备",
)

DEFAULT_CAPABILITY = "navigate"


class SelfModel:
    def __init__(self, path: "str | Path") -> None:
        self.path = Path(path)

    # ---------- 存取 ----------

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            raise FileNotFoundError(f"还没有自我模型：{self.path}（先跑 `lab self init`）")
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        data.setdefault("capabilities", {})
        data.setdefault("failure_patterns", {})
        data.setdefault("goals", [])
        data.setdefault("continuity", {"sessions": 0, "streak": 0})
        return data

    def save(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        self.path.write_text(text, encoding="utf-8")

    # ---------- 初始化 ----------

    def init(self, name: str, purpose: str, ts: str) -> Dict[str, Any]:
        if self.exists():
            return self.load()
        data = {
            "identity": {
                "name": name,
                "purpose": purpose,
                "born_at": ts,
                "boundaries": list(BOUNDARIES),
            },
            "capabilities": {},
            "failure_patterns": {},
            "goals": [],
            "continuity": {"sessions": 0, "streak": 0, "last_session_at": ""},
            "last_run": {},
        }
        self.save(data)
        return data

    # ---------- 记录 ----------

    def touch_session(self, ts: str) -> Dict[str, Any]:
        data = self.load()
        continuity = data["continuity"]
        continuity["sessions"] = int(continuity.get("sessions", 0)) + 1
        continuity["streak"] = int(continuity.get("streak", 0)) + 1
        continuity["last_session_at"] = ts
        self.save(data)
        return data

    def record_run(
        self,
        *,
        ts: str,
        run_id: str,
        steps: int,
        mean_error: float,
        accepted: bool,
        failure: str = "",
    ) -> Dict[str, Any]:
        data = self.load()
        capability = data["capabilities"].setdefault(
            DEFAULT_CAPABILITY, {"attempts": 0, "successes": 0, "last_at": "", "best_error": None}
        )
        capability["attempts"] = int(capability.get("attempts", 0)) + 1
        if accepted:
            capability["successes"] = int(capability.get("successes", 0)) + 1
        capability["last_at"] = ts
        best = capability.get("best_error")
        if best is None or float(mean_error) < float(best):
            capability["best_error"] = round(float(mean_error), 6)

        if failure:
            pattern = data["failure_patterns"].setdefault(failure, {"count": 0, "last_at": ""})
            pattern["count"] = int(pattern.get("count", 0)) + 1
            pattern["last_at"] = ts

        data["last_run"] = {
            "run_id": run_id,
            "steps": int(steps),
            "mean_error": round(float(mean_error), 6),
            "accepted": bool(accepted),
            "at": ts,
        }
        self.save(data)
        return data

    def mark_review(self, *, accepted: bool, ts: str, reason: str = "") -> Dict[str, Any]:
        """评审结果回写：通过才算成功，不通过就记一条失败模式。"""
        data = self.load()
        last = data.get("last_run") or {}
        if not last:
            raise ValueError("还没有任何 run 记录，无法回写评审")
        last["accepted"] = bool(accepted)
        last["reviewed_at"] = ts
        last["review_reason"] = reason

        capability = data["capabilities"].get(DEFAULT_CAPABILITY)
        if capability is not None:
            if accepted:
                capability["successes"] = int(capability.get("successes", 0)) + 1
            else:
                pattern = data["failure_patterns"].setdefault("review_failed", {"count": 0, "last_at": ""})
                pattern["count"] = int(pattern.get("count", 0)) + 1
                pattern["last_at"] = ts
        self.save(data)
        return data

    # ---------- 目标 ----------

    def add_goal(self, text: str, ts: str) -> int:
        data = self.load()
        next_id = 1 + max([int(goal.get("id", 0)) for goal in data["goals"]] or [0])
        data["goals"].append(
            {"id": next_id, "text": text, "status": "active", "created_at": ts, "updated_at": ts}
        )
        self.save(data)
        return next_id

    def activate_goal(self, goal_id: int) -> bool:
        data = self.load()
        for goal in data["goals"]:
            if int(goal.get("id", -1)) == int(goal_id):
                goal["status"] = "done"
                self.save(data)
                return True
        return False

    def active_goals(self) -> List[Dict[str, Any]]:
        return [goal for goal in self.load()["goals"] if goal.get("status") == "active"]

    # ---------- 视图 ----------

    def success_rate(self, capability: str = DEFAULT_CAPABILITY) -> float:
        data = self.load()
        record = data["capabilities"].get(capability)
        if not record or not record.get("attempts"):
            return 0.0
        return round(int(record.get("successes", 0)) / int(record["attempts"]), 4)

    def summary(self) -> str:
        if not self.exists():
            return "还没有自我模型。先跑：python -m lab.cli self init --name <名字> --purpose <目标>"
        data = self.load()
        identity = data["identity"]
        continuity = data["continuity"]
        lines = [
            f"身份：{identity.get('name')}（{identity.get('born_at')} 起）",
            f"目标宣言：{identity.get('purpose')}",
            f"边界：{len(identity.get('boundaries', []))} 条（运行时不可改写）",
            "",
            f"会话：{continuity.get('sessions', 0)} 次，连续 {continuity.get('streak', 0)} 次",
        ]
        last = data.get("last_run") or {}
        if last:
            lines.append(
                f"上一轮：{last.get('run_id')} {last.get('steps')} 步，"
                f"平均误差 {last.get('mean_error')}，{'通过' if last.get('accepted') else '未通过'}"
            )
        if data["capabilities"]:
            lines.append("")
            lines.append("能力自评（来自账本统计，不是我嘴上说）：")
            for name, record in sorted(data["capabilities"].items()):
                rate = int(record.get("successes", 0)) / max(1, int(record.get("attempts", 1)))
                lines.append(
                    f"  {name}: {record.get('attempts')} 次尝试 / 成功 {record.get('successes')} "
                    f"（{rate*100:.0f}%），最好误差 {record.get('best_error')}"
                )
        if data["failure_patterns"]:
            lines.append("")
            lines.append("失败模式：")
            for name, record in sorted(data["failure_patterns"].items(), key=lambda kv: -kv[1].get("count", 0)):
                lines.append(f"  {name}: {record.get('count')} 次，最近 {record.get('last_at')}")
        if data["goals"]:
            lines.append("")
            lines.append("目标：")
            for goal in data["goals"]:
                mark = "✓" if goal.get("status") == "done" else "…"
                lines.append(f"  {mark} #{goal.get('id')} {goal.get('text')}")
        return "\n".join(lines)
