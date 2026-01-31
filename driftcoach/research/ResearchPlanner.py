from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Literal


ResearchIntent = Literal[
    "PERFORMANCE_STABILITY",
    "PERFORMANCE_RISK",
    "FORM_VOLATILITY",
    "PERFORMANCE_OVERVIEW",
    "STABILITY_CHECK",
    "WHAT_IF",
    "REVIEW",
    "IMPROVEMENT_ADVICE",
]


@dataclass
class EvidenceAxis:
    axis: Literal["time", "baseline", "opponent", "format", "segment"]
    required: bool = True
    proxy_allowed: bool = True


@dataclass
class ConvergenceTarget:
    name: Literal["PLAYER_STATS", "TEAM_STATS"]
    unlocks_axes: List[str] = field(default_factory=list)
    priority: int = 1
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)


@dataclass
class StopPolicy:
    min_axes_required: int
    allow_proxy_completion: bool = True


@dataclass
class ResearchPlan:
    research_intent: ResearchIntent
    evidence_axes: List[EvidenceAxis]
    convergence_targets: List[ConvergenceTarget]
    stop_policy: StopPolicy


@dataclass
class ResearchProgress:
    satisfied_axes: List[str]
    missing_axes: List[str]
    closest_convergence_target: Optional[Dict[str, str]]
    can_answer: bool


INTENT_MAP = {
    "PERFORMANCE_OVERVIEW": ["time", "baseline"],
    "STABILITY_CHECK": ["baseline", "time"],
    "WHAT_IF": ["baseline", "segment"],
    "REVIEW": ["time", "opponent"],
    "IMPROVEMENT_ADVICE": ["baseline", "segment", "opponent"],
}


def _map_intent_label(coach_query: str) -> Optional[str]:
    q = (coach_query or "").lower()
    if "如果" in coach_query or "what if" in q or "换打法" in coach_query:
        return "WHAT_IF"
    if "复盘" in coach_query or "review" in q:
        return "REVIEW"
    if "建议" in coach_query or "提升" in coach_query:
        return "IMPROVEMENT_ADVICE"
    if "稳定" in coach_query or "波动" in coach_query:
        return "PERFORMANCE_STABILITY"
    if "表现" in coach_query or "overview" in q:
        return "PERFORMANCE_OVERVIEW"
    return None


def _infer_intent(coach_query: str) -> ResearchIntent:
    mapped = _map_intent_label(coach_query)
    if mapped:
        return mapped  # type: ignore[return-value]
    q = (coach_query or "").lower()
    if "风险" in coach_query or "高风险" in coach_query:
        return "PERFORMANCE_RISK"
    if "异常" in coach_query or "稳定" in coach_query:
        return "PERFORMANCE_STABILITY"
    return "PERFORMANCE_STABILITY"


def _axes_for_intent(intent: ResearchIntent) -> List[EvidenceAxis]:
    if intent in INTENT_MAP:
        axes = []
        mapped = INTENT_MAP[intent]
        for ax in mapped:
            required = True
            proxy_allowed = ax != "baseline"
            axes.append(EvidenceAxis(axis=ax, required=required, proxy_allowed=proxy_allowed))
        return axes
    if intent == "PERFORMANCE_RISK":
        return [
            EvidenceAxis(axis="opponent", required=True, proxy_allowed=True),
            EvidenceAxis(axis="baseline", required=True, proxy_allowed=False),
            EvidenceAxis(axis="time", required=False, proxy_allowed=True),
        ]
    if intent == "PERFORMANCE_STABILITY":
        return [
            EvidenceAxis(axis="time", required=True, proxy_allowed=True),
            EvidenceAxis(axis="baseline", required=True, proxy_allowed=False),
            EvidenceAxis(axis="opponent", required=False, proxy_allowed=True),
            EvidenceAxis(axis="format", required=False, proxy_allowed=True),
        ]
    # FORM_VOLATILITY default
    return [
        EvidenceAxis(axis="time", required=True, proxy_allowed=True),
        EvidenceAxis(axis="format", required=True, proxy_allowed=True),
        EvidenceAxis(axis="baseline", required=False, proxy_allowed=False),
    ]


