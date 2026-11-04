"""已知事实库（v0.44）：记忆的第二层——"已经确定的量"。

为什么需要它（委托人原话）：
    "我叫你添加上下文强记忆，你不添加。现在出问题了吧？"

上一版只做了**规则**（`lessons.py`：什么不许做），没做**事实**（`facts`：已经测出什么）。
后果很具体：我反复不知道"BFS 在 ref-1 上已经吃满 30/30"，于是连续几轮去追一个
数学上追不到的目标。

规则回答"怎么做事"，事实回答"现在的世界是什么样"。两者都不许靠记性。

用法：
    lab facts                 # 列出全部事实
    lab facts --brief         # 只看最关键的几条（上下文丢了先跑这个）
    lab facts --check F1,F7   # 下结论前引用它依赖的事实
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence


@dataclass(frozen=True)
class Fact:
    fact_id: str
    statement: str
    value: str
    scope: str            # 在什么条件下成立
    evidence: str         # 复算命令或实验编号
    verified: str


FACTS: Sequence[Fact] = (
    Fact("F1", "每个评测回合最多吃到 5 份食物", "5 份/回合",
         "ref-1 系列（size=10, corridor, hazards=6）", "python -m lab.cli ref --repeats 12", "v0.43"),
    Fact("F2", "BFS 在 ref-1（非致命）上吃满上限", "30/30（5.0/回合）",
         "ref-1", "docs/experiments/0028-twenty-repeats.md", "v0.43"),
    Fact("F3", "BFS 在致命世界吃不满", "21/30（3.5/回合），受伤 8",
         "corridor, lethal=True", "CHANGELOG v0.43.0", "v0.43"),
    Fact("F4", "BFS 在碰即死世界吃得更少", "12/30（2.0/回合），受伤 5",
         "corridor, one_hit=True", "CHANGELOG v0.43.0", "v0.43"),
    Fact("F5", "线性学习器在 ref-1 上吃得少但受伤更少", "吃 7.8–13.1、伤 4.7–6.1",
         "ref-1，12–20 组", "docs/experiments/0028-twenty-repeats.md", "v0.42"),
    Fact("F6", "严格势能式塑形不改变行为", "12 组逐位相同",
         "ref-1，shaping=potential", "docs/experiments/0027-param-wiring-bug.md", "v0.41"),
    Fact("F7", "探索奖励的收益未证实", "12 组 +5.75 显著；20 组 +3.20 区间含 0",
         "ref-1", "docs/experiments/0028-twenty-repeats.md", "v0.42"),
    Fact("F8", "饿死不受罚曾使'不动'成为理性选择；补上后仍救不回来", "5.8 / 1.5 / 0.0（三世界吃食）",
         "corridor，starve_ends=True", "CHANGELOG v0.43.0", "v0.43"),
    Fact("F9", "神经策略'更差'是预算受限的结论，不是原理性否定", "−0.69 vs +0.60（120 回合/配置）",
         "v0.24 的测试条件", "docs/experiments/0012-neural-policy.md", "v0.24"),
    Fact("F15", "lab frontier 可按预算自动选策略", "预算0→规划器+护栏(2.17/0)；预算≥5→BFS(5.00/2.50)",
         "ref-1，6 seed，repeats=6", "python -m lab.cli frontier --budgets 0,5,10,15", "v0.47"),
    Fact("F13", "下一跳方向特征曾上下颠倒（v0.27–v0.45），已修", "修复后规划器行为与 BFS 一致（30/15）",
         "全任务族", "docs/experiments/0030-combined-frontier.md", "v0.46"),
    Fact("F14", "最优策略取决于受伤预算", "预算≤15 → BFS(30/15)；预算=0 → 安全规划(13/0)",
         "ref-1", "docs/experiments/0030-combined-frontier.md", "v0.46"),
    Fact("F11", "严格约束（吃≥4/5 且伤≤1/回合）对所有方法都不成立", "学习器 0/20；BFS 伤 15 > 6",
         "ref-1，20 组", "docs/experiments/0029-pareto-front.md", "v0.45"),
    Fact("F12", "学习器与 BFS 互不支配，各占 Pareto 一端", "学习器 11.4/5.6（吃/伤） vs BFS 30/15",
         "ref-1，20 组", "docs/experiments/0029-pareto-front.md", "v0.45"),
    Fact("F10", "ref-1 上唯一有 headroom 的轴是受伤次数", "BFS 2.5/回合 vs 学习器 1.0/回合",
         "ref-1", "CHANGELOG v0.43.0", "v0.43"),
)

BRIEF_IDS = ("F2", "F5", "F9", "F10")


def by_id(fact_id: str) -> Fact | None:
    return next((f for f in FACTS if f.fact_id == fact_id), None)


def check_citations(ids: Sequence[str]) -> List[str]:
    """下结论前调用：引用的事实必须存在且已核实。"""
    problems: List[str] = []
    for raw in ids:
        fact = by_id(raw.strip())
        if fact is None:
            problems.append(f"引用了不存在的事实：{raw}")
        elif not fact.verified:
            problems.append(f"事实 {raw} 尚未核实")
    return problems


def format_facts(only_brief: bool = False) -> str:
    chosen = [f for f in FACTS if (not only_brief or f.fact_id in BRIEF_IDS)]
    lines = [f"已知事实 {len(chosen)} 条（下结论前必须引用）：", ""]
    for fact in chosen:
        lines.append(f"{fact.fact_id}　{fact.statement}")
        lines.append(f"     值：{fact.value}")
        lines.append(f"     范围：{fact.scope}")
        lines.append(f"     证据：{fact.evidence}（{fact.verified}）")
    return "\n".join(lines)
