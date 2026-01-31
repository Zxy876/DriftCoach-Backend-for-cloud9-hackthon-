import { describe, it, expect } from "vitest";
import { deriveIntentFromFacts, deriveIntentFromWhatIf } from "../intents";
import type { DerivedFact } from "../../types/insight";
import type { WhatIfOutcome } from "../../types/whatif";

const fact = (overrides: Partial<DerivedFact>): DerivedFact => ({
  factType: "generic",
  value: 0.3,
  baseline: 0.5,
  sampleSize: 20,
  ...overrides,
});

describe("deriveIntentFromFacts", () => {
  it("returns WEAK_SIGNAL_LOW_CONFIDENCE when confidence is low", () => {
    const intent = deriveIntentFromFacts([fact({})], 0.2, "insight");
    expect(intent).toBe("WEAK_SIGNAL_LOW_CONFIDENCE");
  });

  it("detects opening instability when pistol/opening drops", () => {
    const intent = deriveIntentFromFacts([fact({ factType: "pistol_round", value: 0.2, baseline: 0.6 })], 0.8, "insight");
    expect(intent).toBe("OPENING_PHASE_INSTABILITY");
  });

  it("falls back to HIGH_VARIANCE_PATTERN when no rule matches", () => {
    const intent = deriveIntentFromFacts([fact({ value: 0.52, baseline: 0.5 })], 0.8, "insight");
    expect(intent).toBe("HIGH_VARIANCE_PATTERN");
  });
});

describe("deriveIntentFromWhatIf", () => {
  const baseWhatIf: WhatIfOutcome = {
    state: "S1",
    actions: ["SAVE", "RETAKE"],
    outcomes: {
      SAVE: { win_prob: 0.6, support: 10 },
      RETAKE: { win_prob: 0.3, support: 10 },
      FORCE: { win_prob: null, support: 0 },
      ECO: { win_prob: null, support: 0 },
      CONTEST: { win_prob: null, support: 0 },
      TRADE: { win_prob: null, support: 0 },
    },
    confidence: 0.7,
  };

  it("uses MID_GAME_TIMING_PRESSURE when action span is large", () => {
    const intent = deriveIntentFromWhatIf(baseWhatIf);
    expect(intent).toBe("MID_GAME_TIMING_PRESSURE");
  });

  it("falls back to WEAK_SIGNAL_LOW_CONFIDENCE when confidence low", () => {
    const intent = deriveIntentFromWhatIf({ ...baseWhatIf, confidence: 0.1 });
    expect(intent).toBe("WEAK_SIGNAL_LOW_CONFIDENCE");
  });
});