def _convergence_targets(intent: ResearchIntent) -> List[ConvergenceTarget]:
    return [
        ConvergenceTarget(
            name="PLAYER_STATS",
            required_fields=["playerId"],
            optional_fields=["tournamentIds", "timeWindow"],
            unlocks_axes=["baseline", "time", "stability"],
            priority=1,
        ),
        ConvergenceTarget(
            name="TEAM_STATS",
            required_fields=["teamId"],
            optional_fields=["tournamentIds", "timeWindow"],
            unlocks_axes=["baseline", "opponent"],
            priority=2,
        ),
    ]


def _stop_policy(intent: ResearchIntent) -> StopPolicy:
    if intent in INTENT_MAP:
        return StopPolicy(min_axes_required=max(1, min(3, len(INTENT_MAP[intent]))), allow_proxy_completion=True)
    if intent == "PERFORMANCE_STABILITY":
        return StopPolicy(min_axes_required=2, allow_proxy_completion=True)
    if intent == "PERFORMANCE_RISK":
        return StopPolicy(min_axes_required=2, allow_proxy_completion=True)
    return StopPolicy(min_axes_required=2, allow_proxy_completion=True)


def build_research_plan(payload: Dict[str, any]) -> ResearchPlan:
    coach_query = payload.get("coach_query", "") if isinstance(payload, dict) else ""
    intent = _infer_intent(coach_query)
    axes = _axes_for_intent(intent)
    targets = _convergence_targets(intent)
    stop = _stop_policy(intent)
    return ResearchPlan(
        research_intent=intent,
        evidence_axes=axes,
        convergence_targets=targets,
        stop_policy=stop,
    )


def _axis_satisfied(axis: str, mining_summary: any) -> bool:
    if mining_summary is None:
        return False
    counts = getattr(mining_summary, "entity_counts", {}) or getattr(mining_summary, "discovered", {}) or {}
    if isinstance(counts, dict):
        series = counts.get("series") or len(counts.get("series", [])) if isinstance(counts.get("series"), list) else counts.get("series", 0)
        teams = counts.get("teams") or len(counts.get("teams", [])) if isinstance(counts.get("teams"), list) else counts.get("teams", 0)
    else:
        series = teams = 0

    if axis == "time":
        return bool(series)
    if axis == "opponent":
        return teams >= 2
    if axis == "format":
        return bool(series)
    if axis == "segment":
        return bool(series)
    # baseline requires stats (not satisfied here)
    return False


def _blocked_reason(mining_summary: any) -> Optional[str]:
    if mining_summary is None:
        return None
    term = getattr(mining_summary, "termination_reason", None) or getattr(mining_summary, "reason", None)
    if term == "API_CONSTRAINED":
        return "API 受限或网络异常"
    if term == "ALL_TEMPLATES_BLOCKED":
        return "可用模板被 schema 阻断"
    if isinstance(term, str) and term and term.startswith("grid_"):
        return term
    attempts = getattr(mining_summary, "attempts", []) or []
    for att in attempts:
        notes = getattr(att, "notes", None) or (att.get("notes") if isinstance(att, dict) else None)
        if notes and "schema" in str(notes).lower():
            return str(notes)
    return None


def evaluate_mining_progress(research_plan: ResearchPlan, mining_summary: any) -> ResearchProgress:
    satisfied: List[str] = []
    missing: List[str] = []
    for axis_obj in research_plan.evidence_axes:
        if _axis_satisfied(axis_obj.axis, mining_summary):
            satisfied.append(axis_obj.axis + ("(proxy)" if axis_obj.proxy_allowed else ""))
        else:
            missing.append(axis_obj.axis)

    target = research_plan.convergence_targets[0] if research_plan.convergence_targets else None
    blocked_reason = _blocked_reason(mining_summary)
    closest_target = None
    if target:
        closest_target = {"name": target.name}
        if blocked_reason:
            closest_target["blocked_reason"] = blocked_reason

    required_axes = [a.axis for a in research_plan.evidence_axes if a.required]
    satisfied_core = [a for a in satisfied if a.split("(")[0] in required_axes]
    can_answer = len(satisfied_core) >= research_plan.stop_policy.min_axes_required

    return ResearchProgress(
        satisfied_axes=satisfied,
        missing_axes=missing,
        closest_convergence_target=closest_target,
        can_answer=can_answer,
    )
