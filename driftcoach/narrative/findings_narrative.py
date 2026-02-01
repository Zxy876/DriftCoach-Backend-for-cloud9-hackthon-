from __future__ import annotations

from typing import List, Tuple

from driftcoach.question_state import DerivedFinding, QuestionState


def _render_sections(findings: List[DerivedFinding]) -> List[str]:
    lines: List[str] = []
    grouped = {}
    for f in findings:
        grouped.setdefault(f.type, []).append(f)
    order = ["ECON_PROBLEM", "MAP_WEAKNESS", "MOMENTUM_SHIFT", "PLAYER_RISK"]
    for key in order:
        if key not in grouped:
            continue
        section = [f"【{key}】"]
        for item in grouped[key]:
            section.append(f"- {item.summary} (conf={item.confidence:.2f})")
        lines.append("\n".join(section))
    return lines


def _match_review(findings: List[DerivedFinding]) -> Tuple[str, float]:
    if not findings:
        return "基于当前问题，未形成稳定分析结论", 0.2
    sections = _render_sections(findings)
    content = "\n\n".join(sections)
    conf = min(0.9, sum(f.confidence for f in findings) / len(findings))
    return content, conf


def _econ(findings: List[DerivedFinding]) -> Tuple[str, float]:
    if not findings:
        return "当前仅聚焦经济管理：未形成可复用结论。", 0.25
    lines = ["【经济管理问题】"]
    for f in findings:
        lines.append(f"- {f.summary} (conf={f.confidence:.2f})")
    conf = min(0.9, sum(f.confidence for f in findings) / len(findings))
    return "\n".join(lines), conf


def _summary(findings: List[DerivedFinding]) -> Tuple[str, float]:
    if not findings:
        return "当前系统尚未形成可总结的分析结论。", 0.2
    lines = ["【关键教训】"]
    for f in findings:
        lines.append(f"- 来自 {f.type}: {f.summary}")
    conf = min(0.9, sum(f.confidence for f in findings) / len(findings))
    return "\n".join(lines), conf


def _player(findings: List[DerivedFinding]) -> Tuple[str, float]:
    if not findings:
        return "当前缺少与指定选手相关的风险观察。", 0.25
    lines = ["【选手风险】"]
    for f in findings:
        lines.append(f"- {f.summary} (conf={f.confidence:.2f})")
    conf = min(0.9, sum(f.confidence for f in findings) / len(findings))
    return "\n".join(lines), conf


def render_narrative_from_findings(question_state: QuestionState, findings: List[DerivedFinding]) -> Tuple[str, float]:
    intent = question_state.intent
    if intent == "MATCH_REVIEW":
        return _match_review(findings)
    if intent == "SUMMARY" or question_state.scope == "SUMMARY":
        return _summary(findings)
    if question_state.scope == "ECON":
        return _econ(findings)
    if question_state.scope == "PLAYER":
        return _player(findings)
    return _match_review(findings)
