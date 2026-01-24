from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class DerivedFact:
    fact_type: str
    value: float
    baseline: Optional[float]
    sample_size: int
    metadata: Dict[str, Any] = field(default_factory=dict)
