"""
LLM Interpretation Layer (pure presentation): converts structured outputs
into qualitative, number-free explanations. It must not mutate inputs,
introduce new facts, or recommend actions.
"""
from __future__ import annotations

import random
from typing import Sequence, Union

from driftcoach.outputs.insight import Insight
from driftcoach.outputs.review_item import ReviewAgendaItem
from driftcoach.outputs.what_if import WhatIfOutcome

OutputType = Union[Insight, ReviewAgendaItem, WhatIfOutcome]


def interpret(output_obj: OutputType) -> str:
    if isinstance(output_obj, Insight):
        return _interpret_insight(output_obj)
    if isinstance(output_obj, ReviewAgendaItem):
        return _interpret_review(output_obj)
    if isinstance(output_obj, WhatIfOutcome):
        return _interpret_what_if(output_obj)
    return ""  # unknown type: return empty explanation


def _confidence_tone(conf: float) -> str:
    if conf >= 0.75:
        return "信号稳健，波动较低。"
    if conf >= 0.5:
        return "信号可用，但仍有一定波动。"
    if conf >= 0.25:
        return "信号偏弱，更多作为提示而非结论。"
    return "信号很弱，需谨慎看待。"


def _sample_tone(sample_size: int) -> str:
    if sample_size >= 50:
        return "样本量充分，观察更稳定。"
    if sample_size >= 20:
        return "样本量中等，可能存在波动。"
    return "样本量有限，结果仅作初步参考。"


def _delta_tone(value: float, baseline: float | None) -> str:
    if baseline is None:
        return "缺少基线，对偏离程度的解读受限。"
    delta = value - baseline
    if delta >= 0.1:
        return "表现显著高于基线，呈现正向偏离。"
    if delta <= -0.1:
        return "表现显著低于基线，值得注意的负向偏离。"
    return "表现接近基线，偏离不大。"


def _volatility_tone(value: float, baseline: float | None) -> str:
    # Qualitative risk shape without exposing numbers
    if baseline is None:
        return "风险形态不明朗，但可关注未来波动。"
    gap = abs(value - baseline)
    if gap >= 0.2:
        return "呈现高波动 / boom-or-bust 的形态。"
    if gap >= 0.05:
        return "存在一定波动，但尚在可控范围。"
    return "波动较低，更偏稳定收益。"


def _interpret_insight(insight: Insight) -> str:
    fact = insight.derived_facts[0]
    parts: Sequence[str] = [
        _delta_tone(fact.value, fact.baseline),
        _volatility_tone(fact.value, fact.baseline),
        _sample_tone(fact.sample_size),
        _confidence_tone(insight.confidence),
    ]
    return " ".join(parts)


def _interpret_review(review: ReviewAgendaItem) -> str:
    fact = review.evidence[0]
    parts: Sequence[str] = [
        _delta_tone(fact.value, fact.baseline),
        "关注该主题的结构性风险，适合复盘讨论。",
        _sample_tone(fact.sample_size),
        _confidence_tone(review.confidence),
    ]
    return " ".join(parts)


def _interpret_what_if(what_if: WhatIfOutcome) -> str:
    actions = list(what_if.actions)
    rng = random.Random(42)
    if len(actions) < 2:
        action_tone = rng.choice(
            [
                "方案较少，差异有限，可视为接近等价。",
                "仅有少量方案，缺乏对比基础。",
            ]
        )
    else:
        win_probs = [what_if.outcomes[a].get("win_prob", 0.0) or 0.0 for a in actions]
        spread = max(win_probs) - min(win_probs)
        if spread >= 0.2:
            candidates = [
                "两个方案差距显著，更偏向稳态一侧。",
                "对比呈现明显分化，可按风险偏好取舍。",
            ]
        elif spread >= 0.05:
            candidates = [
                "方案间有可感知差异，可结合上下文取舍。",
                "差距存在但不极端，可按团队偏好调整。",
            ]
        else:
            candidates = [
                "方案差异很小，可视为等价选择。",
                "两个方案近乎持平，关注执行稳定性。",
            ]
        action_tone = rng.choice(candidates)

    parts: Sequence[str] = [
        action_tone,
        _confidence_tone(what_if.confidence),
    ]
    return " ".join(parts)
