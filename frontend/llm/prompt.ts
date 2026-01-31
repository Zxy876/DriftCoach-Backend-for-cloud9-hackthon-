import type { NarrativeIntent } from "./intents";
import type { GameProfile } from "./profiles";
import { renderTemplate, type TemplateContext } from "./templates";

const SYSTEM_PROMPT = `You are an esports performance analyst acting as a post-match interpreter.

Your role is NOT to analyze new data, NOT to infer new causes, and NOT to give advice.

You only translate existing, structured analytical results into game-contextual language
that a professional coach or analyst would naturally use.

You must strictly obey the following rules:
- Do NOT introduce new statistics, probabilities, or causes.
- Do NOT modify or reinterpret any numeric values.
- Do NOT give recommendations, suggestions, or commands.
- Do NOT use words like "should", "must", "need to", or "optimal".

If the signal is weak or the sample size is small, you must explicitly express uncertainty.
Your output must be explainable and traceable to the given inputs.
Avoid repeating the same key noun phrase across outputs when possible; vary phrasing while preserving meaning.`;

export type PromptInput = {
  gameId: string;
  gameProfile: GameProfile;
  intent: NarrativeIntent;
  structuredFacts: Record<string, unknown>;
  context: TemplateContext;
  mathMetaphor?: string | null;
};

export function buildPrompt(input: PromptInput) {
  const templateBaseline = renderTemplate(input.intent, input.gameProfile, input.context);
  const user = `Game: ${input.gameId}\nGame Profile: ${input.gameProfile.id}\n\nNarrative Intent:\n${input.intent}\n\nStructured Facts (read-only):\n${JSON.stringify(input.structuredFacts, null, 2)}\n\nStatistical Context:\n- baseline: ${input.context.baseline ?? "n/a"}\n- observed value: ${input.context.value ?? "n/a"}\n- sample size: ${input.context.sampleSize ?? "n/a"}\n- confidence: ${input.context.confidence ?? "n/a"}\n\nOptional Mathematical Metaphor:\n${input.mathMetaphor ?? "(none)"}\n\nTask:\nWrite a short, professional explanation in the language and tone commonly used by coaches in this game.\nThe explanation should stay faithful to the facts above, use appropriate game-context terminology, and reflect uncertainty if confidence or sample size is low.\nDo NOT add new conclusions or advice.\nYou may vary wording to avoid repeating the same noun phrase.\nFor reference, a safe template is: ${templateBaseline}`;

  return {
    system: SYSTEM_PROMPT,
    user,
  };
}