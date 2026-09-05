import {
  act,
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { BriefHistoryPanel } from "./BriefHistoryPanel";
import type { components } from "./generated/openapi";
import type {
  BriefVersion,
  ClientHistory,
  DemoViewModel,
} from "./brief-history-api";

type Client = components["schemas"]["ClientView"];
const client: Client = {
  header: {
    client_id: "CL-0003",
    client_name: "Margarethe",
    rm_id: "rm",
    rm_name: "Alex",
    rm_desk: "Desk",
    base_currency: "EUR",
    risk_profile: "Balanced",
    life_stage: "Retired",
    reporting_language: "English",
    booking_centre: "Singapore",
  },
  data_tab: {},
  change_report: {
    as_of: "2026-08-01",
    run_id: "bbbbbbbbbbbb",
    client_id: "CL-0003",
    processing_mode: "incremental_update",
  },
  brief_version: 1,
  brief_status: "Needs review",
};
const review = {
  client_id: "CL-0003",
  action: "Approve" as const,
  run_id: "aaaaaaaaaaaa",
  brief_version: 1,
  review_id: "review-old",
  rm: "Alex",
  timestamp: "2026-08-01T10:00:00Z",
  text: "",
};
function version(run: string, text: string): BriefVersion {
  return {
    run_id: run,
    brief_version: 1,
    origin: "generated",
    created_at: "2026-08-01T09:00:00Z",
    meeting_brief: {
      sections: {
        opening: { id: "opening", text, citations: ["note:dated-source"] },
      },
    },
    verification: { passed: true },
    reviews: run === "aaaaaaaaaaaa" ? [review] : [],
  };
}
function history(overrides: Partial<ClientHistory> = {}): ClientHistory {
  return {
    client_id: "CL-0003",
    run_id: "bbbbbbbbbbbb",
    versions: [
      version("bbbbbbbbbbbb", "Ask about the revised plans."),
      version("aaaaaaaaaaaa", "Discuss the original plans."),
    ],
    ...overrides,
  };
}
function response(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status });
}
const model: DemoViewModel = {
  run_id: "bbbbbbbbbbbb",
  as_of: "2026-08-01",
  refreshed_at: "2026-08-01T10:00:00Z",
  data_health: "Current",
  clients: { "CL-0003": client },
};
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("compares same-number versions from different runs without inheriting an earlier approval", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(history())));
  render(
    <BriefHistoryPanel
      client={client}
      runId={model.run_id}
      onModelChange={vi.fn()}
    />,
  );
  const earlier = await screen.findByRole("article", {
    name: "Earlier Meeting Brief",
  });
  const current = screen.getByRole("article", {
    name: "Current Meeting Brief",
  });
  expect(earlier).toHaveTextContent("Discuss the original plans.");
  expect(current).toHaveTextContent("Ask about the revised plans.");
  expect(current).toHaveTextContent("Changed");
  expect(earlier).toHaveTextContent("review-old");
  expect(current).not.toHaveTextContent("review-old");
  expect(current).toHaveTextContent("No Review Decision recorded.");
  expect(screen.getByText(/Earlier approvals apply only/)).toBeVisible();
});

it("never exposes withheld Brief content from raw traces or review text", async () => {
  const value = history();
  value.versions[0].meeting_brief = null;
  value.versions[0].verification = { passed: false };
  value.versions[0].trace = [{ text: "SECRET unsupported generated claim" }];
  value.versions[0].reviews = [
    { ...review, run_id: model.run_id, text: "SECRET rejected draft" },
  ];
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(value)));
  render(
    <BriefHistoryPanel
      client={client}
      runId={model.run_id}
      onModelChange={vi.fn()}
    />,
  );
  expect(
    await screen.findByText(/Meeting Brief content is withheld/),
  ).toBeVisible();
  expect(screen.queryByText(/SECRET/)).not.toBeInTheDocument();
  expect(screen.queryByText(/· Changed/)).not.toBeInTheDocument();
});

it("clears old Client history immediately and ignores a late prior request", async () => {
  let complete!: (response: Response) => void;
  const fetch = vi
    .fn()
    .mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          complete = resolve;
        }),
    )
    .mockResolvedValueOnce(
      response(history({ client_id: "other", versions: [] })),
    );
  vi.stubGlobal("fetch", fetch);
  const { rerender } = render(
    <BriefHistoryPanel
      client={client}
      runId={model.run_id}
      onModelChange={vi.fn()}
    />,
  );
  const other = { ...client, header: { ...client.header, client_id: "other" } };
  rerender(
    <BriefHistoryPanel
      client={other}
      runId={model.run_id}
      onModelChange={vi.fn()}
    />,
  );
  expect(
    await screen.findByText(/No saved Meeting Brief versions yet/),
  ).toBeVisible();
  await act(async () => complete(response(history())));
  expect(
    screen.queryByText("Ask about the revised plans."),
  ).not.toBeInTheDocument();
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
});

it("rejects history from another run and supports retry", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(response(history({ run_id: "aaaaaaaaaaaa" })))
    .mockResolvedValueOnce(response(history()));
  vi.stubGlobal("fetch", fetch);
  render(
    <BriefHistoryPanel
      client={client}
      runId={model.run_id}
      onModelChange={vi.fn()}
    />,
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("does not match");
  await userEvent.click(screen.getByRole("button", { name: "Retry history" }));
  expect(await screen.findByText("Ask about the revised plans.")).toBeVisible();
});

