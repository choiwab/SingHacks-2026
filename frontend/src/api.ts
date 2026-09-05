import type {
  MondayBriefProjection,
  ReviewRequest,
  ReviewResponse,
} from "./contracts";

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

export function getMondayBrief(): Promise<MondayBriefProjection> {
  return request<MondayBriefProjection>(
    isPreview ? "/preview/dashboard" : "/api/app",
  );
}

export function saveReview(review: ReviewRequest): Promise<ReviewResponse> {
  return request<ReviewResponse>(
    isPreview ? "/preview/reviews" : "/api/reviews",
    {
      method: "POST",
      body: JSON.stringify(review),
    },
  );
}
