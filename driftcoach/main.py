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


def run_analysis() -> None:
    registry = build_registry()
    states = load_states()
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
        _build_outputs(states, derived_facts)
    else:
        print("No derived facts generated; skip structured outputs")


def _build_outputs(states: list[State], derived_facts):
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
        print(f"[INSIGHT] {insight}")

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
        print(f"[REVIEW] {review}")

    # What-if outcome (stub) using simple heuristic
    if states:
        state_for_what_if = states[-1].state_id
        actions = [Action.SAVE, Action.RETAKE]
        outcomes = {
            Action.SAVE: {"win_prob": 0.60},
            Action.RETAKE: {"win_prob": 0.25},
        }
        what_if = WhatIfOutcome.build(
            state=state_for_what_if,
            actions=actions,
            outcomes=outcomes,
            confidence=0.7,
        )
        print(f"[WHAT-IF] {what_if}")


def main() -> None:
    run_analysis()


if __name__ == "__main__":
    main()
