import { describe, it, expect } from "vitest";
import { renderWithLLM } from "../client";
import { VALORANT_PROFILE } from "../profiles";

describe("LLM fallback", () => {
  it("returns template when API key missing", async () => {
    const template = "template-fallback";
    const result = await renderWithLLM(
      {
        gameId: "valorant",
        gameProfile: VALORANT_PROFILE,
        intent: "RESOURCE_SNOWBALL",
        structuredFacts: { claim: "demo" },
        context: { value: 0.2, baseline: 0.6, sampleSize: 10, confidence: 0.5 },
      },
      template
    );

    expect(result.usedLLM).toBe(false);
    expect(result.text).toBe(template);
  });
});