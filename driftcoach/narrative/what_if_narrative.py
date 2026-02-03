from __future__ import annotations

from typing import Any, Dict, List

from driftcoach.outputs.what_if import WhatIfOutcome


def render_what_if_narrative(what_if: WhatIfOutcome) -> str:
    """Render What-If analysis into narrative form."""
    actions = what_if.actions
    outcomes: Dict[Any, Dict[str, Any]] = what_if.outcomes

    if not actions:
        return "当前缺少可比较的行动选项。"

    sorted_actions = sorted(actions, key=lambda a: outcomes.get(a, {}).get("win_prob", 0), reverse=True)
    best_action = sorted_actions[0]
    worst_action = sorted_actions[-1]
    best_outcome = outcomes.get(best_action, {})
    worst_outcome = outcomes.get(worst_action, {})

    lines: List[str] = []
    lines.append(f"当前状态：{getattr(what_if.state, 'state_id', what_if.state)}")
    lines.append("")

    for action in actions:
        outcome = outcomes.get(action, {})
        win_prob = outcome.get("win_prob", 0) * 100
        support = outcome.get("support_count") or outcome.get("support") or 0
        insufficient = outcome.get("insufficient_support", False)
        if insufficient:
            lines.append(f"选项 {action.value}：预测胜率 {win_prob:.1f}%（样本不足，历史相似局 <5）")
        else:
            lines.append(f"选项 {action.value}：预测胜率 {win_prob:.1f}%（基于 {support} 个相似局面）")

    lines.append("")
    delta = (best_outcome.get("win_prob", 0) - worst_outcome.get("win_prob", 0)) if actions else 0
    if delta > 0.2:
        lines.append(
            f"建议选择 {best_action.value}：该选项胜率比 {worst_action.value} 高 {delta*100:.1f} 个百分点"
        )
    else:
        lines.append("两个选项胜率差异有限，可结合团队状态再决定。")

    return "\n".join(lines)
