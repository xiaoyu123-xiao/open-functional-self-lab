"""人与智能的协作层 + 行为涌现检测（v0.8）。

两件事：

1. **协作**：系统不再自作主张，而是**提出候选方案 + 理由 + 预期代价**，由人挑一个。
   人的选择被记录，并且影响下次的排序——这不是"迎合"，是"记住你的偏好"。
2. **涌现检测**：把"涌现"从形容词变成可计算的量。我们不声称它"有想法"，
   只统计**没有被奖励直接鼓励、但从规则交互里长出来的行为**：
       wall_bump（撞墙率）、hazard_entry（进毒区率）、rest_ratio（原地不动率）、
       food_camp（蹲在食物点不动）、action_entropy（动作多样性）、armor_blocked（靠甲硬扛）

   这些数字可以对比"训练前 / 训练后 / BFS 基线"。如果某个行为**训练后才出现、
   且没人奖励过它**，那就是这个项目里"涌现"的操作性定义。
"""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

PROPOSAL_LIBRARY: List[Dict[str, str]] = [
    {"id": "train", "title": "继续训练策略", "why": "留出分数还低于基线", "cost": "CPU 1–2 分钟"},
    {"id": "curriculum", "title": "提高难度再训", "why": "已在简单任务上饱和", "cost": "CPU 数分钟"},
    {"id": "armor", "title": "开启护甲（风险-收益权衡）", "why": "想观察它敢不敢冒险", "cost": "CPU 数分钟"},
    {"id": "learn", "title": "收新资料入库", "why": "知识库还少，影响不了决策", "cost": "离线 1 秒 / 在线扣预算"},
    {"id": "eval", "title": "只评测，不改任何东西", "why": "想先看清现状", "cost": "5 秒"},
    {"id": "ack", "title": "处理待回应告警", "why": "有告警没人回，通知系统在失效", "cost": "1 秒"},
]


def build_proposals(
    *,
    has_policy: bool,
    learned_score: Optional[float],
    baseline_score: Optional[float],
    knowledge_count: int,
    pending_alerts: int,
    preferences: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """按当前状态挑出候选方案，并按"人过去的偏好"排序（偏好只影响顺序，不删选项）。"""
    picks: List[Dict[str, Any]] = []
    by_id = {item["id"]: item for item in PROPOSAL_LIBRARY}

    if pending_alerts > 0:
        picks.append({**by_id["ack"], "reason": f"{pending_alerts} 条告警未回应"})
    if not has_policy or learned_score is None:
        picks.append({**by_id["train"], "reason": "还没有策略"})
    elif baseline_score is not None and learned_score < baseline_score:
        picks.append({**by_id["train"], "reason": f"留出 {learned_score:+.2f} < 基线 {baseline_score:+.2f}"})
    else:
        picks.append({**by_id["curriculum"], "reason": f"留出 {learned_score:+.2f} 已不低于基线"})
    if knowledge_count == 0:
        picks.append({**by_id["learn"], "reason": "知识库为空"})
    picks.append({**by_id["armor"], "reason": "观察风险偏好（甲够不够大胆去用）"})
    picks.append({**by_id["eval"], "reason": "不动任何东西，只测"})

    preferences = preferences or {}
    picks.sort(key=lambda item: -int(preferences.get(str(item["id"]), 0)))
    return picks[:3]


def record_choice(ledger: Any, ts: str, proposals: Sequence[Dict[str, Any]], chosen_id: str) -> Dict[str, Any]:
    return ledger.append(
        "collab",
        {"chosen": chosen_id, "options": [item["id"] for item in proposals]},
        ts,
        actor="human",
    )


# ---------------------------------------------------------------- 行为分析


def analyse(steps: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    """从账本 step 记录里算行为特征。没有记录时返回全 0。"""
    if not steps:
        return {
            "samples": 0,
            "wall_bump_rate": 0.0,
            "hazard_entry_rate": 0.0,
            "rest_ratio": 0.0,
            "food_camp_ratio": 0.0,
            "action_entropy": 0.0,
        }

    total = len(steps)
    bumps = sum(1 for step in steps if step.get("blocked"))
    hurts = sum(1 for step in steps if step.get("hurt"))
    rests = sum(1 for step in steps if step.get("action") == "rest")

    cells = [(int(step.get("x", 0)), int(step.get("y", 0))) for step in steps]
    camp = 0
    run = 1
    for index in range(1, len(cells)):
        if cells[index] == cells[index - 1]:
            run += 1
            if run >= 5:
                camp += 1
        else:
            run = 1

    counts = Counter(str(step.get("action")) for step in steps)
    entropy = -sum((count / total) * math.log2(count / total) for count in counts.values())

    return {
        "samples": total,
        "wall_bump_rate": round(bumps / total, 4),
        "hazard_entry_rate": round(hurts / total, 4),
        "rest_ratio": round(rests / total, 4),
        "food_camp_ratio": round(camp / total, 4),
        "action_entropy": round(entropy, 4),
    }


def emergent_gap(before: Dict[str, float], after: Dict[str, float]) -> List[str]:
    """哪些行为是"训练后新长出来的"（变化超过阈值）。这是本项目的涌现代理。"""
    notes: List[str] = []
    thresholds = {
        "wall_bump_rate": 0.05,
        "hazard_entry_rate": 0.05,
        "rest_ratio": 0.05,
        "food_camp_ratio": 0.02,
        "action_entropy": 0.30,
    }
    for key, threshold in thresholds.items():
        delta = float(after.get(key, 0.0)) - float(before.get(key, 0.0))
        if abs(delta) >= threshold:
            direction = "上升" if delta > 0 else "下降"
            notes.append(f"{key} {direction} {abs(delta):.3f}（{before.get(key):.3f} → {after.get(key):.3f}）")
    return notes
