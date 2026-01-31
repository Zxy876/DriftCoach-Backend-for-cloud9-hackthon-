from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# Allowed Fact whitelist (附件 B)
ALLOWED_FACTS = {
    "FULL_BUY_ROUND",
    "FORCE_BUY_ROUND",
    "ROUND_SWING",
    "HIGH_RISK_SEQUENCE",
    "ECO_COLLAPSE_SEQUENCE",
    "OBJECTIVE_LOSS_CHAIN",
}


def _extract_player_name(coach_query: str, fallback_name: Optional[str] = None) -> Optional[str]:
    """Best-effort extract player name from NL query.

    Strategy: pick the first token that looks like a player handle (latin letters/numbers/underscore)
    and starts with a letter; otherwise reuse last known player name.

    player_id 是执行细节，player_name 才是认知入口。
    """
    if not coach_query and not fallback_name:
        return None
    pattern = re.compile(r"\b([A-Za-z][A-Za-z0-9_\-]{2,})\b")
    match = pattern.search(coach_query or "")
    if match:
        return match.group(1)
    return fallback_name


def _intent_and_facts_from_query(coach_query: str, last_player_name: Optional[str] = None) -> Dict[str, Any]:
    q_raw = coach_query or ""
    q = q_raw.lower()

    def has_any(keywords: List[str]) -> bool:
        return any(k in q for k in keywords)

    # 默认设定（用于 fallback）
    intent = "UNKNOWN"
    question_type = "OPEN"
    required_facts: List[str] = []
    entities: List[str] = ["team", "round"]
    temporal_granularity = "round"
    temporal_range = "entire_series"
    player_name = _extract_player_name(q_raw, fallback_name=last_player_name)

    # A1. 问题类型映射表（硬规则）
    if has_any(["高风险", "risk", "高危", "险局"]):
        intent = "RISK_ASSESSMENT"
        question_type = "CLASSIFICATION"
        required_facts = ["HIGH_RISK_SEQUENCE", "ROUND_SWING"]
    elif has_any(["保枪", "省枪", "save gun", "不强起", "不 force", "不强买"]):
        intent = "ECONOMIC_COUNTERFACTUAL"
        question_type = "WHAT_IF"
        required_facts = ["FORCE_BUY_ROUND", "ECO_COLLAPSE_SEQUENCE", "FULL_BUY_ROUND"]
        temporal_range = "critical_rounds"
    elif has_any(["反复", "频次", "多次", "稳定性", "偶发", "重复"]):
        intent = "STABILITY_ANALYSIS"
        question_type = "DISTRIBUTION"
        required_facts = ["ROUND_SWING"]
    elif has_any(["反转", "逆转", "翻盘", "势头", "swing"]):
        intent = "MOMENTUM_ANALYSIS"
        question_type = "DETECTION"
        required_facts = ["ROUND_SWING"]
    elif has_any(["经济崩", "eco 崩", "经济断档", "eco collapse"]):
        intent = "ECONOMIC_FAILURE"
        question_type = "DIAGNOSIS"
        required_facts = ["ECO_COLLAPSE_SEQUENCE"]
    elif has_any(["强起", "force buy"]) and has_any(["失败", "输", "失败了", "没成功", "失利"]):
        intent = "TACTICAL_EVAL"
        question_type = "EVALUATION"
        required_facts = ["FORCE_BUY_ROUND"]
    elif has_any(["崩盘", "崩溃", "断档", "经济断", "eco 崩溃"]):
        intent = "COLLAPSE_ONSET_ANALYSIS"
        question_type = "DIAGNOSIS"
        required_facts = ["ECO_COLLAPSE_SEQUENCE", "ROUND_SWING"]
    elif has_any(["上半", "下半", "阶段", "phase", "节奏"]):
        intent = "PHASE_COMPARISON"
        question_type = "COMPARISON"
        required_facts = ["ROUND_SWING", "HIGH_RISK_SEQUENCE"]
    elif has_any(["战术决策", "执行", "回合决策", "起买", "force", "半起", "tactical"]):
        intent = "TACTICAL_DECISION_EVAL"
        question_type = "EVALUATION"
        required_facts = ["FORCE_BUY_ROUND", "FULL_BUY_ROUND", "ROUND_SWING"]
    elif has_any(["执行力", "strategy", "战略", "策应", "执行与战略"]):
        intent = "EXECUTION_VS_STRATEGY"
        question_type = "EVALUATION"
        required_facts = ["OBJECTIVE_LOSS_CHAIN", "ROUND_SWING"]
    elif has_any(["弱点", "薄弱", "突破口", "map", "点位", "防守漏洞"]):
        intent = "MAP_WEAK_POINT"
        question_type = "DETECTION"
        required_facts = ["HIGH_RISK_SEQUENCE", "OBJECTIVE_LOSS_CHAIN"]
    elif has_any(["回合拆解", "round breakdown", "逐回合", "回合分析", "回合分解"]):
        intent = "ROUND_BREAKDOWN"
        question_type = "ANALYSIS"
        required_facts = ["ROUND_SWING", "FORCE_BUY_ROUND"]

    # 玩家相关意图：如果提到 player 名或包含“选手/他/她”等语义，则标记
    if player_name or has_any(["选手", "他", "她", "个人表现", "个人"]):
        if "player" not in entities:
            entities.append("player")

    # 过滤到白名单并兜底
    required_facts = [f for f in required_facts if f in ALLOWED_FACTS]
    if not required_facts:
        required_facts = ["OBJECTIVE_LOSS_CHAIN"]
        intent = intent or "UNKNOWN"
        question_type = question_type or "OPEN"

    return {
        "intent": intent,
        "question_type": question_type,
        "required_facts": required_facts,
        "entities": entities,
        "player_name": player_name,
        "temporal_granularity": temporal_granularity,
        "temporal_range": temporal_range,
    }


def generate_mining_plan(
    coach_query: str,
    series_id: str,
    existing_facts: Optional[List[Dict[str, Any]]] = None,
    last_player_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deterministic stand-in for GPT-4o Mining Orchestrator.
    Produces a MiningPlan JSON that downstream executors must follow.
    """

    parsed = _intent_and_facts_from_query(coach_query, last_player_name=last_player_name)

    plan = {
        "intent": parsed["intent"],
        "question_type": parsed["question_type"],
        "required_facts": parsed["required_facts"],
        "scope": {
            "series_id": series_id or "",
            "entities": parsed["entities"],
        },
        "temporal_focus": {
            "granularity": parsed["temporal_granularity"],
            "range": parsed["temporal_range"],
        },
        "constraints": {
            "min_samples": 3,
            "confidence_threshold": 0.7,
        },
        "fallback": {
            "if_missing": "ACK_INSUFFICIENT_EVIDENCE",
            "if_insufficient_data": "ACK_INSUFFICIENT_EVIDENCE",
        },
    }

    if parsed.get("player_name"):
        plan["scope"]["player"] = {"name": parsed["player_name"]}

    # If existing facts already cover requested types, keep same request but executor may short-circuit
    if existing_facts:
        have_types = {f.get("fact_type") for f in existing_facts}
        missing = [f for f in plan["required_facts"] if f not in have_types]
        plan["missing_required_facts"] = missing

    return plan
