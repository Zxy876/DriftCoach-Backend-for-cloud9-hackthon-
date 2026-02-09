from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Any

from driftcoach.config.bounds import (
    SystemBounds,
    DEFAULT_BOUNDS,
    enforce_bounds_on_facts,
    calculate_finding_quota,
)


@dataclass
class AnswerInput:
    question: str
    intent: str
    required_facts: List[str]
    facts: Dict[str, List[Dict[str, Any]]]
    series_id: str


@dataclass
class AnswerSynthesisResult:
    claim: str
    verdict: Literal["YES", "NO", "INSUFFICIENT"]
    support_facts: List[str]
    counter_facts: List[str]
    confidence: float
    followups: List[str]


def _fmt_fact(fact: Dict[str, Any]) -> str:
    note = fact.get("note") or ""
    rr = fact.get("round_range") or []
    rr_str = f"R{rr[0]}-R{rr[1]}" if len(rr) == 2 else ""
    gi = fact.get("game_index")
    game_str = f"G{gi}" if gi is not None else ""
    pieces = [p for p in [game_str, rr_str, note] if p]
    return " | ".join(pieces) or fact.get("fact_type") or "fact"


def _support_strings(
    facts: List[Dict[str, Any]],
    limit: int = None,
    bounds: SystemBounds = DEFAULT_BOUNDS,
) -> List[str]:
    """
    Format facts into support strings, respecting hard bounds.

    Args:
        facts: List of fact dictionaries
        limit: Optional explicit limit (overrides bounds if provided)
        bounds: System bounds to enforce

    Returns:
        List of formatted fact strings
    """
    if limit is None:
        limit = bounds.max_support_facts
    out: List[str] = []
    for f in facts[:limit]:
        out.append(_fmt_fact(f))
    return out


def _counter_strings(
    facts: List[Dict[str, Any]],
    limit: int = None,
    bounds: SystemBounds = DEFAULT_BOUNDS,
) -> List[str]:
    """
    Format counter-fact strings, respecting hard bounds.

    Args:
        facts: List of counter-fact dictionaries (or string messages)
        limit: Optional explicit limit (overrides bounds if provided)
        bounds: System bounds to enforce

    Returns:
        List of formatted counter-fact strings
    """
    if limit is None:
        limit = bounds.max_counter_facts

    # Handle both dict facts and string messages
    out: List[str] = []
    for f in facts[:limit]:
        if isinstance(f, dict):
            out.append(_fmt_fact(f))
        else:
            out.append(str(f))
    return out


def _limit_followups(
    followups: List[str],
    bounds: SystemBounds = DEFAULT_BOUNDS,
) -> List[str]:
    """Limit follow-up questions to max_followup_questions bound."""
    return (followups or [])[:bounds.max_followup_questions]


def _swings_across_segments(swings: List[Dict[str, Any]]) -> bool:
    if not swings:
        return False
    game_indices = {f.get("game_index") for f in swings if f.get("game_index") is not None}
    if len(game_indices) >= 2:
        return True
    rounds = [r for f in swings for r in (f.get("round_range") or []) if isinstance(r, int)]
    if not rounds:
        return False
    return max(rounds) - min(rounds) >= 3 and len(swings) >= 3


def _swing_changes_winner(fact: Dict[str, Any]) -> bool:
    opening = fact.get("opening_team")
    winner = fact.get("winner") or fact.get("winning_team")
    if opening and winner:
        return str(opening) != str(winner)
    note = (fact.get("note") or "").lower()
    if "opening_team=" in note and "winner=" in note:
        try:
            segs = {kv.split("=")[0]: kv.split("=")[1] for kv in note.replace(",", " ").split() if "=" in kv}
            if segs.get("opening_team") and segs.get("winner"):
                return segs["opening_team"] != segs["winner"]
        except Exception:
            pass
    if "loser_kills" in note:
        return True
    return False


def synthesize_answer(
    inp: AnswerInput,
    bounds: SystemBounds = DEFAULT_BOUNDS,
) -> AnswerSynthesisResult:
    """
    ✅ Phase 2: Delegate to divide-and-conquer synthesizer with Spec-based visibility reduction.

    This wrapper maintains backward compatibility while using the new handler-based architecture
    that integrates Spec contracts for filtering facts by intent.
    """
    from driftcoach.analysis.synthesizer_router import AnswerSynthesizer

    synthesizer = AnswerSynthesizer()
    return synthesizer.synthesize(inp, bounds=bounds)


def render_answer(result: AnswerSynthesisResult) -> str:
    support = result.support_facts or ["无"]
    counter = result.counter_facts or ["无"]
    followups = result.followups or ["无"]
    lines = [
        "【结论】",
        result.claim,
        "",
        "【依据】",
        *(f"- {s}" for s in support),
        "",
        "【不确定性 / 反例】",
        *(f"- {c}" for c in counter),
        "",
        "【置信度】",
        str(result.confidence),
        "",
        "【可继续追问】",
        *(f"- {f}" for f in followups),
    ]
    return "\n".join(lines)
