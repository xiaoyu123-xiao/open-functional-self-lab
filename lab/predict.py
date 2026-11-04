"""预测基线对比（Issue 0003）。

问题：`lab run` 会记一个 `prediction_error`，但**它到底算好还是算差**？没有对照就无从谈起。
所以这里放三个预测器，用同一段环境、同一批 seed 跑同一套误差：

    random       下界：在观测范围内瞎猜（固定 seed，可复现）
    persistence  基线：假设"下一步和上一步完全一样"
    linear       稍聪明：假设"下一步 = 上一步 + 最近一次的变化量"

误差定义（与 docs/metrics.md 一致）：预测值与真实值在 x / y / energy / damage 四个键上的
**平均绝对偏差**。没有做显著性检验——样本小的时候极易虚假显著，文档里也写明了这一点。
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Sequence, Tuple

KEYS: Tuple[str, ...] = ("x", "y", "energy", "damage")
BOUNDS: Dict[str, Tuple[float, float]] = {
    "x": (0.0, 7.0),
    "y": (0.0, 7.0),
    "energy": (0.0, 1.0),
    "damage": (0.0, 1.0),
}


def error(predicted: Dict[str, float], actual: Dict[str, float]) -> float:
    total = 0.0
    for key in KEYS:
        total += abs(float(actual.get(key, 0.0)) - float(predicted.get(key, 0.0)))
    return round(total / len(KEYS), 6)


class Predictor:
    name = "base"

    def predict(self, observation: Dict[str, float]) -> Dict[str, float]:
        raise NotImplementedError

    def update(self, observation: Dict[str, float]) -> None:
        raise NotImplementedError


class Persistence(Predictor):
    """假设下一个观测和当前完全一样。最朴素，也最难被打败的基线。"""

    name = "persistence"

    def predict(self, observation: Dict[str, float]) -> Dict[str, float]:
        return {key: observation[key] for key in KEYS}

    def update(self, observation: Dict[str, float]) -> None:
        return None


class Linear(Predictor):
    """假设下一个观测 = 当前 + 上一次的变化量（速度外推）。"""

    name = "linear"

    def __init__(self) -> None:
        # 记住"这次预测是从哪个观测出发的"，update() 据此算出真实位移
        self._from: "Dict[str, float] | None" = None
        self._delta: Dict[str, float] = {key: 0.0 for key in KEYS}

    def predict(self, observation: Dict[str, float]) -> Dict[str, float]:
        self._from = {key: observation[key] for key in KEYS}
        predicted = {}
        for key in KEYS:
            low, high = BOUNDS[key]
            predicted[key] = min(high, max(low, observation[key] + self._delta[key]))
        return predicted

    def update(self, observation: Dict[str, float]) -> None:
        if self._from is not None:
            self._delta = {key: observation[key] - self._from[key] for key in KEYS}
        self._from = None


class RandomGuess(Predictor):
    """下界：在合法范围内随机猜。固定 seed，所以"随机"本身也可复现。"""

    name = "random"

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)

    def predict(self, observation: Dict[str, float]) -> Dict[str, float]:
        predicted = {}
        for key in KEYS:
            low, high = BOUNDS[key]
            predicted[key] = self._rng.uniform(low, high)
        return predicted

    def update(self, observation: Dict[str, float]) -> None:
        return None


def _std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


def benchmark(steps: int = 200, seeds: Sequence[int] = (1, 2, 3)) -> Dict[str, object]:
    """跑同一批 seed，返回每个预测器的误差统计。纯函数，给定输入必得同一结果。"""
    from .env import GridWorld, greedy_action  # 局部导入，避免循环依赖

    if steps <= 0:
        raise ValueError("steps 必须是正整数")
    if not seeds:
        raise ValueError("至少要有一个 seed")

    names = ("random", "persistence", "linear")
    errors: Dict[str, List[float]] = {name: [] for name in names}
    wins: Dict[str, int] = {name: 0 for name in names}
    tie_count = 0        # 并列最优的步数：不能算进任何一方的胜场，否则占比之和会超过 100%
    per_step: List[Dict[str, float]] = []

    for seed in seeds:
        environment = GridWorld(seed)
        observation = environment.observe()
        predictors: List[Predictor] = [
            RandomGuess(seed=seed),
            Persistence(),
            Linear(),
        ]
        for _ in range(steps):
            predictions = {predictor.name: predictor.predict(observation) for predictor in predictors}
            action = greedy_action(environment)
            outcome = environment.step(action)
            actual = outcome["observation"]
            step_errors = {name: error(predictions[name], actual) for name in names}
            for name in names:
                errors[name].append(step_errors[name])
            best = min(step_errors.values())
            winners = [name for name in names if step_errors[name] == best]
            if len(winners) == 1:
                wins[winners[0]] += 1
            else:
                tie_count += 1
            per_step.append(step_errors)
            for predictor in predictors:
                predictor.update(actual)
            observation = actual

    summary: Dict[str, object] = {
        "steps_per_seed": steps,
        "seeds": list(seeds),
        "samples": len(errors["random"]),
        "mean": {},
        "std": {},
        "win_rate": {},
        "tie_rate": 0.0,
        "per_step": per_step,
    }
    for name in names:
        values = errors[name]
        summary["mean"][name] = round(sum(values) / len(values), 6)  # type: ignore[index]
        summary["std"][name] = round(_std(values), 6)  # type: ignore[index]
        summary["win_rate"][name] = round(wins[name] / len(values), 4)  # type: ignore[index]
    summary["tie_rate"] = round(tie_count / len(errors["random"]), 4)  # type: ignore[index]
    return summary


def sparkline(values: Sequence[float], width: int = 40) -> str:
    """把误差序列压成一行 ASCII 曲线（无依赖）。"""
    if not values:
        return ""
    blocks = "▁▂▃▄▅▆▇█"
    if len(values) > width:
        bucket = len(values) / width
        bucketed = []
        for i in range(width):
            chunk = values[int(i * bucket):int((i + 1) * bucket)]
            if chunk:
                bucketed.append(sum(chunk) / len(chunk))
        values = bucketed
    low, high = min(values), max(values)
    if high - low < 1e-9:
        return blocks[0] * len(values)
    return "".join(blocks[min(len(blocks) - 1, int((value - low) / (high - low) * (len(blocks) - 1)))] for value in values)


def render_report(summary: Dict[str, object], generated_at: str) -> str:
    names = ("random", "persistence", "linear")
    means: Dict[str, float] = summary["mean"]  # type: ignore[assignment]
    stds: Dict[str, float] = summary["std"]  # type: ignore[assignment]
    win_rates: Dict[str, float] = summary["win_rate"]  # type: ignore[assignment]
    per_step: List[Dict[str, float]] = summary["per_step"]  # type: ignore[assignment]

    best = min(names, key=lambda name: means[name])
    gap = (means["persistence"] - means[best]) / means["persistence"] * 100 if means["persistence"] else 0.0

    lines: List[str] = []
    lines.append("# 预测基线对比")
    lines.append("")
    lines.append(f"> `python -m lab.cli bench` 自动生成于 `{generated_at}`，请勿手改。")
    lines.append(
        f"> 样本：{summary['samples']} 步（每 seed {summary['steps_per_seed']} 步 × seeds {summary['seeds']}）"
    )
    lines.append("> 误差定义：x / y / energy / damage 四项的平均绝对偏差。**未做显著性检验**。")
    lines.append("")
    lines.append("| 预测器 | 平均误差 | 标准差 | 单步严格最优占比 |")
    lines.append("|---|---|---|---|")
    for name in names:
        lines.append(f"| `{name}` | {means[name]:.4f} | {stds[name]:.4f} | {win_rates[name]*100:.1f}% |")
    tie_rate = float(summary.get("tie_rate", 0.0))  # type: ignore[arg-type]
    total_rate = sum(win_rates.values()) + tie_rate
    lines.append("")
    lines.append(
        f"校验：三者占比 + 并列 {tie_rate*100:.1f}% = {total_rate*100:.1f}%（必须等于 100%，"
        "否则说明统计口径又错了——v0.1.3 这里曾算出 168.2%）"
    )
    lines.append("")
    if best == "persistence":
        verdict = "没有预测器打败持久性基线——这说明当前的任务太可预测（网格世界），或预测器太弱。"
    else:
        verdict = f"`{best}` 比基线低 {gap:.1f}%（未做显著性检验，样本小时别当结论）。"
    lines.append(f"**结论**：{verdict}")
    lines.append("")
    lines.append("## 误差曲线（越矮越好）")
    lines.append("")
    for name in names:
        series = [entry[name] for entry in per_step]
        lines.append(f"- `{name}` `{sparkline(series)}`")
    lines.append("")
    lines.append("## 怎么读这张表")
    lines.append("")
    lines.append("- `random` 是下界：任何预测器如果打不过它，说明实现有 bug。")
    lines.append("- `persistence` 是主基线：网格世界里观测变化很小，它天然很强。")
    lines.append("- `linear` 是「稍聪明」的一档：它外推速度，但环境是离散移动，容易过冲。")
    lines.append("- 想看真差别，需要换更复杂的任务（Issue 0008），而不是调参。")
    lines.append("")
    return "\n".join(lines)
