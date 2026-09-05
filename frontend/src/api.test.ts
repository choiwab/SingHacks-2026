import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("live API boundary", () => {
  it("rejects the live DemoViewModel before preview screens consume it", async () => {
    vi.stubEnv("MODE", "development");
    const fetch = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ run_id: "123456789abc", clients: [] })),
      );
    vi.stubGlobal("fetch", fetch);
    const { getMondayBrief } = await import("./api");
    await expect(getMondayBrief()).rejects.toThrow(
      "The dashboard API is not available yet.",
    );
    expect(fetch).toHaveBeenCalledWith("/api/app", expect.any(Object));
  });

  it("does not submit a preview decision to the live review ledger", async () => {
    vi.stubEnv("MODE", "development");
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const { saveReview } = await import("./api");
    await expect(
      saveReview({ client_id: "CL-0003", action: "Approve", text: "Draft" }),
    ).rejects.toThrow(
      "Review actions are not available in this dashboard yet.",
    );
    expect(fetch).not.toHaveBeenCalled();
  });
});
