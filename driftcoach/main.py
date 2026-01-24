import json
from pathlib import Path

from driftcoach.analysis.registry import AnalysisRegistry
from driftcoach.analysis.trigger import is_eligible
from driftcoach.analysis.methods.econ_cascade import EconCascade
from driftcoach.analysis.methods.free_death import FreeDeathImpact
from driftcoach.analysis.methods.objective_fail import ObjectiveFail
from driftcoach.core.state import State


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


def main() -> None:
    run_analysis()


if __name__ == "__main__":
    main()
