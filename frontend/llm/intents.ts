import type { DerivedFact } from "../types/insight";
import type { WhatIfOutcome } from "../types/whatif";

export type NarrativeIntent =
  | "RESOURCE_SNOWBALL"
  | "OPENING_PHASE_INSTABILITY"
  | "MID_GAME_TIMING_PRESSURE"
  | "OBJECTIVE_TRADE_INEFFICIENCY"
  | "HIGH_VARIANCE_PATTERN"
  | "WEAK_SIGNAL_LOW_CONFIDENCE";

type IntentSource = "insight" | "review" | "whatif";

function hasWeakConfidence(confidence: number | undefined): boolean {
  return confidence !== undefined && confidence < 0.4;
}

function pickByFact(fact: DerivedFact): NarrativeIntent | null {
  const delta = fact.baseline !== null && fact.baseline !== undefined ? fact.value - fact.baseline : undefined;
  const factType = fact.factType.toLowerCase();
  if (delta !== undefined && delta <= -0.2) {
    if (factType.includes("pistol") || factType.includes("opening")) return "OPENING_PHASE_INSTABILITY";
    if (factType.includes("econom") || factType.includes("econ")) return "RESOURCE_SNOWBALL";
    return "OBJECTIVE_TRADE_INEFFICIENCY";
  }
  if (delta !== undefined && Math.abs(delta) >= 0.25 && fact.sampleSize >= 10) {
    return "HIGH_VARIANCE_PATTERN";
  }
  return null;
}

export function deriveIntentFromFacts(facts: DerivedFact[], confidence?: number, source: IntentSource = "insight"):
  NarrativeIntent {
  if (hasWeakConfidence(confidence)) return "WEAK_SIGNAL_LOW_CONFIDENCE";
  for (const fact of facts) {
    const intent = pickByFact(fact);
    if (intent) return intent;
  }
  if (source === "whatif") return "MID_GAME_TIMING_PRESSURE";
  return "HIGH_VARIANCE_PATTERN";
}

export function deriveIntentFromWhatIf(payload: WhatIfOutcome): NarrativeIntent {
  if (hasWeakConfidence(payload.confidence)) return "WEAK_SIGNAL_LOW_CONFIDENCE";
  const values = Object.values(payload.outcomes).map((o) => o.win_prob).filter((v): v is number => v !== null);
  const span = values.length ? Math.max(...values) - Math.min(...values) : 0;
  if (span >= 0.2) return "MID_GAME_TIMING_PRESSURE";
  if (values.length && Math.max(...values) < 0.4) return "RESOURCE_SNOWBALL";
  return "HIGH_VARIANCE_PATTERN";
}