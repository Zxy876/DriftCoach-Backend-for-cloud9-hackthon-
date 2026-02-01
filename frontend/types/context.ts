export type ContextSchema = {
  hasOutcome?: boolean;
  missing?: string[];
};

export type EvidenceMeta = {
  states?: number;
  byType?: Record<string, number>;
  delta_states?: number;
  delta_by_type?: Record<string, number>;
  patch_success_rate?: number;
};

export type AnalysisContext = {
  player: string;
  team: string;
  match: string;
  map: string;
  timestamp: string; // ISO string
  source: "mock" | "GRID" | string;
  window: string;
  schema?: ContextSchema;
  evidence?: EvidenceMeta;
  provenance?: Array<Record<string, unknown>>;
};

export type InferencePlan = {
  judgment: "EVIDENCE_SUFFICIENT" | "EVIDENCE_INSUFFICIENT";
  rationale: string;
  missing_evidence?: {
    concept: string;
    required_entity: string;
    reason: string;
  }[];
  proposed_patches?: PatchPlan[];
  confidence_note: string;
};

export type PatchPlan = {
  patch_type: string;
  target_entity: "series" | "player" | "team";
  params?: Record<string, unknown>;
  constraints?: string[];
  expected_evidence_type: "AGGREGATED_PERFORMANCE" | "CONTEXT_ONLY";
};

export type PatchResult = {
  patch: string;
  status: "ok" | "skipped" | "error";
  trace_id?: string;
  origin?: string;
  reason?: string;
};

export type SessionAnalysisNode = {
  node_id: string;
  type: string;
  source: string;
  axes_covered: string[];
  confidence: number;
  created_from_query: string;
  created_at: string;
  last_updated_at: string;
  target?: string | null;
  window?: string | null;
  used_in_queries?: string[];
  metadata?: Record<string, unknown>;
};

export type SessionStatsSnapshot = {
  target: string;
  window?: string | null;
  used_in_queries: string[];
  last_status: string;
  last_updated_at: string;
  metadata?: Record<string, unknown>;
};

export type SessionAnalysis = {
  session_id: string;
  entities: {
    players: string[];
    teams: string[];
    series: string[];
    tournaments: string[];
  };
  analysis_nodes: SessionAnalysisNode[];
  stats_snapshots: SessionStatsSnapshot[];
  last_query?: string | null;
  last_updated_at?: string | null;
  recently_added_node_ids?: string[];
};

export type CoachPayload = {
  context: AnalysisContext;
  insights?: import("./insight").Insight[];
  review?: import("./review").ReviewAgendaItem[];
  whatIf?: import("./whatif").WhatIfOutcome;
  assistant_message?: string;
  answer_synthesis?: { claim?: string; confidence?: number; rationale?: string; [key: string]: unknown };
  narrative?: { type?: string; confidence?: number | string | null; content?: unknown; [key: string]: unknown };
  inference_plan?: InferencePlan;
  patch_results?: PatchResult[];
  session_analysis?: SessionAnalysis;
};

export type DemoPayload = CoachPayload;
