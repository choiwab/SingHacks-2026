import type { components } from "./generated/openapi";
import type { MondayBriefProjection, ScenarioPair } from "./preview-contracts";

export type {
  MondayBriefProjection,
  RankedClient,
  CitedText,
  ClientPreRead,
  WorkflowContext,
  ScenarioPair,
} from "./preview-contracts";

export type ScenarioKey = keyof ScenarioPair;
export type ProjectionFact = MondayBriefProjection["facts"][string][number];
export type CitationId = keyof MondayBriefProjection["evidence"];

// The live review API requires a persisted run and brief version.
type Schemas = components["schemas"];
export type ReviewActionRequest = Schemas["ReviewActionRequest"];
export type ReviewActionResponse = Schemas["ReviewActionResponse"];

// The preview server only echoes simulated receipts, without a persisted run.
export interface ReviewRequest {
  client_id: string;
  action: "Approve" | "Edit" | "Reject";
  text: string;
}
export interface ReviewResponse {
  review: ReviewRequest & {
    review_id: string;
    timestamp: string;
    rm: string;
  };
}
export type ReviewAction = ReviewRequest["action"];
