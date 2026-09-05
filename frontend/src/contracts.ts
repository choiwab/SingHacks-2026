import type { components } from "./generated/openapi";

type Schemas = components["schemas"];

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
export type ReviewRequest = Schemas["ReviewRequest"];
export type ReviewResponse = Schemas["ReviewResponse"];
export type ReviewAction = ReviewRequest["action"];
export type CitationId = string;
export type ProjectionFact = MondayBriefProjection["facts"][string][number];
