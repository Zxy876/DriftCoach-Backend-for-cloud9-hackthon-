import argparse
import json
from pathlib import Path

from driftcoach.analysis.registry import AnalysisRegistry
from driftcoach.analysis.trigger import is_eligible
from driftcoach.analysis.methods.econ_cascade import EconCascade
from driftcoach.analysis.methods.free_death import FreeDeathImpact
from driftcoach.analysis.methods.objective_fail import ObjectiveFail
from driftcoach.core.state import State
from driftcoach.core.action import Action
from driftcoach.outputs.insight import Insight
from driftcoach.outputs.review_item import ReviewAgendaItem
from driftcoach.outputs.what_if import WhatIfOutcome
from driftcoach.llm.interpreter import interpret
from driftcoach.ml.state_similarity import StateSimilarity


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def build_registry() -> AnalysisRegistry:
    registry = AnalysisRegistry()
    registry.register(FreeDeathImpact())
    registry.register(EconCascade())
    registry.register(ObjectiveFail())
    return registry


def load_states() -> list[State]:
    states_path = FIXTURES_DIR / "states.json"
    with states_path.open() as f:
        data = json.load(f)
    return [State.from_dict(item) for item in data]


def load_actions() -> dict[str, Action]:
    actions_path = FIXTURES_DIR / "actions.json"
    if not actions_path.exists():
        return {}
    with actions_path.open() as f:
        records = json.load(f)
    mapping: dict[str, Action] = {}
    for rec in records:
        try:
            mapping[rec["state_id"]] = Action(rec["action"])
        except Exception:
            continue
    return mapping


def run_analysis(explain: bool = False) -> None:
    registry = build_registry()
    states = load_states()
    actions = load_actions()
    print(f"Loaded {len(states)} states from fixtures")
    derived_facts = []
    for method in registry.all():
        eligible = is_eligible(method, states)
        if not eligible:
            print(f"[SKIP] {method.name} not eligible (requirements/trigger not met)")
            continue
        result = method.run(states)
        if result is None:
            print(f"[NO RESULT] {method.name} returned no derived fact")
            continue
        baseline_str = f"{result.baseline:.2f}" if result.baseline is not None else "n/a"
        print(
            f"[OK] {method.name} -> {result.fact_type} "
            f"value={result.value:.2f} baseline={baseline_str} samples={result.sample_size}"
        )
        derived_facts.append((method.name, result))

    if derived_facts:
        outputs = _build_outputs(states, derived_facts, actions)
        _print_demo(outputs, explain=explain)
    else:
        print("No derived facts generated; skip structured outputs")


def _build_outputs(states: list[State], derived_facts, action_map: dict[str, Action]):
    outputs = []
    # Insight from free_death_impact if available
    fd_fact = next((f for name, f in derived_facts if name == "free_death_impact"), None)
    if fd_fact:
        insight = Insight.build(
            subject="player:mock",
            claim="Free deaths correlate with round losses",
            derived_facts=[fd_fact],
            confidence=min(1.0, fd_fact.metadata.get("confidence", 0.0)),
            failure_conditions=["ult_advantage >= 2"],
        )
        outputs.append(insight)

    # Review Agenda from econ_cascade if available
    econ_fact = next((f for name, f in derived_facts if name == "econ_cascade"), None)
    if econ_fact:
        involved_states = [s.state_id for s in states[:2]] or ["unknown"]
        review = ReviewAgendaItem.build(
            match_id="M_MOCK",
            topic="Econ cascade after disadvantaged rounds",
            states_involved=involved_states,
            evidence=[econ_fact],
            confidence=min(1.0, econ_fact.metadata.get("confidence", 0.0)),
        )
        outputs.append(review)

    # What-if outcome via StateSimilarity top-K bucketed by action
    if states:
        what_if_obj = _build_what_if_with_similarity(states, action_map)
        if what_if_obj:
            outputs.append(what_if_obj)

    return outputs


