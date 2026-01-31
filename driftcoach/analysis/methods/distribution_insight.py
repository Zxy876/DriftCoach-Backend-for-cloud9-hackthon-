from __future__ import annotations

from typing import Dict, List, Sequence, Any
from datetime import datetime

from driftcoach.analysis.registry import AnalysisMethod
from driftcoach.core.state import State
from driftcoach.outputs.distribution_insight import DistributionInsight


def _time_bucket(ts: str | None) -> str:
    if not ts:
        return "UNKNOWN"
    try:
        cleaned = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
        dt = datetime.fromisoformat(cleaned)
        return f"{dt.year}-{dt.month:02d}"
    except Exception:
        return "UNKNOWN"


def _build_buckets(states: Sequence[State]) -> Dict[str, Dict[str, int]]:
    buckets: Dict[str, Dict[str, int]] = {
        "format": {},
        "tournament": {},
        "time_bucket": {},
        "opponent": {},
    }

    for s in states:
        extras = s.extras or {}
        if extras.get("evidence_type") != "CONTEXT_ONLY":
            continue

        fmt = (extras.get("format") or "UNKNOWN").upper()
        tournament = extras.get("tournament") or "UNKNOWN"
        t_bucket = _time_bucket(extras.get("start_time"))

        opponents = extras.get("team_names") if isinstance(extras, dict) else None
        if isinstance(opponents, list) and opponents:
            opp_label = " vs ".join(sorted(str(o) for o in opponents))
        else:
            opp_label = "UNKNOWN"

        for key, value in (
            ("format", fmt),
            ("tournament", tournament),
            ("time_bucket", t_bucket),
            ("opponent", opp_label),
        ):
            buckets[key][value] = buckets[key].get(value, 0) + 1

    return buckets


def _build_summary(buckets: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "coverage": {"axes": {}, "overall": False},
        "concentration": {},
        "bias_flags": {},
    }

    axes = ["format", "tournament", "time_bucket", "opponent"]
    all_covered = True

    for axis in axes:
        axis_buckets = buckets.get(axis) or {}
        total = sum(axis_buckets.values())
        covered = total > 0
        summary["coverage"]["axes"][axis] = covered
        all_covered = all_covered and covered

        if total <= 0:
            summary["concentration"][axis] = {"top1": 0.0, "top3": 0.0, "total": 0}
            summary["bias_flags"][axis] = False
            continue

        sorted_counts = sorted(axis_buckets.values(), reverse=True)
        top1 = sorted_counts[0]
        top3 = sum(sorted_counts[:3])
        summary["concentration"][axis] = {
            "top1": round(top1 / total, 4),
            "top3": round(top3 / total, 4),
            "total": total,
        }

        bias_threshold = 0.6
        summary["bias_flags"][axis] = (top1 / total) >= bias_threshold

    summary["coverage"]["overall"] = all_covered
    return summary


def _axes_with_bias(summary: Dict[str, Any]) -> List[str]:
    axes = []
    conc = summary.get("concentration", {})
    bias = summary.get("bias_flags", {})
    for axis, stats in conc.items():
        top1 = stats.get("top1", 0)
        if top1 >= 0.6 or bias.get(axis):
            axes.append(axis)
    return axes


class DistributionInsightMethod(AnalysisMethod):
    name = "distribution_insight"
    scope = "context"
    requires: List[str] = []

    def __init__(self) -> None:
        self.trigger_conditions = {
            "min_context_states": lambda states: any((s.extras or {}).get("evidence_type") == "CONTEXT_ONLY" for s in states),
        }

    def eligible(self, states: Sequence[State]) -> bool:
        buckets = _build_buckets(states)
        summary = _build_summary(buckets)
        if not summary.get("coverage", {}).get("overall"):
            return False
        biased_axes = _axes_with_bias(summary)
        return bool(biased_axes)

    def run(self, states: Sequence[State]):
        buckets = _build_buckets(states)
        summary = _build_summary(buckets)
        if not summary.get("coverage", {}).get("overall"):
            return None
        axes = _axes_with_bias(summary)
        if not axes:
            return None
        return DistributionInsight.build(
            axes=axes,
            summary_ref="context.evidence.summary",
            confidence="LOW",
            note="No outcome/stats; descriptive only",
        )
