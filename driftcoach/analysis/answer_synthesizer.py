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
    intent = (inp.intent or "").upper()
    facts = inp.facts or {}

    def get_list(ft: str) -> List[Dict[str, Any]]:
        return facts.get(ft, [])

    support: List[str] = []
    counter: List[str] = []
    followups: List[str] = []
    claim = "未生成结论"
    verdict: Literal["YES", "NO", "INSUFFICIENT"] = "INSUFFICIENT"
    confidence = 0.3

    # 1. 高风险对局
    if intent == "RISK_ASSESSMENT":
        hrs = get_list("HIGH_RISK_SEQUENCE")
        swings = get_list("ROUND_SWING")
        if len(hrs) >= 2:
            verdict = "YES"
            claim = "这是一场高风险对局"
            confidence = 0.9
            support = _support_strings(hrs, bounds=bounds) or _support_strings(swings, bounds=bounds)
        elif len(swings) >= 5:
            verdict = "YES"
            claim = "这是一场高风险对局"
            confidence = 0.75
            support = _support_strings(swings, bounds=bounds)
        else:
            verdict = "INSUFFICIENT"
            claim = "现有证据不足以判定为高风险对局"
            confidence = 0.35
            counter = [f"HIGH_RISK_SEQUENCE={len(hrs)}", f"ROUND_SWING={len(swings)}"]
            followups = ["补充更多局数的风险片段", "核查关键局的输分原因"]

    # 2. 保枪 vs 强起
    elif intent == "ECONOMIC_COUNTERFACTUAL":
        force_buy = get_list("FORCE_BUY_ROUND")
        eco_collapse = get_list("ECO_COLLAPSE_SEQUENCE")
        full_buy = get_list("FULL_BUY_ROUND")
        if len(force_buy) > 0 and len(eco_collapse) > 0:
            verdict = "YES"
            claim = "强起决策很可能放大了风险，保枪可能更优"
            confidence = 0.82
            # Enforce max_findings_per_intent: limit to 2 total
            support = _support_strings(force_buy, limit=1, bounds=bounds) + _support_strings(eco_collapse, limit=1, bounds=bounds)
        elif len(full_buy) > len(force_buy):
            verdict = "NO"
            claim = "即使保枪，结果也未必会更好"
            confidence = 0.55
            support = _support_strings(full_buy, bounds=bounds)
            counter = _support_strings(force_buy, bounds=bounds)
        else:
            verdict = "INSUFFICIENT"
            claim = "无法仅凭当前经济事件判断"
            confidence = 0.35
            counter = [f"FORCE_BUY_ROUND={len(force_buy)}", f"ECO_COLLAPSE_SEQUENCE={len(eco_collapse)}", f"FULL_BUY_ROUND={len(full_buy)}"]
            followups = ["补充关键强起回合的经济明细", "核查失分与强起回合的对应关系"]

    # 3. 关键局势反转
    elif intent in {"MOMENTUM_ANALYSIS", "MOMENTUM_SHIFT"}:
        swings = get_list("ROUND_SWING")
        any_change = any(_swing_changes_winner(f) for f in swings) or len(swings) > 0
        if any_change:
            verdict = "YES"
            claim = "比赛中出现过关键的局势反转"
            confidence = 0.78
            support = _support_strings(swings, bounds=bounds)
        else:
            verdict = "NO"
            claim = "未发现能改变局势的反转"
            confidence = 0.45
            counter = ["ROUND_SWING=0"]
            followups = ["检查关键局的开局/收官表现"]

    # 4. 偶发 or 反复
    elif intent in {"STABILITY_ANALYSIS", "STABILITY_CHECK"}:
        swings = get_list("ROUND_SWING")
        repeated = len(swings) >= 3 and _swings_across_segments(swings)
        if repeated:
            verdict = "YES"
            claim = "局势反转在多局段反复出现"
            confidence = 0.76
            support = _support_strings(swings, bounds=bounds)
        else:
            verdict = "NO"
            claim = "局势反转更像偶发事件"
            confidence = 0.52 if swings else 0.4
            support = _support_strings(swings, bounds=bounds)
            if not swings:
                counter = ["未提炼到 ROUND_SWING"]
            else:
                counter = ["集中于单一局段，缺少跨局分布"]
            followups = ["补充其他地图/局段的 swing 事件"]

    # 5. 经济崩盘起点分析
    elif intent == "COLLAPSE_ONSET_ANALYSIS":
        eco = get_list("ECO_COLLAPSE_SEQUENCE")
        swings = get_list("ROUND_SWING")
        if eco:
            verdict = "YES"
            claim = "出现过经济崩盘/断档的起点，需要控制经济节奏"
            confidence = 0.78
            support = _support_strings(eco, bounds=bounds)
            counter = _support_strings(swings, bounds=bounds)
        elif swings:
            verdict = "INSUFFICIENT"
            claim = "有局势波动，但尚不足以定位经济崩盘起点"
            confidence = 0.45
            support = _support_strings(swings, bounds=bounds)
            followups = ["补充经济明细（loadout/money）以定位崩盘回合"]
        else:
            verdict = "INSUFFICIENT"
            claim = "缺少经济崩盘相关事件"
            confidence = 0.3
            counter = ["ECO_COLLAPSE_SEQUENCE=0", "ROUND_SWING=0"]
            followups = ["补充经济事件文件", "核查关键输分后的经济状态"]

    # 6. 阶段对比（上半/下半/节奏）
    elif intent == "PHASE_COMPARISON":
        swings = get_list("ROUND_SWING")
        hrs = get_list("HIGH_RISK_SEQUENCE")
        repeated = _swings_across_segments(swings)
        if repeated or len(hrs) >= 2:
            verdict = "YES"
            claim = "不同阶段的局势波动差异明显"
            confidence = 0.7
            # Enforce max_findings_per_intent
            support = _support_strings(swings, limit=1, bounds=bounds) + _support_strings(hrs, limit=1, bounds=bounds)
        elif swings:
            verdict = "INSUFFICIENT"
            claim = "有波动但未见明显阶段差异"
            confidence = 0.45
            support = _support_strings(swings, bounds=bounds)
            followups = ["按上/下半场拆分 swing 事件", "补充更多局段样本"]
        else:
            verdict = "INSUFFICIENT"
            claim = "缺少可用于阶段对比的 swing 事件"
            confidence = 0.3
            counter = ["ROUND_SWING=0"]

    # 7. 战术决策评估（force/半起等）
    elif intent == "TACTICAL_DECISION_EVAL":
        force_buy = get_list("FORCE_BUY_ROUND")
        full_buy = get_list("FULL_BUY_ROUND")
        swings = get_list("ROUND_SWING")
        if force_buy:
            verdict = "YES"
            claim = "存在关键战术起买决策，需复盘其收益/风险"
            confidence = 0.7
            support = _support_strings(force_buy, bounds=bounds)
            counter = _support_strings(swings, bounds=bounds)
        elif full_buy:
            verdict = "NO"
            claim = "以常规满购买为主，未见异常战术决策"
            confidence = 0.5
            support = _support_strings(full_buy, bounds=bounds)
        else:
            verdict = "INSUFFICIENT"
            claim = "缺少可评估的战术决策事件"
            confidence = 0.3
            counter = ["FORCE_BUY_ROUND=0", "FULL_BUY_ROUND=0"]
            followups = ["补充关键局的起买/半起信息"]

    # 8. 执行 vs 战略匹配
    elif intent == "EXECUTION_VS_STRATEGY":
        obj_loss = get_list("OBJECTIVE_LOSS_CHAIN")
        swings = get_list("ROUND_SWING")
        if obj_loss:
            verdict = "YES"
            claim = "战略意图可能未被执行到位（连续目标失守）"
            confidence = 0.72
            support = _support_strings(obj_loss, bounds=bounds)
            counter = _support_strings(swings, bounds=bounds)
        elif len(swings) >= 2:
            verdict = "INSUFFICIENT"
            claim = "有局势波动，但缺少目标层面的失守证据"
            confidence = 0.45
            support = _support_strings(swings, bounds=bounds)
            followups = ["补充目标/据点失守的记录"]
        else:
            verdict = "INSUFFICIENT"
            claim = "缺少执行与战略匹配度的线索"
            confidence = 0.3
            counter = ["OBJECTIVE_LOSS_CHAIN=0", "ROUND_SWING<2"]

    # 9. 地图弱点/薄弱点
    elif intent == "MAP_WEAK_POINT":
        hrs = get_list("HIGH_RISK_SEQUENCE")
        obj_loss = get_list("OBJECTIVE_LOSS_CHAIN")
        if hrs or obj_loss:
            verdict = "YES"
            claim = "存在可疑的地图薄弱点/失守区域"
            confidence = 0.65
            # Enforce max_findings_per_intent
            support = _support_strings(hrs, limit=1, bounds=bounds) + _support_strings(obj_loss, limit=1, bounds=bounds)
        else:
            verdict = "INSUFFICIENT"
            claim = "未找到明确的地图薄弱点"
            confidence = 0.32
            counter = ["HIGH_RISK_SEQUENCE=0", "OBJECTIVE_LOSS_CHAIN=0"]
            followups = ["补充分区/点位失守的事件", "对比攻防两侧表现"]

    # 10. 回合拆解
    elif intent == "ROUND_BREAKDOWN":
        swings = get_list("ROUND_SWING")
        force_buy = get_list("FORCE_BUY_ROUND")
        if swings:
            verdict = "YES"
            claim = "关键回合拆解可揭示局势转折点"
            confidence = 0.66
            support = _support_strings(swings, bounds=bounds)
            counter = _support_strings(force_buy, bounds=bounds)
        elif force_buy:
            verdict = "INSUFFICIENT"
            claim = "有战术起买，但缺少回合势头波动信息"
            confidence = 0.4
            support = _support_strings(force_buy, bounds=bounds)
            followups = ["补充 swing/关键击杀事件"]
        else:
            verdict = "INSUFFICIENT"
            claim = "缺少可拆解的回合事件"
            confidence = 0.3
            counter = ["ROUND_SWING=0", "FORCE_BUY_ROUND=0"]

    else:
        claim = "缺少对应规则，无法生成结论"
        verdict = "INSUFFICIENT"
        confidence = 0.2
        followups = ["补充意图映射或规则"]

    # Enforce global bounds on outputs
    support = support[:bounds.max_support_facts]
    counter = counter[:bounds.max_counter_facts]
    followups = _limit_followups(followups, bounds=bounds)

    return AnswerSynthesisResult(
        claim=claim,
        verdict=verdict,
        support_facts=support,
        counter_facts=counter,
        confidence=round(confidence, 2),
        followups=followups,
    )


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
