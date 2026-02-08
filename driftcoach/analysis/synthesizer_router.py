"""
Answer Synthesizer Router (Combine phase).

Routes intents to their respective handlers using divide-and-conquer.
"""

from typing import List
from driftcoach.analysis.intent_handlers import (
    IntentHandler,
    HandlerContext,
    RiskAssessmentHandler,
    EconomicCounterfactualHandler,
    MomentumAnalysisHandler,
    StabilityAnalysisHandler,
    CollapseOnsetHandler,
    FallbackHandler,
)
from driftcoach.config.bounds import SystemBounds, DEFAULT_BOUNDS
from driftcoach.analysis.answer_synthesizer import (
    AnswerInput,
    AnswerSynthesisResult,
)


class AnswerSynthesizer:
    """
    Divide-and-conquer answer synthesizer.

    Architecture:
    - Divide: Route intent to appropriate handler
    - Conquer: Handler processes independently
    - Combine: Return unified result format

    Benefits:
    - O(1) intent routing (vs O(n) if-elif chain)
    - Independent testing per handler
    - Easy to add new intents
    - Each handler respects global bounds
    """

    def __init__(self, handlers: List[IntentHandler] | None = None):
        """
        Initialize synthesizer with intent handlers.

        Args:
            handlers: List of intent handlers (uses default if None)
        """
        self.handlers = handlers or self._default_handlers()

    def _default_handlers(self) -> List[IntentHandler]:
        """
        Default handler registry.

        Handlers are tried in order; first match wins.
        Fallback handler must be last.
        """
        return [
            # Specific handlers (tried first)
            RiskAssessmentHandler(),
            EconomicCounterfactualHandler(),
            MomentumAnalysisHandler(),
            StabilityAnalysisHandler(),
            CollapseOnsetHandler(),
            # TODO: Add remaining handlers
            # PhaseComparisonHandler(),
            # TacticalDecisionHandler(),
            # ExecutionStrategyHandler(),
            # MapWeakPointHandler(),
            # RoundBreakdownHandler(),

            # Fallback handler (must be last)
            FallbackHandler(),
        ]

    def synthesize(
        self,
        inp: AnswerInput,
        bounds: SystemBounds = DEFAULT_BOUNDS
    ) -> AnswerSynthesisResult:
        """
        Synthesize answer using divide-and-conquer.

        Algorithm:
        1. Divide: Route to appropriate handler
        2. Conquer: Handler processes independently
        3. Combine: Return unified format

        Args:
            inp: Answer input
            bounds: System bounds to enforce

        Returns:
            Answer synthesis result
        """
        intent = (inp.intent or "").upper()

        # Create handler context
        ctx = HandlerContext(
            input=inp,
            bounds=bounds,
            intent=intent
        )

        # Divide + Conquer: Find and execute handler
        for handler in self.handlers:
            if handler.can_handle(intent):
                # Each handler processes independently
                result = handler.process(ctx)

                # Enforce global bounds on outputs
                result.support_facts = result.support_facts[:bounds.max_support_facts]
                result.counter_facts = result.counter_facts[:bounds.max_counter_facts]
                result.followups = result.followups[:bounds.max_followup_questions]

                return result

        # Should never reach here (fallback handler handles everything)
        raise RuntimeError(f"No handler found for intent: {intent}")

    def add_handler(self, handler: IntentHandler, position: int | None = None):
        """
        Add a new handler to the registry.

        Args:
            handler: Handler to add
            position: Position to insert (None = append)
        """
        if position is None:
            self.handlers.append(handler)
        else:
            self.handlers.insert(position, handler)

    def remove_handler(self, handler_class: type) -> bool:
        """
        Remove a handler by class type.

        Args:
            handler_class: Class of handler to remove

        Returns:
            True if removed, False if not found
        """
        for i, handler in enumerate(self.handlers):
            if isinstance(handler, handler_class):
                # Never remove fallback handler
                if isinstance(handler, FallbackHandler):
                    return False
                self.handlers.pop(i)
                return True
        return False


# Backward compatibility wrapper
def synthesize_answer(
    inp: AnswerInput,
    bounds: SystemBounds = DEFAULT_BOUNDS,
) -> AnswerSynthesisResult:
    """
    Backward-compatible wrapper for synthesize_answer.

    Delegates to the new divide-and-conquer synthesizer.
    """
    synthesizer = AnswerSynthesizer()
    return synthesizer.synthesize(inp, bounds=bounds)