def _build_what_if_with_similarity(states: list[State], action_map: dict[str, Action], k: int = 30, alpha: float = 1.0, beta: float = 1.0, min_support: int = 5):
    # Use last state as query; historical pool includes all states
    query_state = states[-1]
    similarity = StateSimilarity(n_components=4, n_neighbors=min(k, len(states)))
    similarity.fit(states)
    neighbor_info = similarity.query(query_state)

    buckets: dict[Action, list[tuple[float, int]]] = {}
    for idx, dist in neighbor_info:
        neighbor = states[idx]
        act = action_map.get(neighbor.state_id)
        if not act:
            continue
        rr = neighbor.extras.get("round_result")
        if rr not in {"WIN", "LOSS"}:
            continue
        win = 1 if rr == "WIN" else 0
        buckets.setdefault(act, []).append((dist, win))

    if not buckets:
        return None

    outcomes: dict[Action, dict[str, float | int | bool | None]] = {}
    confidences: list[float] = []
    for act, samples in buckets.items():
        wins = sum(win for _, win in samples)
        n = len(samples)
        avg_dist = sum(dist for dist, _ in samples) / n if n else 1.0
        sim_score = max(0.0, 1.0 - avg_dist)
        smoothed = (wins + alpha) / (n + alpha + beta) if n else 0.5
        insufficient = n < min_support
        conf = min(1.0, 0.5 * min(1.0, n / k) + 0.5 * sim_score)
        outcomes[act] = {
            "win_prob": None if insufficient else round(smoothed, 3),
            "support": n,
            "insufficient_support": insufficient,
        }
        confidences.append(conf)

    # Only keep actions with some support
    chosen_actions = [a for a in outcomes.keys() if outcomes[a]["support"] > 0]
    if not chosen_actions:
        return None

    overall_conf = min(1.0, sum(confidences) / len(confidences)) if confidences else 0.0
    return WhatIfOutcome.build(
        state=query_state.state_id,
        actions=chosen_actions,
        outcomes=outcomes,
        confidence=overall_conf,
    )


def _print_demo(outputs, explain: bool = False):
    for obj in outputs:
        if isinstance(obj, Insight):
            fact = obj.derived_facts[0]
            baseline_str = f"{fact.baseline:.2f}" if fact.baseline is not None else "n/a"
            delta_str = f"{(fact.value - fact.baseline):.2f}" if fact.baseline is not None else "n/a"
            print("[PLAYER INSIGHT]")
            print(f"  Data: 在条件 {fact.metadata.get('condition', 'unknown')} 下胜率 {fact.value:.2f} (基线 {baseline_str}, 样本 {fact.sample_size})")
            print(f"  Meaning: 偏离 {delta_str}, confidence {obj.confidence:.2f}")
            if obj.failure_conditions:
                print(f"  Notes: 触发失败条件 {', '.join(obj.failure_conditions)}")
            else:
                print("  Notes: -")
            _print_explain(obj, explain)

        elif isinstance(obj, ReviewAgendaItem):
            fact = obj.evidence[0]
            baseline_str = f"{fact.baseline:.2f}" if fact.baseline is not None else "n/a"
            states_involved = ", ".join(obj.states_involved)
            print("[POST-MATCH REVIEW]")
            print(f"  Data: {fact.fact_type} = {fact.value:.2f} (基线 {baseline_str}, 样本 {fact.sample_size})")
            print(f"  Agenda item: {obj.topic}")
            print(f"  Evidence states: {states_involved}")
            print(f"  Notes: confidence {obj.confidence:.2f}")
            _print_explain(obj, explain)

        elif isinstance(obj, WhatIfOutcome):
            print("[WHAT-IF ANALYSIS]")
            print(f"  State: {obj.state}")
            print("  Counterfactual outcomes (empirical):")
            for act in obj.actions:
                payload = obj.outcomes.get(act, {})
                support = payload.get("support", 0)
                insuff = payload.get("insufficient_support", False)
                win_prob = payload.get("win_prob")
                if insuff or win_prob is None:
                    line = f"    {act.value}: insufficient support (n={support})"
                else:
                    line = f"    {act.value}: p≈{win_prob:.2f} (支持样本 {support})"
                print(line)
            print(f"  Confidence: {obj.confidence:.2f} (样本比例 + 平均相似度)")
            _print_explain(obj, explain)


def _print_explain(obj, explain: bool):
    if not explain:
        return
    explanation = interpret(obj)
    if explanation:
        print(f"  Explain: {explanation}")


def main() -> None:
    parser = argparse.ArgumentParser(description="DriftCoach mock run")
    parser.add_argument("--explain", action="store_true", help="print LLM interpretation text")
    args = parser.parse_args()
    run_analysis(explain=args.explain)


if __name__ == "__main__":
    main()
