import type { components } from "./generated/openapi";
export type DemoViewModel = components["schemas"]["DemoViewModel"];
export type ClientView = components["schemas"]["ClientView"];
export type Fact = components["schemas"]["Fact"];
export function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
export function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}
export interface Claim {
  id: string;
  text: string;
  citations: string[];
  authorship: string;
}
export function claim(value: unknown): Claim | null {
  const item = record(value);
  if (!text(item.id) || !text(item.text)) return null;
  return {
    id: text(item.id),
    text: text(item.text),
    citations: Array.isArray(item.citations)
      ? item.citations.filter((v): v is string => typeof v === "string")
      : [],
    authorship: text(item.authorship),
  };
}
export function claims(value: unknown): Claim[] {
  return (Array.isArray(value) ? value : [])
    .map(claim)
    .filter((v): v is Claim => v !== null);
}
export function clientFacts(client: ClientView): Fact[] {
  return Object.values(client.data_tab).flatMap((items) => items ?? []);
}
export function factValue(fact: Fact): string {
  return `${fact.value.toLocaleString("en-GB", { maximumFractionDigits: 8 })} ${fact.currency ?? fact.unit}`;
}

export function briefSections(client: ClientView): Record<string, unknown> {
  return record(client.meeting_brief?.sections ?? client.meeting_brief);
}

export function displayDate(value: unknown): string {
  const source = text(value);
  if (!source) return "Date unavailable";
  const parsed = new Date(source);
  if (Number.isNaN(parsed.getTime())) return source;
  return (
    new Intl.DateTimeFormat("en-SG", {
      dateStyle: "medium",
      ...(source.includes("T")
        ? { timeStyle: "short" as const, timeZone: "Asia/Singapore" }
        : { timeZone: "UTC" }),
    }).format(parsed) + (source.includes("T") ? " SGT" : "")
  );
}
export function factLabel(fact: Fact): string {
  return fact.kind.replaceAll(/[._]/g, " ");
}
