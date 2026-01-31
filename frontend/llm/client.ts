import { config } from "../config";
import type { PromptInput } from "./prompt";
import { buildPrompt } from "./prompt";

export type LLMResult = {
  text: string;
  usedLLM: boolean;
};

async function callOpenAI(prompt: PromptInput): Promise<string> {
  const apiKey = config.llm.apiKey;
  if (!apiKey) throw new Error("OPENAI_API_KEY missing");

  const { system, user } = buildPrompt(prompt);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), config.llm.timeoutMs);

  try {
    const resp = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: config.llm.model,
        messages: [
          { role: "system", content: system },
          { role: "user", content: user },
        ],
        temperature: 0.4,
      }),
      signal: controller.signal,
    });

    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`OpenAI error: ${resp.status} ${text}`);
    }

    const json = await resp.json();
    const content: string | undefined = json.choices?.[0]?.message?.content;
    if (!content) throw new Error("Empty completion");
    return content.trim();
  } finally {
    clearTimeout(timer);
  }
}

export async function renderWithLLM(prompt: PromptInput, templateFallback: string): Promise<LLMResult> {
  try {
    const text = await callOpenAI(prompt);
    return { text, usedLLM: true };
  } catch (err) {
    console.warn("LLM call failed, fallback to template", err);
    return { text: templateFallback, usedLLM: false };
  }
}