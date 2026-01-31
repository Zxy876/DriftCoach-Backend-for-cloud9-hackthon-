import { describe, it, expect } from "vitest";
import { renderTemplate } from "../templates";
import { VALORANT_PROFILE, LOL_PROFILE } from "../profiles";

describe("renderTemplate snapshot", () => {
  it("RESOURCE_SNOWBALL in Valorant includes滚雪球", () => {
    const text = renderTemplate("RESOURCE_SNOWBALL", VALORANT_PROFILE, { value: 0.2, baseline: 0.6, sampleSize: 20 });
    expect(text).toContain("滚雪球");
  });

  it("WEAK_SIGNAL_LOW_CONFIDENCE carries uncertainty hint", () => {
    const text = renderTemplate("WEAK_SIGNAL_LOW_CONFIDENCE", VALORANT_PROFILE, { confidence: 0.2 });
    expect(text).toContain("样本");
  });

  it("MID_GAME_TIMING_PRESSURE in LoL uses中期决策 wording", () => {
    const text = renderTemplate("MID_GAME_TIMING_PRESSURE", LOL_PROFILE, { value: 0.4, baseline: 0.5, sampleSize: 15 });
    expect(text).toMatch(/中期|mid/i);
  });
});