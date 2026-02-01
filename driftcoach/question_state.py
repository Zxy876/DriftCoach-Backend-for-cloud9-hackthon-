from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


def _gen_id(prefix: str, payload: str) -> str:
    raw = f"{prefix}:{payload}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


@dataclass
class FactRef:
    id: str
    fact_type: str
    scope: Dict[str, Any]
    summary: str
    confidence: float = 0.5

    @staticmethod
    def from_fact(fact: Dict[str, Any], default_type: Optional[str] = None) -> "FactRef":
        fact_type = fact.get("fact_type") or fact.get("type") or default_type or "UNKNOWN"
        scope = fact.get("scope") or {
            "series_id": fact.get("series_id"),
            "team_id": fact.get("team_id"),
            "player_id": fact.get("player_id"),
            "player_name": fact.get("player_name"),
            "round_range": fact.get("round_range") or fact.get("round"),
            "map": fact.get("map"),
        }
        summary = fact.get("note") or fact.get("description") or fact_type
        base_id = fact.get("id") or fact.get("fact_id") or fact.get("uuid") or summary
        fact_id = _gen_id("fact", f"{fact_type}:{base_id}:{scope}")
        conf = 0.5
        metrics = fact.get("metrics") or {}
        sample = metrics.get("sample_size") or fact.get("sample_size")
        if sample:
            conf = min(0.9, 0.5 + min(sample / 100.0, 0.35))
        elif fact.get("confidence") == "high":
            conf = 0.7
        elif fact.get("confidence") == "medium":
            conf = 0.6
        return FactRef(id=fact_id, fact_type=fact_type, scope=scope, summary=summary, confidence=conf)


@dataclass
class DerivedFinding:
    id: str
    type: str
    scope: str
    summary: str
    supporting_facts: List[FactRef] = field(default_factory=list)
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "scope": self.scope,
            "summary": self.summary,
            "supporting_facts": [
                {
                    "id": f.id,
                    "fact_type": f.fact_type,
                    "scope": f.scope,
                    "summary": f.summary,
                    "confidence": f.confidence,
                }
                for f in self.supporting_facts
            ],
            "confidence": self.confidence,
        }


@dataclass
class QuestionState:
    question_id: str
    question_text: str
    intent: str
    scope: str
    required_fact_types: List[str]
    available_facts: List[Dict[str, Any]]
    derived_findings: List[DerivedFinding] = field(default_factory=list)
    confidence: float = 0.0
    status: Literal["ANSWERED", "WEAK", "INSUFFICIENT"] = "INSUFFICIENT"

    @staticmethod
    def new(question_text: str, intent: str, scope: str, required_fact_types: Optional[List[str]] = None, available_facts: Optional[List[Dict[str, Any]]] = None) -> "QuestionState":
        return QuestionState(
            question_id=uuid.uuid4().hex,
            question_text=question_text,
            intent=intent,
            scope=scope,
            required_fact_types=list(required_fact_types or []),
            available_facts=list(available_facts or []),
            derived_findings=[],
            confidence=0.0,
            status="INSUFFICIENT",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "intent": self.intent,
            "scope": self.scope,
            "required_fact_types": self.required_fact_types,
            "derived_findings": [f.to_dict() for f in self.derived_findings],
            "confidence": self.confidence,
            "status": self.status,
        }


@dataclass
class SessionQAState:
    session_id: str
    questions: List[QuestionState] = field(default_factory=list)
    findings_pool: List[DerivedFinding] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "questions": [q.to_dict() for q in self.questions],
            "findings_pool": [f.to_dict() for f in self.findings_pool],
        }
