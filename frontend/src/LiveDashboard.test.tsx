import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { FluentProvider, teamsLightTheme } from "@fluentui/react-components";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LiveDashboard } from "./LiveDashboard";
import type { DemoViewModel } from "./live-contracts";
vi.hoisted(() => vi.stubEnv("MODE", "development"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const opening = {
  id: "opening",
  text: "Could we review the payment?",
  citations: ["notes:one"],
  authorship: "agent",
};
function model(): DemoViewModel {
  return {
    as_of: "2026-08-26",
    run_id: "abc123abc123",
    refreshed_at: "2026-08-26T08:00:00Z",
    data_health: "Current",
    clients: {
      "CL-0003": {
        header: {
          client_id: "CL-0003",
          client_name: "Margarethe",
          rm_id: "RM-1",
          rm_name: "Alex",
          rm_desk: "Singapore",
          base_currency: "SGD",
          risk_profile: "Balanced",
          life_stage: "Retired",
          reporting_language: "English",
          booking_centre: "Singapore",
        },
        brief_version: 1,
        brief_status: "Needs review",
        meeting_brief: {
          opening,
          questions: [opening],
          talking_points: [{ ...opening, id: "talking_point:funding" }],
        },
        data_tab: {},
        memory_tab: [
          {
            id: "notes:one",
            source: "notes",
            occurred_at: "2026-08-20T10:00:00Z",
            text: "Please follow up on my payment.",
            availability: "Cached",
          },
        ],
        memory_card: {
          open_promises: {
            claims: [
              {
                ...opening,
                id: "promise",
                text: "Please follow up on my payment.",
              },
            ],
          },
        },
        change_report: {
          client_id: "CL-0003",
          run_id: "abc123abc123",
          as_of: "2026-08-26",
          processing_mode: "first_seen",
        },
      },
    },
    calendar: [
      {
        id: "calendar:one",
        client_id: "CL-0003",
        scheduled_at: "2026-08-26T12:00:00Z",
        availability: "Cached",
      },
    ],
  };
}
function start() {
  render(
    <FluentProvider theme={teamsLightTheme}>
      <MemoryRouter>
        <LiveDashboard />
      </MemoryRouter>
    </FluentProvider>,
  );
}
describe("live Meeting Brief", () => {
  it("opens booked client, resolves exact Evidence, and binds review to current run/version", async () => {
    const data = model();
    data.clients["CL-0003"].meeting_brief = {
      sections: data.clients["CL-0003"].meeting_brief,
    };
    const ready = structuredClone(data);
    ready.clients["CL-0003"].brief_status = "Ready";
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(data)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ brief_version: 1 })))
      .mockResolvedValueOnce(new Response(JSON.stringify(ready)));
    vi.stubGlobal("fetch", fetch);
    start();
    expect(
      await screen.findByRole("heading", { name: "Margarethe" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Since we last spoke" }),
    ).toBeVisible();
    const user = userEvent.setup();
    await user.click(
      screen.getAllByRole("button", { name: "Evidence: notes:one" })[0],
    );
    expect(await screen.findByRole("dialog")).toHaveTextContent(
      "2026-08-20T10:00:00Z",
    );
    await user.click(screen.getByRole("button", { name: "Close" }));
    await user.click(
      screen.getByRole("button", { name: "Approve Meeting Brief" }),
    );
    await screen.findByText("Reviewed meeting pack");
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toMatchObject({
      action: "Approve",
      client_id: "CL-0003",
      run_id: "abc123abc123",
      brief_version: 1,
    });
  });
  it("preserves edited wording after a rejected stale review and uses claim IDs", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(model())))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Stale brief version" }), {
          status: 409,
        }),
      );
    vi.stubGlobal("fetch", fetch);
    start();
    await screen.findByRole("heading", { name: "Margarethe" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Edit wording" }));
    await user.selectOptions(
      screen.getByLabelText("Section to edit"),
      "talking_point:funding",
    );
    await user.clear(screen.getByLabelText("Relationship Manager wording"));
    await user.type(
      screen.getByLabelText("Relationship Manager wording"),
      "Please confirm the funding source.",
    );
    await user.click(
      screen.getByRole("button", { name: "Save edited version" }),
    );
    expect(await screen.findByText(/Stale brief version/)).toBeVisible();
    expect(screen.getByLabelText("Relationship Manager wording")).toHaveValue(
      "Please confirm the funding source.",
    );
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toMatchObject({
      action: "Edit",
      section: "talking_point:funding",
      brief_version: 1,
    });
  });
  it("shows blocked generation as data availability, not network failure", async () => {
    const data = model();
    data.clients["CL-0003"].meeting_brief = null;
    data.clients["CL-0003"].memory_card = null;
    data.clients["CL-0003"].brief_status = "Not prepared";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify(data))),
    );
    start();
    expect(
      await screen.findByText(/No verified Meeting Brief is available/),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Approve Meeting Brief" }),
    ).toBeDisabled();
    expect(screen.getByText(/No changed Fact is identified/)).toBeVisible();
    await waitFor(() =>
      expect(screen.queryByText(/Could not load/)).not.toBeInTheDocument(),
    );
  });
});
