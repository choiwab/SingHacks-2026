import type { components } from "./generated/openapi";

type Schemas = components["schemas"];
export type ClientHistory = Schemas["ClientHistory"];
export type BriefVersion = Schemas["BriefHistoryVersion"];
export type DemoViewModel = Schemas["DemoViewModel"];

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail =
      payload &&
      typeof payload === "object" &&
      "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : "The request failed. Please try again.";
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function getBriefHistory(
  clientId: string,
  runId: string,
  signal: AbortSignal,
): Promise<ClientHistory> {
  const history = await request<ClientHistory>(
    `/api/clients/${encodeURIComponent(clientId)}/history?run_id=${encodeURIComponent(runId)}`,
    { signal },
  );
  if (
    history.client_id !== clientId ||
    history.run_id !== runId ||
    !Array.isArray(history.versions)
  ) {
    throw new Error(
      "The history does not match this Client and Pipeline Run. Reload the workspace.",
    );
  }
  return history;
}

export async function controlledUpdate(
  action: "apply" | "reset",
): Promise<DemoViewModel> {
  await request<DemoViewModel>("/api/demo/update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  // POST marks its response Updating; read the settled view before review resumes.
  return request<DemoViewModel>("/api/app");
}
