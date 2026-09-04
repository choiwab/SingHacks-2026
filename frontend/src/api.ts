import type {
  MondayBriefProjection,
  ReviewRequest,
  ReviewResponse,
} from "./generated/api";

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
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export function getMondayBrief(): Promise<MondayBriefProjection> {
  return request<MondayBriefProjection>("/api/monday-brief");
}

export function saveReview(review: ReviewRequest): Promise<ReviewResponse> {
  return request<ReviewResponse>("/api/reviews", {
    method: "POST",
    body: JSON.stringify(review),
  });
}
