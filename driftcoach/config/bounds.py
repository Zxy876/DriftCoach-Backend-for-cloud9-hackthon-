"""
Hard bounds for DriftCoach system.

These are enforced constraints to prevent unbounded computation and output.
Goal: Keep F(x) computable and focused on actionable insights.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class SystemBounds:
    """
    Hard bounds for system behavior.

    These are NOT soft recommendations - they are enforced constraints.
    """
    # Intent decomposition bounds
    max_sub_intents: int = 3  # Maximum number of sub-intents to pursue per query

    # Findings generation bounds
    max_findings_per_intent: int = 2  # Maximum findings to extract per intent
    max_findings_total: int = 5  # Maximum total findings across all intents

    # Evidence/fact bounds
    max_support_facts: int = 3  # Maximum supporting facts to show
    max_counter_facts: int = 3  # Maximum counter-examples to show
    max_followup_questions: int = 3  # Maximum follow-up questions to suggest

    # Mining bounds
    max_mining_patches: int = 3  # Maximum data mining patches per query
    max_series_to_enumerate: int = 200  # Maximum series to enumerate in one patch
    max_retry_attempts: int = 2  # Maximum retry attempts for failed queries

    # Analysis bounds
    max_analysis_methods_per_intent: int = 4  # Maximum analysis methods to run per intent
    max_ml_similar_states: int = 5  # Maximum similar states to retrieve via ML

    # Output bounds
    max_narrative_length: int = 2000  # Maximum characters in narrative output
    max_rationale_length: int = 600  # Maximum characters in rationale


# Global instance
DEFAULT_BOUNDS = SystemBounds()


def enforce_bounds_on_facts(
    facts: List[Dict],
    intent: Optional[str] = None,
    bounds: SystemBounds = DEFAULT_BOUNDS,
) -> List[Dict]:
    """
    Enforce max_findings bounds on a list of facts.

    Args:
        facts: List of fact dictionaries
        intent: Optional intent type (for per-intent limits)
        bounds: System bounds to enforce

    Returns:
        Truncated list of facts respecting the bounds
    """
    if not facts:
        return []

    # Apply per-intent limit
    max_per_intent = bounds.max_findings_per_intent
    limited_by_intent = facts[:max_per_intent]

    return limited_by_intent


def enforce_bounds_on_intents(
    intents: List[str],
    bounds: SystemBounds = DEFAULT_BOUNDS,
) -> List[str]:
    """
    Enforce max_sub_intents bound on a list of intents.

    Args:
        intents: List of intent strings
        bounds: System bounds to enforce

    Returns:
        Truncated list of intents respecting the bound
    """
    if not intents:
        return []

    return intents[:bounds.max_sub_intents]


def calculate_finding_quota(
    num_intents: int,
    bounds: SystemBounds = DEFAULT_BOUNDS,
) -> Dict[str, int]:
    """
    Calculate how many findings each intent can generate, given total quota.

    Distributes max_findings_total across intents fairly.

    Args:
        num_intents: Number of intents being processed
        bounds: System bounds

    Returns:
        Dictionary with per-intent quota and total quota
    """
    if num_intents == 0:
        return {"per_intent": 0, "total": 0}

    # Fair distribution: min(per_intent_limit, total // num_intents)
    per_intent = min(
        bounds.max_findings_per_intent,
        bounds.max_findings_total // num_intents,
    )

    # Ensure at least 1 per intent if total allows
    if per_intent == 0 and bounds.max_findings_total >= num_intents:
        per_intent = 1

    return {
        "per_intent": per_intent,
        "total": min(bounds.max_findings_total, per_intent * num_intents),
    }


def check_bounds_violation(
    actual_count: int,
    bound_name: str,
    bounds: SystemBounds = DEFAULT_BOUNDS,
) -> tuple[bool, str]:
    """
    Check if a count violates a bound.

    Args:
        actual_count: Actual count of items
        bound_name: Name of the bound to check (e.g., "max_sub_intents")
        bounds: System bounds

    Returns:
        (is_violation, message) tuple
    """
    bound_value = getattr(bounds, bound_name, None)
    if bound_value is None:
        return False, f"Unknown bound: {bound_name}"

    if actual_count > bound_value:
        return True, f"{bound_name}: {actual_count} > {bound_value}"

    return False, ""


class BoundEnforcer:
    """
    Context manager for enforcing bounds during computation.

    Usage:
        with BoundEnforcer(bounds=DEFAULT_BOUNDS) as enforcer:
            enforcer.check_sub_intent_count(current_intents)
            # ... do work ...
            enforcer.check_finding_count(current_findings)
    """

    def __init__(self, bounds: SystemBounds = DEFAULT_BOUNDS):
        self.bounds = bounds
        self.violations: List[str] = []

    def check_sub_intent_count(self, count: int) -> bool:
        """Check if sub-intent count is within bounds."""
        is_violation, msg = check_bounds_violation(count, "max_sub_intents", self.bounds)
        if is_violation:
            self.violations.append(msg)
        return not is_violation

    def check_finding_count(self, count: int) -> bool:
        """Check if finding count is within bounds."""
        is_violation, msg = check_bounds_violation(count, "max_findings_total", self.bounds)
        if is_violation:
            self.violations.append(msg)
        return not is_violation

    def get_per_intent_quota(self, num_intents: int) -> int:
        """Get per-intent finding quota."""
        quota = calculate_finding_quota(num_intents, self.bounds)
        return quota["per_intent"]

    def has_violations(self) -> bool:
        """Check if any violations occurred."""
        return len(self.violations) > 0

    def get_violations(self) -> List[str]:
        """Get list of violation messages."""
        return self.violations.copy()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.has_violations():
            # Log violations but don't raise (bounds are enforced, not just checked)
            import warnings
            warnings.warn(f"System bounds violations: {self.violations}")
        return False
