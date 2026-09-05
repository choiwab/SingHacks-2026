import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { components } from "./generated/openapi";
import { MeetingPresentation } from "./MeetingPresentation";

type Client = components["schemas"]["ClientView"];
type Model = components["schemas"]["DemoViewModel"];
const client: Client = {
  header: {
    client_id: "c1",
    client_name: "Margarethe",
    rm_id: "rm1",
    rm_name: "Taylor",
    rm_desk: "Desk",
    base_currency: "EUR",
    risk_profile: "Balanced",
    life_stage: "Retired",
    reporting_language: "German",
    booking_centre: "Singapore",
  },
  brief_status: "Needs review",
  brief_version: 2,
  verification: { passed: true },
  meeting_brief: {
    sections: {
      opening: {
        text: "What has changed in your plans?",
        citations: ["source1"],
      },
      uncertainty: [{ text: "Confirm the timing.", citations: ["source1"] }],
    },
  },
  data_tab: {},
  change_report: {
    client_id: "c1",
    run_id: "run2",
    as_of: "2026-08-01",
    processing_mode: "incremental_update",
  },
};
const model: Model = {
  as_of: "2026-08-01",
  run_id: "run2",
  refreshed_at: "2026-08-01T00:00:00Z",
  data_health: "Current",
  clients: { c1: client },
  evidence: {
    source1: {
      id: "source1",
      title: "Client note",
      kind: "note",
      source: "notes",
      source_file: "notes.csv",
      row_index: 4,
      record: {},
    },
    secret: {
      id: "secret",
      title: "Other client private source",
      kind: "note",
      source: "notes",
      source_file: "notes.csv",
      record: {},
    },
  },
};
const approval = {
  client_id: "c1",
  run_id: "run2",
  brief_version: 2,
  action: "Approve" as const,
  text: "",
  review_id: "r1",
  rm: "Taylor",
  timestamp: "2026-08-01T01:00:00Z",
};
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it("presents cited draft content and exact identity without implying approval or translating", () => {
  render(
    <MeetingPresentation client={client} model={model} onClose={() => {}} />,
  );
  expect(screen.getByRole("status")).toHaveTextContent(
    "Draft: needs Relationship Manager review",
  );
  expect(screen.getByText("run2")).toBeVisible();
  expect(
    screen.getByText(/Requested reporting language: German/),
  ).toBeVisible();
  expect(screen.getByText(/notes.csv/)).toBeVisible();
  expect(
    screen.queryByText("Other client private source"),
  ).not.toBeInTheDocument();
});
it("accepts only the current run and version's approval", () => {
  const { rerender } = render(
    <MeetingPresentation
      client={{ ...client, brief_status: "Ready" }}
      model={{ ...model, reviews: [{ ...approval, brief_version: 1 }] }}
      onClose={() => {}}
    />,
  );
  expect(screen.getByRole("status")).toHaveTextContent("Draft");
  rerender(
    <MeetingPresentation
      client={{ ...client, brief_status: "Ready" }}
      model={{ ...model, reviews: [approval] }}
      onClose={() => {}}
    />,
  );
  expect(screen.getByRole("status")).toHaveTextContent(
    "Reviewed Meeting Brief",
  );
  rerender(
    <MeetingPresentation
      client={{ ...client, brief_status: "Ready" }}
      model={{ ...model, reviews: [approval], data_health: "Stale" }}
      onClose={() => {}}
    />,
  );
  expect(screen.getByRole("status")).toHaveTextContent("Stale data");
});
it.each([
  null,
  { sections: { opening: { text: "Do not publish", citations: [] } } },
])(
  "blocks unavailable or failed verification content and print",
  (meeting_brief) => {
    render(
      <MeetingPresentation
        client={{ ...client, meeting_brief, verification: { passed: false } }}
        model={model}
        onClose={() => {}}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Print Meeting Brief" }),
    ).toBeDisabled();
    expect(screen.queryByText("Do not publish")).not.toBeInTheDocument();
  },
);
it("keeps rejection honest and restores keyboard focus on close", async () => {
  const user = userEvent.setup();
  const opener = document.createElement("button");
  document.body.append(opener);
  opener.focus();
  const onClose = vi.fn();
  const { unmount } = render(
    <MeetingPresentation
      client={client}
      model={{ ...model, reviews: [{ ...approval, action: "Reject" }] }}
      onClose={onClose}
    />,
  );
  expect(screen.getByRole("status")).toHaveTextContent("Rejected");
  expect(document.body).toHaveClass("presenting-meeting");
  await user.keyboard("{Escape}");
  expect(onClose).toHaveBeenCalledOnce();
  unmount();
  expect(opener).toHaveFocus();
  expect(document.body).not.toHaveClass("presenting-meeting");
  opener.remove();
});
it("prints only on request", async () => {
  const print = vi.spyOn(window, "print").mockImplementation(() => {});
  render(
    <MeetingPresentation client={client} model={model} onClose={() => {}} />,
  );
  expect(print).not.toHaveBeenCalled();
  await userEvent.click(
    screen.getByRole("button", { name: "Print Meeting Brief" }),
  );
  expect(print).toHaveBeenCalledOnce();
});
