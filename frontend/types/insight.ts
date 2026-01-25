export type DerivedFact = {
  factType: string;
  value: number;
  baseline?: number | null;
  sampleSize: number;
  metadata?: Record<string, unknown>;
};

export type Insight = {
  subject: string;
  claim: string;
  derivedFacts: DerivedFact[];
  confidence: number; // 0-1
  failureConditions: string[];
  explanation?: string; // LLM-rendered text (frontend layer), optional
};
