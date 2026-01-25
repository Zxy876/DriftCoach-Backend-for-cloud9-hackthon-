import type { Insight } from "../types/insight";
import type { ReviewAgendaItem } from "../types/review";
import type { WhatIfOutcome } from "../types/whatif";

export type RenderMode = "off" | "llm" | "template";

export type RenderOptions = {
  mode: RenderMode;
};

const fallback = {
  insight: "基于历史相似状态的统计解释（LLM 关闭或失败，使用模板）",
  review: "复盘议题依据已有证据与样本量，非建议性结论",
  whatIf: "基于相似状态的经验胜率比较，非行动建议",
};

export function renderInsight(insight: Insight, opts: RenderOptions): string {
  if (opts.mode === "off") return "(LLM off)";
  if (opts.mode === "template") return fallback.insight;
  // LLM mode: call backend proxy here; placeholder
  return fallback.insight;
}

export function renderReview(item: ReviewAgendaItem, opts: RenderOptions): string {
  if (opts.mode === "off") return "(LLM off)";
  if (opts.mode === "template") return fallback.review;
  return fallback.review;
}

export function renderWhatIf(whatIf: WhatIfOutcome, opts: RenderOptions): string {
  if (opts.mode === "off") return "(LLM off)";
  if (opts.mode === "template") return fallback.whatIf;
  return fallback.whatIf;
}
