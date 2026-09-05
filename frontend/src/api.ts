import type {
  MondayBriefProjection,
  ReviewRequest,
  ReviewResponse,
} from "./contracts";

export const isPreview = import.meta.env.MODE === "preview";

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
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

export async function getMondayBrief(): Promise<MondayBriefProjection> {
  const projection = await request<MondayBriefProjection>(
    isPreview ? "/preview/dashboard" : "/api/app",
  );
  // The current live API returns DemoViewModel, which these preview screens
  // cannot render. Keep the unavailable state until that consumer is migrated.
  if (
    !projection ||
    !Array.isArray(projection.ranking) ||
    !projection.pre_reads ||
    !projection.facts ||
    !projection.scenarios ||
    !projection.evidence
  ) {
    throw new Error("The dashboard API is not available yet.");
  }
  return projection;
}

export async function saveReview(
  review: ReviewRequest,
): Promise<ReviewResponse> {
  if (!isPreview) {
    throw new Error("Review actions are not available in this dashboard yet.");
  }
  return request<ReviewResponse>("/preview/reviews", {
    method: "POST",
    body: JSON.stringify(review),
  });
}

export async function getDemoViewModel(): Promise<
  import("./live-contracts").DemoViewModel
> {
  const model =
    await request<import("./live-contracts").DemoViewModel>("/api/app");
  if (
    !model ||
    typeof model.run_id !== "string" ||
    !model.clients ||
    Array.isArray(model.clients)
  ) {
    throw new Error("The server returned an incompatible Demo View Model.");
  }
  return model;
}
export async function saveLiveReview(
  review: import("./contracts").ReviewActionRequest,
): Promise<import("./contracts").ReviewActionResponse> {
  if (isPreview)
    throw new Error("Live reviews are unavailable in fixture preview.");
  return request("/api/reviews", {
    method: "POST",
    body: JSON.stringify(review),
  });
}
