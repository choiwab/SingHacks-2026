/*
 * Initial generated-style contract for the Monday Brief projection.
 * Replace this file with `pnpm generate:api` once the backend is running.
 */

export type CitationId = string;
export type Urgency = "now" | "soon" | "watch";
export type ScenarioKey = "reopens" | "escalates";
export type ReviewAction = "Approve" | "Edit" | "Reject";
export type Confidence = "high" | "medium" | "low";
export type JsonValue =
  string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export interface RankedClient {
  client_id: string;
  name: string;
  score: number;
  urgency: Urgency;
  reason: string;
  meeting: string | null;
  meeting_source: string | null;
  components: Record<string, number>;
  citations: CitationId[];
}

export interface CitedText {
  text: string;
  citations: CitationId[];
}

export interface Belief extends CitedText {
  id: string;
  note_id: string;
}

export interface BeliefGap {
  id: string;
  belief: string;
  data: string;
  citations: CitationId[];
}

export interface WorkflowContext {
  system: string;
  status: string;
  citations: CitationId[];
}

export interface ClientPreRead {
  client_id: string;
  name: string;
  beliefs: Belief[];
  gap: BeliefGap;
  what_changed: CitedText[];
  rules_money: CitedText[];
  language: string;
  opening: CitedText;
  uncertainty: CitedText;
  workflow: WorkflowContext[];
}

export interface ScenarioBullet extends CitedText {
  low_delta: number;
  high_delta: number;
}

export interface ScenarioProjection {
  name: string;
  low_delta: number;
  high_delta: number;
  low_pct: number;
  high_pct: number;
  currency: string;
  portfolio_value: number;
  disclaimer: string;
  bullets: ScenarioBullet[];
  citations: CitationId[];
}

export type ScenarioPair = Record<ScenarioKey, ScenarioProjection>;

export type FactKind =
  | "profile"
  | "mandate_gap"
  | "change"
  | "concentration"
  | "deadline"
  | "facility"
  | "other";

export interface ProjectionFact {
  id: string;
  kind: FactKind;
  what: string;
  numbers: Record<string, JsonValue>;
  source_rows: CitationId[];
  event_ids: CitationId[];
  confidence: Confidence;
}

export interface EvidenceRecord {
  id: CitationId;
  kind: string;
  title: string;
  source: string;
  record: Record<string, JsonValue>;
}

export interface MondayBriefProjection {
  schema_version: 1;
  as_of: string;
  pipeline: string;
  ranking_formula: string;
  ranking: RankedClient[];
  facts: Record<string, ProjectionFact[]>;
  pre_reads: Record<string, ClientPreRead>;
  scenarios: Record<string, ScenarioPair>;
  evidence: Record<CitationId, EvidenceRecord>;
}

export interface ReviewRequest {
  client_id: string;
  action: ReviewAction;
  text: string;
}

export interface ReviewRecord extends ReviewRequest {
  review_id?: string;
  rm: string;
  timestamp: string;
}

export interface ReviewResponse {
  review: ReviewRecord;
}
