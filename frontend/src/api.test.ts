import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

const liveView = {
  as_of: "2026-08-26",
  run_id: "123456789abc",
  refreshed_at: "2026-08-26T08:00:00Z",
  data_health: "Current",
  clients: {
    "CL-0003": {
      header: {
        client_id: "CL-0003",
        client_name: "Margarethe Voss-Brenner",
        reporting_language: "German",
      },
      insights: [
        {
          signal_id: "CL-0003:signal:suitability",
          score: 100,
          components: { consequence: 100 },
          facts: [
            {
              id: "claim-1",
              text: "Equity is 71.5% against a 30% maximum.",
              citations: ["CL-0003:fact:mandate-gap:actual_pct"],
            },
          ],
          why_it_matters: "The mandate is breached.",
        },
      ],
      meeting_brief: {
        sections: {
          summary: [],
          opening: { id: "opening", text: "Shall we review?", citations: [] },
          talking_points: [],
          questions: [],
          uncertainty: [],
        },
      },
      brief_version: 1,
      memory_card: null,
      data_tab: {
        mandate: [
          {
            id: "CL-0003:fact:mandate-gap:actual_pct",
            client_id: "CL-0003",
            kind: "mandate-gap.actual_pct",
            value: 71.5,
            unit: "percent",
            currency: null,
            inputs: {
              actual_pct: 71.5,
              asset_class: "Equity",
              boundary: "maximum",
              gap_pct: 41.5,
              limit_pct: 30,
              scope: "Household",
            },
            evidence_ids: ["holdings:2026-08-26:PF-0005:SYN-EQ-0003"],
            confidence: 1,
          },
        ],
      },
      memory_tab: [],
      brief_status: "Needs review",
      verification: { passed: true },
      context_issues: [],
    },
  },
  calendar: [],
  evidence: {},
  connected_evidence: {},
  reviews: [],
};

describe("live API boundary", () => {
  it("adapts the live DemoViewModel into the projection the screens render", async () => {
    vi.stubEnv("MODE", "development");
    const fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(liveView)));
    vi.stubGlobal("fetch", fetch);
    const { getMondayBrief } = await import("./api");
    const projection = await getMondayBrief();
    expect(fetch).toHaveBeenCalledWith("/api/app", expect.any(Object));
    expect(projection.live?.runId).toBe("123456789abc");
    expect(projection.ranking[0].client_id).toBe("CL-0003");
    expect(projection.pre_reads["CL-0003"].name).toBe(
      "Margarethe Voss-Brenner",
    );
    expect(projection.facts["CL-0003"][0].kind).toBe("mandate_gap");
    expect(projection.scenarios).toEqual({});
  });

  it("rejects a payload that is neither projection nor DemoViewModel", async () => {
    vi.stubEnv("MODE", "development");
    const fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ hello: "world" })));
    vi.stubGlobal("fetch", fetch);
    const { getMondayBrief } = await import("./api");
    await expect(getMondayBrief()).rejects.toThrow(
      "The dashboard API is not available yet.",
    );
  });

  it("refuses a review without a loaded live run", async () => {
    vi.stubEnv("MODE", "development");
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const { saveReview } = await import("./api");
    await expect(
      saveReview({ client_id: "CL-0003", action: "Approve", text: "Draft" }),
    ).rejects.toThrow("Review actions need a loaded live run.");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("submits live reviews with the pinned run and brief version", async () => {
    vi.stubEnv("MODE", "development");
    const fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          review: {
            client_id: "CL-0003",
            action: "Approve",
            text: "Draft",
            review_id: "rev-1",
            rm: "Priscilla Ong",
            timestamp: "2026-08-26T08:00:00Z",
          },
          brief_version: 1,
          verification_report: {},
        }),
      ),
    );
    vi.stubGlobal("fetch", fetch);
    const { saveReview } = await import("./api");
    const response = await saveReview(
      { client_id: "CL-0003", action: "Approve", text: "Draft" },
      { runId: "123456789abc", briefVersion: 1 },
    );
    expect(fetch).toHaveBeenCalledWith(
      "/api/reviews",
      expect.objectContaining({ method: "POST" }),
    );
    const body = JSON.parse(
      (fetch.mock.calls[0][1] as RequestInit).body as string,
    ) as Record<string, unknown>;
    expect(body.run_id).toBe("123456789abc");
    expect(body.brief_version).toBe(1);
    expect(response.review.review_id).toBe("rev-1");
  });
});
