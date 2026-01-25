import type { DerivedFact } from "./insight";

export type ReviewAgendaItem = {
  matchId: string;
  topic: string;
  statesInvolved: string[];
  evidence: DerivedFact[];
  confidence: number; // 0-1
  explanation?: string; // optional LLM rendering
};
