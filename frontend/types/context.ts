export type AnalysisContext = {
  player: string;
  team: string;
  match: string;
  map: string;
  timestamp: string; // ISO string
  source: "mock" | "GRID" | string;
  window: string;
};

export type DemoPayload = {
  context: AnalysisContext;
  insights: import("./insight").Insight[];
  review: import("./review").ReviewAgendaItem[];
  whatIf: import("./whatif").WhatIfOutcome;
};
