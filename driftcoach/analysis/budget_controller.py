"""
BudgetController: CLRS Chapter 5 - Probabilistic Analysis and Randomized Algorithms

Purpose: Rational stopping under uncertainty.

BudgetController answers one question:
  "Is it worth continuing to mine facts?"

It does NOT:
  - Judge fact content correctness
  - Select optimal facts
  - Calculate optimal n in advance

It ONLY:
  - Controls CONTINUE / STOP decision
  - Ensures rational stopping under uncertainty

Theory Anchor (CLRS Ch 5):
  - Judgment event A (e.g., "Is this a high-risk match?")
  - Indicator: I{A} ∈ {0, 1}
  - Expectation: E[I{A}] = P(A) ≈ confidence

Confidence is the engineering mapping of expectation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


# =============================================================================
# 1. BudgetState (Current State of Mining Process)
# =============================================================================

@dataclass
class BudgetState:
    """
    Current state of the fact-mining process.

    Attributes:
        current_confidence: Current estimated confidence (E[I{A}])
        remaining_budget: Remaining mining steps (from L3 bounds)
        confidence_history: History of confidence values (for convergence check)
        facts_mined: Number of facts already mined
    """
    current_confidence: float
    remaining_budget: int
    confidence_history: List[float]
    facts_mined: int = 0

    def update_confidence(self, new_confidence: float) -> None:
        """
        Update confidence and record in history.

        Args:
            new_confidence: New confidence value after mining a fact
        """
        self.current_confidence = new_confidence
        self.confidence_history.append(new_confidence)


# =============================================================================
# 2. ConfidenceTarget (User-Defined Stopping Criteria)
# =============================================================================

@dataclass
class ConfidenceTarget:
    """
    User-defined confidence target and constraints.

    IMPORTANT:
        Target confidence comes from user/coach, NOT from model inference.
        This is an external constraint (CLRS Ch 5 principle).

    Attributes:
        target_confidence: Desired confidence threshold (e.g., 0.7)
        min_steps: Minimum steps before allowing early stop (premature stop guard)
        convergence_window: Window size for convergence check (k)
        convergence_epsilon: Threshold for "converged" (ε)
    """
    target_confidence: float
    min_steps: int = 2
    convergence_window: int = 3
    convergence_epsilon: float = 0.05


# =============================================================================
# 3. BudgetController (Rational Stopping Logic)
# =============================================================================

class BudgetController:
    """
    CLRS Chapter 5 - Rational stopping under uncertainty.

    Core Principle:
        BudgetController does NOT decide "truth".
        It decides: "Is it worth continuing to search for truth?"

    Stopping Rules (Union - stop if ANY condition met):
        1. Achieved target confidence (most important)
        2. Budget exhausted (L3 constraint)
        3. Confidence converged (Chapter 5 essence)
    """

    def should_continue(
        self,
        state: BudgetState,
        target: ConfidenceTarget
    ) -> bool:
        """
        Decide whether to continue mining facts.

        Returns:
            True = CONTINUE mining
            False = STOP (return to DecisionMapper)

        Args:
            state: Current budget state
            target: User-defined confidence target
        """
        # Rule 1: Achieved target confidence (MOST IMPORTANT)
        if self._is_target_achieved(state, target):
            return False

        # Rule 2: Budget exhausted (L3 constraint)
        if self._is_budget_exhausted(state):
            return False

        # Rule 3: Confidence converged (Chapter 5 essence)
        if self._is_converged(state, target):
            # Only stop if we've done minimum steps
            if state.facts_mined >= target.min_steps:
                return False

        # Default: CONTINUE
        return True

    def _is_target_achieved(
        self,
        state: BudgetState,
        target: ConfidenceTarget
    ) -> bool:
        """
        Check if target confidence is achieved.

        Rule: current_confidence >= target_confidence
        """
        return state.current_confidence >= target.target_confidence

    def _is_budget_exhausted(self, state: BudgetState) -> bool:
        """
        Check if mining budget is exhausted.

        Rule: remaining_budget <= 0
        """
        return state.remaining_budget <= 0

    def _is_converged(
        self,
        state: BudgetState,
        target: ConfidenceTarget
    ) -> bool:
        """
        Check if confidence has converged (stable).

        Rule: Last k confidence values change < ε

        This is the ESSENCE of Chapter 5:
        "Stop when marginal gain is negligible."
        """
        if len(state.confidence_history) < target.convergence_window:
            return False

        # Get last k confidence values
        recent = state.confidence_history[-target.convergence_window:]

        # Check if all changes are < ε
        for i in range(1, len(recent)):
            if abs(recent[i] - recent[i-1]) >= target.convergence_epsilon:
                return False

        return True


# =============================================================================
# 4. Factory / Helper Functions
# =============================================================================

def create_initial_state(
    initial_confidence: float = 0.0,
    budget: int = 5
) -> BudgetState:
    """
    Create initial BudgetState for a new mining process.

    Args:
        initial_confidence: Starting confidence (usually 0.0 or 0.3)
        budget: Total mining budget (from L3 bounds)

    Returns:
        Initial BudgetState
    """
    return BudgetState(
        current_confidence=initial_confidence,
        remaining_budget=budget,
        confidence_history=[initial_confidence],
        facts_mined=0
    )


def create_default_target(
    target_confidence: float = 0.7
) -> ConfidenceTarget:
    """
    Create default ConfidenceTarget.

    Args:
        target_confidence: User's desired confidence threshold

    Returns:
        Default ConfidenceTarget with reasonable defaults
    """
    return ConfidenceTarget(
        target_confidence=target_confidence,
        min_steps=2,           # Prevent premature stop
        convergence_window=3,  # Check last 3 steps
        convergence_epsilon=0.05  # 5% change threshold
    )
