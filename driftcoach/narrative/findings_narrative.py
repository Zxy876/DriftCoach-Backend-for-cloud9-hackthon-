from __future__ import annotations

from typing import List, Tuple

from driftcoach.question_state import DerivedFinding, QuestionState


def _to_fact_dict(findings: List[DerivedFinding]) -> List[dict]:
    facts: List[dict] = []
    for f in findings:
        fact_dict = {
            "fact_type": f.type,
            "note": f.summary,
            "confidence": f.confidence,
            "scope": f.scope if hasattr(f, "scope") else {},
        }
        if getattr(f, "supporting_facts", None):
            metrics = {}
            for sf in f.supporting_facts:
                scope = getattr(sf, "scope", None)
                if isinstance(scope, dict):
                    for k, v in scope.items():
                        if k not in metrics:
                            metrics[k] = v
            if metrics:
                fact_dict["metrics"] = metrics
        facts.append(fact_dict)
    return facts


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
    from driftcoach.narrative.narrative_synthesizer import synthesize_narrative
    from driftcoach.narrative.narrative_types import NarrativeType

    intent = question_state.intent
    scope_hint = {
        "player_name": getattr(question_state, "scope", None) if isinstance(getattr(question_state, "scope", None), str) else None,
    }

    facts = _to_fact_dict(findings)

    if intent == "PLAYER_REVIEW":
        narrative_type = NarrativeType.PLAYER_INSIGHT_REPORT
    elif intent == "MATCH_REVIEW":
        narrative_type = NarrativeType.MATCH_REVIEW_AGENDA
    elif intent == "SUMMARY" or question_state.scope == "SUMMARY":
        narrative_type = NarrativeType.SUMMARY_REPORT
    else:
        # fallback to legacy sections
        if intent == "MATCH_REVIEW":
            return _match_review(findings)
        if question_state.scope == "ECON":
            return _econ(findings)
        if question_state.scope == "PLAYER":
            return _player(findings)
        return _match_review(findings)

    result = synthesize_narrative(narrative_type, facts, scope_hint)
    return result.content, result.confidence
