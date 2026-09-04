import type { components } from "./generated/openapi";

type Schemas = components["schemas"];

export type MondayBriefProjection = Schemas["MondayBriefProjection"];
export type RankedClient = Schemas["Priority"];
export type CitedText = Schemas["CitedText"];
export type ClientPreRead = Schemas["PreRead"];
export type WorkflowContext = Schemas["WorkflowContext"];
export type ScenarioPair = Schemas["ScenarioSet"];
export type ScenarioKey = keyof ScenarioPair;
export type ReviewRequest = Schemas["ReviewRequest"];
export type ReviewResponse = Schemas["ReviewResponse"];
export type ReviewAction = ReviewRequest["action"];
export type CitationId = string;
export type ProjectionFact = MondayBriefProjection["facts"][string][number];
