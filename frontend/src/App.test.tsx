import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { App } from "./App";
import { projectionFixture } from "./test/fixture";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function projectionResponse() {
  return new Response(JSON.stringify(projectionFixture), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("Monday Brief", () => {
  it("loads one projection and shares it across the routed workflow", async () => {
    const fetch = vi.fn(() => Promise.resolve(projectionResponse()));
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    );

    const switcher = await screen.findByRole("navigation", {
      name: "Client switcher",
    });
    await user.click(
      within(switcher).getByRole("button", { name: /Margarethe Voss-Brenner/ }),
    );
    expect(
      await screen.findByRole("heading", { name: "Margarethe Voss-Brenner" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Rehearse a Strait scenario →" }),
    );
    expect(
      await screen.findByText("Strait reopens", {
        selector: ".scenario-label",
      }),
    ).toBeVisible();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("filters the client switcher and marks the selected client", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(projectionResponse())),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/clients/CL-0003/pre-read"]}>
        <App />
      </MemoryRouter>,
    );

    const switcher = await screen.findByRole("navigation", {
      name: "Client switcher",
    });
    expect(
      within(switcher).getByRole("button", { name: /Margarethe Voss-Brenner/ }),
    ).toHaveAttribute("aria-current", "true");
    expect(
      within(switcher).getByRole("button", { name: /Abdullah Al-Mansoori/ }),
    ).toBeVisible();

    await user.type(
      within(switcher).getByRole("searchbox", { name: "Search clients" }),
      "margar",
    );
    expect(
      within(switcher).queryByRole("button", { name: /Abdullah Al-Mansoori/ }),
    ).not.toBeInTheDocument();
    expect(
      within(switcher).getByRole("button", { name: /Margarethe Voss-Brenner/ }),
    ).toBeVisible();
  });

  it("moves through the Overview, Insights, Data, and Memory tabs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(projectionResponse())),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/clients/CL-0003/pre-read"]}>
        <App />
      </MemoryRouter>,
    );

    // Dashboard header (PRD 5.2): profile, next meeting, and data health.
    expect(
      await screen.findByText(
        "Margarethe Voss-Brenner has a Conservative profile.",
      ),
    ).toBeVisible();
    expect(screen.getByText("Next meeting · Mon 10:30")).toBeVisible();
    expect(screen.getByText("Data Current")).toBeVisible();
    expect(screen.getByRole("heading", { name: "What changed" })).toBeVisible();

    await user.click(screen.getByRole("tab", { name: "Insights" }));
    // The profile fact is context, so only the two discrepancies rank.
    const insights = screen.getAllByRole("heading", { level: 3 });
    expect(insights.map((node) => node.textContent)).toEqual([
      "Equity is above the mandate limit.",
      "German inheritance tax instalment starts in 36 days.",
      "Suggested question",
      "What we are not sure about",
    ]);
    expect(
      screen.queryByRole("heading", { name: "What changed" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Data" }));
    expect(screen.getByRole("heading", { name: "Profile" })).toBeVisible();
    expect(screen.getByText("booking centre")).toBeVisible();

    await user.click(screen.getByRole("tab", { name: "Memory" }));
    expect(
      screen.getByText("2026-02-16 · Meeting · Priscilla Ong"),
    ).toBeVisible();
    expect(screen.getByText("\u201cKeep it safe.\u201d")).toBeVisible();
  });

  it("opens the meeting brief with the PRD 5.5 summary, agenda and commitments", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(projectionResponse())),
    );
    render(
      <MemoryRouter initialEntries={["/clients/CL-0003/pre-read"]}>
        <App />
      </MemoryRouter>,
    );

    const summary = await screen.findByRole("region", {
      name: "Two-minute summary",
    });
    // Assembled from the profile fact, the ranking, the gap, the deadline and
    // the snapshot deltas - nothing the projection does not already carry.
    expect(
      within(summary).getByText(
        /Recently widowed, resident in Singapore, booked in Singapore/,
      ),
    ).toBeVisible();
    expect(
      within(summary).getByText(
        /You meet Margarethe Voss-Brenner on Mon 10:30/,
      ),
    ).toBeVisible();
    expect(within(summary).getByText(/1 position moved/)).toBeVisible();

    // The agenda is severity-ranked, so the mandate gap leads the deadline.
    const topics = screen.getByRole("region", {
      name: "Three discussion topics",
    });
    const headings = within(topics).getAllByRole("heading", { level: 3 });
    expect(headings.map((heading) => heading.textContent)).toEqual([
      "Equity is above the mandate limit.",
      "German inheritance tax instalment starts in 36 days.",
    ]);
    expect(
      within(topics).getByText(
        "Equity sits at 71.5% against a 30% maximum, 41.5 points out, measured Household look-through; strictest applicable band.",
      ),
    ).toBeVisible();
    expect(
      within(topics).getByText(/Liquid assets cover 528% of it\./),
    ).toBeVisible();

    const commitments = screen.getByRole("region", {
      name: "Open commitments",
    });
    expect(
      within(commitments).getByText("German inheritance tax instalment"),
    ).toBeVisible();
    expect(
      within(commitments).getByText("Due 2026-10-01 to 2026-12-31 · Confirmed"),
    ).toBeVisible();
  });

  it("expands evidence and restores focus to the Why button", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(projectionResponse())),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/clients/CL-0003/pre-read"]}>
        <App />
      </MemoryRouter>,
    );

    // Scoped to the "What changed" block: the two-minute summary above it now
    // owns the first Why? on the page.
    const changed = await screen.findByRole("region", { name: "What changed" });
    const why = within(changed).getAllByRole("button", { name: "Why?" })[0];
    await user.click(why);
    const dialog = screen.getByRole("dialog", { name: "Why?" });
    expect(dialog).toBeVisible();
    // The claim, its review state, the calculation inputs, and the exact source
    // row are all required by PRD 5.7.
    expect(within(dialog).getByText("Equity increased.")).toBeVisible();
    expect(
      within(dialog).getByText("Generated · awaiting RM review"),
    ).toBeVisible();
    expect(within(dialog).getByText("gap pct")).toBeVisible();
    expect(within(dialog).getByText("41.5")).toBeVisible();
    expect(
      within(dialog).getByText(
        "Confidence high · as of 2026-08-26 · fact CL-0003:fact:gap",
      ),
    ).toBeVisible();
    expect(within(dialog).getByText("Current equity holding")).toBeVisible();
    expect(
      within(dialog).getByText("data/holdings.csv · row holding:1"),
    ).toBeVisible();
    await user.click(
      within(dialog).getByRole("button", { name: "Close source trail" }),
    );
    expect(why).toHaveFocus();
  });

  it("redirects an invalid client to an accessible notice", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(projectionResponse())),
    );
    render(
      <MemoryRouter initialEntries={["/clients/CL-9999/pre-read"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: "Who needs you this week" }),
    ).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent(
      /CL-9999 was not found/,
    );
  });

  it("ranks the week's meetings, tracks brief state, and switches client", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        Promise.resolve(
          String(input).endsWith("/api/reviews")
            ? new Response(
                JSON.stringify({
                  review: {
                    review_id: "r-1",
                    client_id: "CL-0003",
                    action: "Approve",
                    text: "",
                    rm: "Priscilla Ong",
                    timestamp: "2026-09-05T09:00:00+00:00",
                  },
                }),
                {
                  status: 200,
                  headers: { "Content-Type": "application/json" },
                },
              )
            : projectionResponse(),
        ),
      ),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/clients/CL-0019/pre-read"]}>
        <App />
      </MemoryRouter>,
    );

    // The calendar remounts with the pre-read, so it is re-queried each time.
    const bookedMeeting = () =>
      within(
        screen.getByRole("navigation", { name: "This week's meetings" }),
      ).getByRole("button", { name: /Margarethe Voss-Brenner/ });
    await screen.findByRole("navigation", { name: "This week's meetings" });
    const booked = bookedMeeting();
    expect(booked).toHaveTextContent("Mon 10:30");
    expect(booked).toHaveTextContent("Needs review");
    expect(booked).not.toHaveAttribute("aria-current");

    await user.click(booked);
    expect(
      await screen.findByRole("heading", { name: "Margarethe Voss-Brenner" }),
    ).toBeVisible();
    expect(bookedMeeting()).toHaveAttribute("aria-current", "true");

    await user.click(screen.getByRole("button", { name: "Approve pre-read" }));
    await waitFor(() => expect(bookedMeeting()).toHaveTextContent("Ready"));
  });

  it("surfaces review failures without leaving the pre-read", async () => {
    const fetch = vi.fn((input: RequestInfo | URL) => {
      if (String(input).endsWith("/api/reviews")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ detail: "Review ledger unavailable" }),
            { status: 503 },
          ),
        );
      }
      return Promise.resolve(projectionResponse());
    });
    vi.stubGlobal("fetch", fetch);
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/clients/CL-0003/pre-read"]}>
        <App />
      </MemoryRouter>,
    );

    await user.click(
      await screen.findByRole("button", { name: "Approve pre-read" }),
    );
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The review was not saved.");
    expect(alert).toHaveTextContent("Review ledger unavailable");
    expect(
      screen.getByRole("heading", { name: "Margarethe Voss-Brenner" }),
    ).toBeVisible();

    // The failure stays until the RM dismisses it, unlike the success toast.
    await user.click(
      screen.getByRole("button", { name: "Dismiss the review error" }),
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
