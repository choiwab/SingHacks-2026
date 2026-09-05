import type {
  ReviewActionRequest,
  ReviewActionResponse,
  ReviewRequest,
  ReviewResponse,
} from "./contracts";
import {
  adaptViewModel,
  isDemoViewModel,
  type AppProjection,
  type CommunicationRecord,
  type DemoViewModel,
} from "./live/adapter";

export const isPreview = import.meta.env.MODE === "preview";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : "The server did not answer. Try again.";
    throw new Error(
      path === "/api/app" && response.status === 404
        ? "The dashboard API is not available yet."
        : detail,
    );
  }

  return (await response.json()) as T;
}

export async function getMondayBrief(): Promise<AppProjection> {
  if (isPreview) {
    return request<AppProjection>("/preview/dashboard");
  }
  const viewModel = await request<DemoViewModel>("/api/app");
  if (!isDemoViewModel(viewModel)) {
    throw new Error("The dashboard API is not available yet.");
  }
  return adaptViewModel(viewModel);
}

/** RM-triggered pipeline run: apply the update overlay or reset to the seed. */
export async function runPipeline(
  action: "apply" | "reset",
): Promise<AppProjection> {
  const viewModel = await request<DemoViewModel>("/api/demo/update", {
    method: "POST",
    body: JSON.stringify({ action }),
  });
  return adaptViewModel(viewModel);
}

export async function getClientMemory(clientId: string): Promise<{
  client_id: string;
  as_of: string;
  records: CommunicationRecord[];
  sources: Record<string, string>;
}> {
  return request(`/api/clients/${clientId}/memory`);
}

export async function getCommunications(source?: string): Promise<{
  as_of: string;
  records: CommunicationRecord[];
}> {
  const query = source ? `?source=${encodeURIComponent(source)}` : "";
  return request(`/api/communications${query}`);
}

export async function saveReview(
  review: ReviewRequest,
  live?: { runId: string; briefVersion: number },
): Promise<ReviewResponse> {
  if (isPreview) {
    return request<ReviewResponse>("/preview/reviews", {
      method: "POST",
      body: JSON.stringify(review),
    });
  }
  if (!live) {
    throw new Error("Review actions need a loaded live run.");
  }
  const payload: ReviewActionRequest = {
    client_id: review.client_id,
    action: review.action,
    text: review.text,
    section: review.action === "Edit" ? "opening" : null,
    reason: null,
    run_id: live.runId,
    brief_version: live.briefVersion,
  };
  const response = await request<ReviewActionResponse>("/api/reviews", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return { review: response.review };
}
