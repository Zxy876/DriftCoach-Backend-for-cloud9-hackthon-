from typing import Protocol

from driftcoach.outputs.insight import Insight
from driftcoach.outputs.what_if import WhatIfOutcome


class Renderer(Protocol):
    def render_insight(self, insight: Insight) -> str:
        ...

    def render_what_if(self, what_if: WhatIfOutcome) -> str:
        ...