it("applies the Controlled Update, replaces the model, and refreshes scoped history", async () => {
  const updated = { ...model, run_id: "cccccccccccc" };
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(response(history()))
    .mockResolvedValueOnce(response(updated))
    .mockResolvedValueOnce(response(updated))
    .mockResolvedValueOnce(
      response(
        history({
          run_id: updated.run_id,
          versions: [version(updated.run_id, "Updated conversation.")],
        }),
      ),
    );
  vi.stubGlobal("fetch", fetch);
  function Harness() {
    const [value, setValue] = useState(model);
    const [busy, setBusy] = useState(false);
    return (
      <BriefHistoryPanel
        client={client}
        runId={value.run_id}
        onModelChange={setValue}
        busy={busy}
        onBusyChange={setBusy}
      />
    );
  }
  render(<Harness />);
  await screen.findByText("Ask about the revised plans.");
  await userEvent.click(
    screen.getByRole("button", { name: "Apply Controlled Update" }),
  );
  expect(await screen.findByText("Updated conversation.")).toBeVisible();
  expect(fetch.mock.calls[1][0]).toBe("/api/demo/update");
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ action: "apply" });
  expect(fetch.mock.calls[2][0]).toBe("/api/app");
  expect(fetch.mock.calls[3][0]).toContain("run_id=cccccccccccc");
});

it("refreshes history even when reset returns the same run and preserves its approval", async () => {
  const value = history();
  value.versions[0].reviews = [
    { ...review, run_id: model.run_id, review_id: "retained-review" },
  ];
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(response(history()))
    .mockResolvedValueOnce(response(model))
    .mockResolvedValueOnce(response(model))
    .mockResolvedValueOnce(response(value));
  vi.stubGlobal("fetch", fetch);
  render(
    <BriefHistoryPanel
      client={client}
      runId={model.run_id}
      onModelChange={vi.fn()}
    />,
  );
  await screen.findByText("Ask about the revised plans.");
  await userEvent.click(
    screen.getByRole("button", { name: "Reset to seed run" }),
  );
  const current = await screen.findByRole("article", {
    name: "Current Meeting Brief",
  });
  await waitFor(() => expect(current).toHaveTextContent("retained-review"));
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ action: "reset" });
  expect(screen.getByRole("status")).toHaveTextContent(
    "latest persisted Meeting Brief",
  );
});

it("blocks repeated updates during a request and retains a recoverable error", async () => {
  let complete!: (response: Response) => void;
  const busy = vi.fn();
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(response(history()))
    .mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          complete = resolve;
        }),
    );
  vi.stubGlobal("fetch", fetch);
  render(
    <BriefHistoryPanel
      client={client}
      runId={model.run_id}
      onModelChange={vi.fn()}
      onBusyChange={busy}
    />,
  );
  await screen.findByText("Ask about the revised plans.");
  await userEvent.click(
    screen.getByRole("button", { name: "Apply Controlled Update" }),
  );
  expect(
    screen.getByRole("button", { name: "Reset to seed run" }),
  ).toBeDisabled();
  await act(async () => complete(response({ detail: "Stale update" }, 409)));
  expect(await screen.findByRole("alert")).toHaveTextContent("Stale update");
  expect(busy.mock.calls).toEqual([[true], [false]]);
  expect(
    screen.getByRole("button", { name: "Apply Controlled Update" }),
  ).toBeEnabled();
  expect(
    within(
      screen.getByRole("article", { name: "Current Meeting Brief" }),
    ).getByText("Ask about the revised plans."),
  ).toBeVisible();
});

it("withholds comparison when a newer version was saved after the workspace loaded", async () => {
  const value = history();
  value.versions.unshift({
    ...version(model.run_id, "A newer saved opening"),
    brief_version: 2,
  });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(value)));
  render(
    <BriefHistoryPanel
      client={client}
      runId={model.run_id}
      onModelChange={vi.fn()}
    />,
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "History and the current Brief version differ",
  );
  expect(screen.queryByText("A newer saved opening")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("article", { name: "Current Meeting Brief" }),
  ).not.toBeInTheDocument();
});

it("lets the RM select an older saved version and shows removed claims on that side", async () => {
  const value = history();
  const older = version("999999999999", "An older conversation.");
  older.meeting_brief = {
    sections: {
      opening: {
        id: "opening",
        text: "An older conversation.",
        citations: ["note:old"],
      },
      questions: [
        {
          id: "old-question",
          text: "A question removed from the current Brief.",
          citations: ["note:old"],
        },
      ],
    },
  };
  value.versions.push(older);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(value)));
  render(
    <BriefHistoryPanel
      client={client}
      runId={model.run_id}
      onModelChange={vi.fn()}
    />,
  );
  await screen.findByText("Discuss the original plans.");
  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "Compare with" }),
    "999999999999:1",
  );
  expect(
    screen.queryByText("Discuss the original plans."),
  ).not.toBeInTheDocument();
  const earlier = screen.getByRole("article", {
    name: "Earlier Meeting Brief",
  });
  expect(earlier).toHaveTextContent("An older conversation.");
  expect(
    within(earlier)
      .getByText("A question removed from the current Brief.")
      .closest(".brief-version-claim"),
  ).toHaveClass("is-changed");
});
