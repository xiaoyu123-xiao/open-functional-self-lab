"""教训库：把"犯过的错"变成会拦人的检查（v0.39）。

为什么需要它（委托人原话）：
    "上下文记忆呢？好多以前犯过的错一直在犯。"

问题不在"没记录"——26 篇实验都记了；问题在**记录不会拦人**。
所以这里把教训结构化，并提供 `check_experiment()`：跑完实验、写结论之前调用它，
违反任何一条就返回违规清单，调用方应当拒绝下结论。

设计原则（跟本仓库其他部分一致）：
1. 每条教训必须**指向一处执行位置**（测试或脚本），否则视为"没有牙齿"，由测试检查出来。
2. 检查是**机械的**：只看数值/参数，不看措辞。
3. 教训只增不改：修订时新增一条，并写明它取代了哪一条。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class Lesson:
    lesson_id: str
    rule: str
    why: str
    enforcement: str          # "test:<名字>" 或 "script:<路径>" 或 "doc:<路径>"
    learned_at: str


LESSONS: Sequence[Lesson] = (
    Lesson("L01", "一次运行不算结论：至少 10 组重复并给出 95% 区间",
           "v0.16 的 1.15 倍、v0.30 的拐点、v0.31 的显著性，全部被加重复推翻",
           "script:scripts/precheck_experiment.py", "v0.16"),
    Lesson("L02", "奖励一改，旧分数作废；主指标改用吃到份数/受伤次数/存活步数",
           "v0.24 存活奖励让所有策略分数普涨，能力没变",
           "test:test_shaping_does_not_change_behavior_metric", "v0.26"),
    Lesson("L03", "任何奖励改动都要配一条'什么都不做也能拿分'的否定测试",
           "v0.37 前，策略靠站着不动刷 +1.20",
           "test:test_idle_agent_cannot_farm_bonus", "v0.37"),
    Lesson("L04", "加特征前先统计它的分布，否则会退化成常数",
           "v0.25 绕行距离分档 200 张图里 171 张落在同一档",
           "test:test_path_bucket_distribution_is_not_constant", "v0.22"),
    Lesson("L05", "先诊断瓶颈再动手：不是所有卡住都是'容量不够'",
           "v0.24 换更大模型更差；v0.27 换特征才好",
           "doc:docs/experiments/0020-bottleneck-dependence.md", "v0.24"),
    Lesson("L06", "两条独立测量路径必须对齐，否则先怀疑测量",
           "v0.29 诊断函数在评测时更新策略，得出相反结论",
           "test:test_diag_matches_evaluate", "v0.29"),
    Lesson("L07", "文献结论必须本地复现后再引用；引用时要同时给出本地结果",
           "v0.38 势能式塑形在本地'分数更高但行为不变'",
           "test:test_potential_shaping_matches_formula", "v0.38"),
    Lesson("L08", "没有收益的改动必须回退，并在代码里留注释指向实验记录",
           "v0.26 把塑形换成 BFS 距离后更差，已回退",
           "doc:docs/experiments/0014-three-attempts.md", "v0.26"),
    Lesson("L11", "任何结论必须引用已核实的事实编号（F1..F10）",
           "反复忘记'BFS 已在 ref-1 吃满 30/30'，连续几轮追一个追不到的目标",
           "test:test_claim_must_cite_facts", "v0.44"),
    Lesson("L10", "12 组的显著不足以定稿：必须在 ≥20 组上复现且区间仍不含 0",
           "v0.41 的探索奖励 +5.75（11/12）在 20 组时缩到 +3.20 且区间含 0",
           "test:test_small_sample_significance_is_not_enough", "v0.42"),
    Lesson("L09", "改代码前先看外部资料，但落地时必须配一次本地消融",
           "委托人提醒：论文与自己推要结合，不能只做一半",
           "doc:docs/MEMORY-PROTOCOL.md", "v0.39"),
)


def ci95(values: Sequence[float]) -> Optional[tuple[float, float]]:
    """95% 置信区间（正态近似）；样本少于 2 个时返回 None。"""
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    half = 1.96 * math.sqrt(var) / math.sqrt(len(values))
    return mean - half, mean + half


@dataclass
class ExperimentReport:
    """一次实验的"交付凭据"。缺任何一项都不该下结论。"""

    name: str
    repeats: int = 1
    diff_ci: Optional[tuple[float, float]] = None
    primary_metric: str = "mean_return"
    same_reward_baseline: bool = False
    reward_changed: bool = False
    idle_control: bool = False
    feature_stats: Optional[Dict[str, float]] = None
    literature_refs: List[str] = field(default_factory=list)
    claims_significant: bool = False
    cited_facts: List[str] = field(default_factory=list)


def check_experiment(report: ExperimentReport) -> List[str]:
    """返回违规清单；空列表表示可以下结论。"""
    violations: List[str] = []

    if report.repeats < 10:
        violations.append(f"L01 重复次数不足：{report.repeats} < 10")
    if report.repeats < 20 and report.claims_significant:
        violations.append(f"L10 样本 {report.repeats} < 20：不能声称'显著'，只能说'待复现'")

    if report.primary_metric in {"mean_return", "score", "reward"}:
        violations.append(
            f"L02 主指标是 {report.primary_metric}（与奖励相关）；应改为 ate/hurt/steps 之一"
        )

    if report.reward_changed and not report.same_reward_baseline:
        violations.append("L02/L07 改了奖励但没有在同奖励下重算基线")

    if report.reward_changed and not report.idle_control:
        violations.append("L03 改了奖励但没有'什么都不做'的对照")

    if report.feature_stats is not None:
        top_share = max(report.feature_stats.values()) if report.feature_stats else 0.0
        if top_share > 0.8:
            violations.append(f"L04 特征过于集中：单档占比 {top_share:.0%} > 80%")

    if report.literature_refs and report.repeats < 10:
        violations.append("L07 引用了文献但样本不足，不能声称复现")

    if report.repeats >= 10:
        if not report.cited_facts:
            violations.append("L11 结论必须引用已核实事实（lab facts --brief 看有哪些）")
        else:
            from .facts import check_citations

            violations.extend(f"L11 {item}" for item in check_citations(report.cited_facts))

    if report.diff_ci is not None and report.diff_ci[0] < 0 < report.diff_ci[1]:
        violations.append("L01 置信区间包含 0：只能说'未观察到差异'，不能说'有效'")

    return violations


def summary() -> str:
    lines = [f"教训库：{len(LESSONS)} 条（每条都必须有执行位置）", ""]
    for lesson in LESSONS:
        kind, _, target = lesson.enforcement.partition(":")
        label = {"test": "测试", "script": "脚本", "doc": "文档"}.get(kind, kind)
        lines.append(f"{lesson.lesson_id} [{label}] {lesson.rule}")
        lines.append(f"     为什么：{lesson.why}")
        lines.append(f"     执行：{target}（来自 {lesson.learned_at}）")
    return "\n".join(lines)
