import { config, type RenderMode } from "../config";
import type { Insight } from "../types/insight";
import type { ReviewAgendaItem } from "../types/review";
import type { WhatIfOutcome } from "../types/whatif";
import { deriveIntentFromFacts, deriveIntentFromWhatIf, type NarrativeIntent } from "./intents";
import { getGameProfile } from "./profiles";
import { renderTemplate } from "./templates";
import { createTrace, type ExplanationTrace } from "./trace";
import { renderWithLLM } from "./client";

export type RenderOptions = {
  mode?: RenderMode;
  gameId?: string;
  mathMetaphor?: string | null;
};

export type RenderedExplanation = {
  text: string;
  trace: ExplanationTrace;
};

const OFF_TEXT = "(LLM off)";

function resolveMode(mode?: RenderMode): RenderMode {
  if (mode === "off" || mode === "template" || mode === "llm-contextual") return mode;
  return config.renderMode ?? "template";
}

function baseContextFromFact(fact: import("../types/insight").DerivedFact) {
  return {
    value: fact.value,
    baseline: fact.baseline ?? null,
    sampleSize: fact.sampleSize,
  };
}

async function renderByIntent(
  intent: NarrativeIntent,
  structuredFacts: Record<string, unknown>,
  ctx: ReturnType<typeof baseContextFromFact> & { confidence?: number; bestAction?: string; bestWinProb?: number },
  opts: RenderOptions
): Promise<RenderedExplanation> {
  const mode = resolveMode(opts.mode);
  const profile = getGameProfile(opts.gameId ?? config.defaultGameId);
  const template = renderTemplate(intent, profile, ctx);

  if (mode === "off") {
    return {
      text: OFF_TEXT,
      trace: createTrace({ intent, gameProfile: profile.id, renderMode: "off", sourceFields: Object.keys(structuredFacts), fallbackUsed: true }),
    };
  }

  if (mode === "template") {
    return {
      text: template,
      trace: createTrace({ intent, gameProfile: profile.id, renderMode: "template", sourceFields: Object.keys(structuredFacts), fallbackUsed: true }),
    };
  }

  const promptInput = {
    gameId: opts.gameId ?? profile.id,
    gameProfile: profile,
    intent,
    structuredFacts,
    context: ctx,
    mathMetaphor: opts.mathMetaphor ?? null,
  };

  const result = await renderWithLLM({ ...promptInput, gameId: promptInput.gameId }, template);

  return {
    text: result.text,
    trace: createTrace({
      intent,
      gameProfile: profile.id,
      renderMode: mode,
      sourceFields: Object.keys(structuredFacts),
      fallbackUsed: !result.usedLLM,
      message: result.usedLLM ? undefined : "LLM unavailable, template fallback",
    }),
  };
}

export async function renderInsight(insight?: Insight, opts: RenderOptions = {}): Promise<RenderedExplanation> {
  if (!insight) {
    return {
      text: "暂无分析结果",
      trace: createTrace({
        intent: "insight-empty" as any,
        gameProfile: config.defaultGameId,
        renderMode: resolveMode(opts.mode),
        sourceFields: [],
        fallbackUsed: true,
        message: "missing insight payload",
      }),
    };
  }

  if (!Array.isArray(insight.derivedFacts) || insight.derivedFacts.length === 0) {
    return {
      text: "当前问题证据不足（INSUFFICIENT）",
      trace: createTrace({
        intent: "insight-empty" as any,
        gameProfile: config.defaultGameId,
        renderMode: resolveMode(opts.mode),
        sourceFields: [],
        fallbackUsed: true,
        message: "empty derivedFacts",
      }),
    };
  }

  const fact = insight.derivedFacts[0];
  const intent = deriveIntentFromFacts(insight.derivedFacts, insight.confidence, "insight");
  const structuredFacts = {
    subject: insight.subject,
    claim: insight.claim,
    derivedFacts: insight.derivedFacts,
    confidence: insight.confidence,
  };
  return renderByIntent(intent, structuredFacts, { ...baseContextFromFact(fact), confidence: insight.confidence }, opts);
}

export async function renderReview(item: ReviewAgendaItem, opts: RenderOptions): Promise<RenderedExplanation> {
  const fact = item.evidence[0];
  if (!fact) {
    return {
      text: OFF_TEXT,
      trace: createTrace({
        intent: "review-empty" as any,
        gameProfile: config.defaultGameId,
        renderMode: resolveMode(opts.mode),
        sourceFields: [],
        fallbackUsed: true,
        message: "missing evidence for review",
      }),
    };
  }
  const intent = deriveIntentFromFacts(item.evidence, item.confidence, "review");
  const structuredFacts = {
    topic: item.topic,
    evidence: item.evidence,
    confidence: item.confidence,
  };
  return renderByIntent(intent, structuredFacts, { ...baseContextFromFact(fact), confidence: item.confidence }, opts);
}

export async function renderWhatIf(whatIf: WhatIfOutcome, opts: RenderOptions): Promise<RenderedExplanation> {
  const intent = deriveIntentFromWhatIf(whatIf);
  const bestAction = whatIf.actions
    .map((action) => ({ action, winProb: whatIf.outcomes[action].win_prob }))
    .filter((x) => x.winProb !== null)
    .sort((a, b) => (b.winProb ?? 0) - (a.winProb ?? 0))[0];

  const structuredFacts = {
    state: whatIf.state,
    actions: whatIf.actions,
    outcomes: whatIf.outcomes,
    confidence: whatIf.confidence,
  };

  return renderByIntent(
    intent,
    structuredFacts,
    {
      confidence: whatIf.confidence,
      bestAction: bestAction?.action,
      bestWinProb: bestAction?.winProb ?? undefined,
      value: bestAction?.winProb ?? undefined,
      baseline: null,
      sampleSize: bestAction ? whatIf.outcomes[bestAction.action].support : undefined,
    },
    opts
  );
}
