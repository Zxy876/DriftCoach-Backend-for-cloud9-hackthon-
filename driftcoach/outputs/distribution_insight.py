from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class DistributionInsight:
    insight_type: str
    axes: List[str]
    summary_ref: str
    confidence: str
    note: str

    @staticmethod
    def build(axes: List[str], summary_ref: str = "context.evidence.summary", confidence: str = "LOW", note: str = "Descriptive; no outcome/stats") -> "DistributionInsight":
        if not axes:
            raise ValueError("axes cannot be empty for distribution insight")
        return DistributionInsight(
            insight_type="DISTRIBUTION_INSIGHT",
            axes=axes,
            summary_ref=summary_ref,
            confidence=confidence,
            note=note,
        )
