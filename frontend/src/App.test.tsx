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
import { measure } from "./ClientDashboard";
import type { ProjectionFact, ReviewRequest } from "./contracts";
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
  it.each([
    ["maximum", 12.9, 15, false],
    ["maximum", 15, 15, false],
    ["maximum", 15.1, 15, true],
    ["minimum", 7.1, 5, false],
    ["minimum", 5, 5, false],
    ["minimum", 4.9, 5, true],
    ["minimum", 0, 0, false],
  ] as const)(
    "preserves source order for a %s mandate at %s against %s",
    async (boundary, actual, limit, breached) => {
      const projection = structuredClone(projectionFixture);
      const fact = projection.facts["CL-0003"].find(
        (f) => f.kind === "mandate_gap",
      )!;
      if (fact.kind !== "mandate_gap")
        throw new Error("Missing mandate fixture");
      fact.numbers = {
        ...fact.numbers,
        boundary,
        actual_pct: actual,
        limit_pct: limit,
        gap_pct: breached ? 0.1 : 0,
      };
      fact.what = `Equity is ${actual}% against a ${limit}% ${boundary}.`;
      projection.pre_reads["CL-0003"].rules_money = [];
      projection.pre_reads["CL-0003"].what_changed = [];
      vi.stubGlobal(
        "fetch",
        vi.fn(() => Promise.resolve(new Response(JSON.stringify(projection)))),
      );
      render(
        <MemoryRouter initialEntries={["/clients/CL-0003/pre-read"]}>
          <App />
        </MemoryRouter>,
      );
      const top = await screen.findByRole("region", {
        name: "Client facts",
      });
      const cards = within(top).getAllByRole("article");
      const mandate = cards.find((card) =>
        within(card).queryByRole("heading", { name: fact.what }),
      )!;
      expect(mandate).toHaveTextContent(fact.what);
      expect(mandate).not.toHaveTextContent("High");
      expect(mandate).not.toHaveTextContent("Within limit");
      expect(mandate).not.toHaveTextContent("Ask");
      expect(cards.at(-1)).toBe(mandate);
    },
  );

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
    const search = within(switcher).getByRole("searchbox", {
      name: "Search clients",
    });
    const results = within(switcher).getByRole("status");
    expect(results).toHaveTextContent("2 clients, ranked by priority");

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
    expect(results).toHaveTextContent("1 of 2 clients shown");
    expect(search).toHaveFocus();

    await user.clear(search);
    await user.type(search, "nobody");
    expect(results).toHaveTextContent("0 of 2 clients shown");
    expect(within(switcher).getByText("No match for “nobody”.")).toBeVisible();

    await user.click(
      within(switcher).getByRole("button", { name: "Clear client search" }),
    );
    expect(results).toHaveTextContent("2 clients, ranked by priority");
    expect(search).toHaveFocus();
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
    expect(screen.getByText("Data health unavailable")).toBeVisible();
    expect(screen.getByRole("heading", { name: "What changed" })).toBeVisible();

    // The fact preview stays visible across tabs in projection order.
    const top = screen.getByRole("region", { name: "Client facts" });
    expect(
      within(top)
        .getAllByRole("heading", { level: 3 })
        .map((node) => node.textContent),
    ).toEqual([
      "German inheritance tax instalment starts in 36 days.",
      "Equity is above the mandate limit.",
    ]);
    expect(top).not.toHaveTextContent("brought back inside");
    expect(top).not.toHaveTextContent("Liquid assets cover");
    // The uncertainty cites the gap fact only, so it rides that card alone.
    expect(
      within(top).getAllByText("To confirm: Confirm intent before advising."),
    ).toHaveLength(1);
    // Only the mandate fact puts a value on a scale, so only its card draws a
    // bar; the deadline's inputs are money and days.
    const bars = within(top).getAllByText(/against the 30% maximum/);
    expect(bars).toHaveLength(1);
    expect(bars[0]).toHaveTextContent(
      "Equity allocation against the 30% maximum",
    );

    await user.click(screen.getByRole("tab", { name: "Insights" }));
    expect(
      screen.getByText("Every fact for this client is shown above."),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "More client facts" }),
    ).toBeVisible();
    expect(within(top).getAllByRole("heading", { level: 3 })).toHaveLength(2);
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

  it("retrieves the RM notes that answer a question typed into Memory", async () => {
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

    await user.click(await screen.findByRole("tab", { name: "Memory" }));
    const search = screen.getByRole("searchbox", {
      name: "Search this client's RM notes",
    });
    expect(
      screen.getByText(
        "Searching 2 notes and 1 extracted belief for this client.",
      ),
    ).toBeVisible();

    // Question words are dropped, so the query retrieves on "safe" alone.
    await user.type(search, "What did she say about safe?");
    expect(
      screen.getByText("1 of 2 notes and 1 of 1 belief mention safe."),
    ).toBeVisible();
    expect(
      screen.getByText("2026-02-16 \u00b7 Meeting \u00b7 Priscilla Ong"),
    ).toBeVisible();
    expect(
      screen.queryByText("2026-03-02 \u00b7 Call \u00b7 Priscilla Ong"),
    ).not.toBeInTheDocument();
    // The matching word is marked in both the note and the extracted belief.
    expect(screen.getAllByText("safe", { selector: "mark" })).toHaveLength(2);

    const noteSource = within(
      screen.getByRole("region", { name: "RM notes" }),
    ).getByRole("button", { name: "Why?" });
    // Exercise keyboard activation here; browser tests cover pointer activation.
    noteSource.focus();
    expect(noteSource).toHaveFocus();
    await user.keyboard("{Enter}");
    const sourceTrail = await screen.findByRole(
      "dialog",
      { name: "Why?" },
      { timeout: 3000 },
    );
    expect(sourceTrail).toHaveTextContent("data/rm_notes.json · row note:1");
    expect(sourceTrail).toHaveTextContent("Keep it safe.");
    expect(sourceTrail).not.toHaveTextContent("Berlin apartment");
    expect(
      within(sourceTrail).queryByRole("region", { name: "Generated claim" }),
    ).not.toBeInTheDocument();
    await user.click(
      within(sourceTrail).getByRole("button", { name: "Close source trail" }),
    );
    expect(noteSource).toHaveFocus();
    expect(search).toHaveValue("What did she say about safe?");

    await user.clear(search);
    await user.type(search, "custody");
    expect(
      screen.getByText("No note mentions custody. Try another word."),
    ).toBeVisible();
    expect(
      screen.getByText("No recorded belief mentions custody."),
    ).toBeVisible();
  });

  it("retrieves and highlights short financial terms without substring matches", async () => {
    const projection = structuredClone(projectionFixture);
    projection.evidence["note:1"].record.note =
      "Discuss UK tax, FX hedging and US tuition in Q2.";
    projection.evidence["note:2"].record.note =
      "Asked about a ukulele, Q20 and USD expenses.";
    projection.pre_reads["CL-0003"].beliefs[0].text = "Discuss FX in Q2.";
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(JSON.stringify(projection)))),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/clients/CL-0003/pre-read"]}>
        <App />
      </MemoryRouter>,
    );
    await user.click(await screen.findByRole("tab", { name: "Memory" }));
    const search = screen.getByRole("searchbox", {
      name: "Search this client's RM notes",
    });
    const notes = screen.getByRole("region", { name: "RM notes" });
    for (const term of ["UK", "fx", "Q2", "U.K.", "u.k", "U.S.", "u.s"]) {
      await user.clear(search);
      await user.type(search, term);
      expect(
        within(notes).getAllByRole("button", { name: "Why?" }),
      ).toHaveLength(1);
      expect(notes.querySelector("mark")?.textContent?.toLowerCase()).toBe(
        term.replaceAll(".", "").toLowerCase(),
      );
      expect(search).toHaveValue(term);
      expect(notes).not.toHaveTextContent("ukulele");
    }
    // A region abbreviation remains searchable; lowercase "us" is question glue.
    await user.clear(search);
    await user.type(search, "What did she say to us about FX?");
    expect(
      within(
        screen.getByRole("region", { name: "Search the client memory" }),
      ).getByRole("status"),
    ).toHaveTextContent("mention fx.");
    expect(within(notes).getAllByRole("button", { name: "Why?" })).toHaveLength(
      1,
    );
    expect(
      screen
        .getByRole("region", { name: "Extracted beliefs" })
        .querySelector("mark"),
    ).toHaveTextContent("FX");
    await user.clear(search);
    await user.type(search, "US");
    expect(
      within(
        screen.getByRole("region", { name: "Search the client memory" }),
      ).getByRole("status"),
    ).toHaveTextContent("mention us.");
    expect(within(notes).getAllByRole("button", { name: "Why?" })).toHaveLength(
      1,
    );
    expect(notes).toHaveTextContent("US tuition");
    expect(notes.querySelector("mark")).toHaveTextContent("US");
  });

  it("discloses missing briefing fields and displays supplied cash-need facts", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(projectionResponse())),
    );
    render(
      <MemoryRouter initialEntries={["/clients/CL-0003/pre-read"]}>
        <App />
      </MemoryRouter>,
    );

    const needs = await screen.findByRole("region", {
      name: "Planned cash needs",
    });
    expect(needs).toHaveTextContent(
      "German inheritance tax instalment starts in 36 days.",
    );
    expect(needs).toHaveTextContent("3,400,000");
    expect(needs).toHaveTextContent(
      "Private-fund commitments and open follow-ups are not available",
    );
    expect(
      screen.getByText(
        /A two-minute summary, discussion topics, and suggested questions are not yet available/,
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("region", { name: "Three discussion topics" }),
    ).not.toBeInTheDocument();
    expect(needs).not.toHaveTextContent("Due 2026-10-01 to 2026-12-31");
  });

  it("makes every PRD 5.5 brief block a named region the RM can jump to", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(projectionResponse())),
    );
    render(
      <MemoryRouter initialEntries={["/clients/CL-0003/pre-read"]}>
        <App />
      </MemoryRouter>,
    );

    await screen.findByRole("region", { name: "What changed" });
    for (const name of [
      "What changed",
      "You said / Data says",
      "Rules & money",
      "Planned cash needs",
      "Suggested opening",
      "What we are not sure about",
      "Where you left off",
    ]) {
      const block = screen.getByRole("region", { name });
      expect(within(block).getByRole("heading", { name })).toBeVisible();
    }
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

    // Scope the action to its brief section.
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

  it("discloses an unresolved claim citation even when no evidence resolves", async () => {
    const projection = structuredClone(projectionFixture);
    projection.facts["CL-0003"] = projection.facts["CL-0003"].filter(
      (fact) => fact.id !== "CL-0003:fact:gap",
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(JSON.stringify(projection)))),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/clients/CL-0003/pre-read"]}>
        <App />
      </MemoryRouter>,
    );
    const changed = await screen.findByRole("region", { name: "What changed" });
    await user.click(
      within(changed).getAllByRole("button", { name: "Why?" })[0],
    );
    const drawer = screen.getByRole("dialog", { name: "Why?" });
    expect(within(drawer).getByRole("alert")).toHaveTextContent(
      "Evidence trail is incomplete.",
    );
    expect(within(drawer).getByRole("listitem")).toHaveTextContent(
      "CL-0003:fact:gap",
    );
    expect(within(drawer).getByText("Equity increased.")).toBeVisible();
    expect(within(drawer).queryAllByRole("article")).toHaveLength(0);
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
    expect(
      within(screen.getByRole("main")).getByRole("status"),
    ).toHaveTextContent(/CL-9999 was not found/);
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

    // The header states the review status of the brief on the page itself,
    // not only inside the evidence drawer (PRD 6.6).
    expect(
      screen.getByText("Generated \u00b7 awaiting RM review"),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Approve pre-read" }));
    await waitFor(() => expect(bookedMeeting()).toHaveTextContent("Ready"));
    expect(screen.getByText("Approved by the RM")).toBeVisible();
  });

  it("keeps saved wording through client switches, failed edits, and approval", async () => {
    let failSave = false;
    const requests: ReviewRequest[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (!String(input).endsWith("/api/reviews")) {
          return Promise.resolve(projectionResponse());
        }
        const request = JSON.parse(String(init?.body)) as ReviewRequest;
        requests.push(request);
        return Promise.resolve(
          failSave
            ? new Response(JSON.stringify({ detail: "Ledger unavailable" }), {
                status: 503,
              })
            : new Response(
                JSON.stringify({
                  review: {
                    ...request,
                    review_id: "r-edit",
                    rm: "Priscilla Ong",
                    timestamp: "2026-09-05T09:00:00+00:00",
                  },
                }),
              ),
        );
      }),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/clients/CL-0003/pre-read"]}>
        <App />
      </MemoryRouter>,
    );
    const opening = () =>
      screen.getByRole("region", { name: "Suggested opening" });
    const selectClient = async (name: RegExp) => {
      await user.click(
        within(
          screen.getByRole("navigation", { name: "Client switcher" }),
        ).getByRole("button", { name }),
      );
    };
    const saved = "May we discuss your cash needs first?";
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    await user.clear(screen.getByLabelText("Edit the opening line"));
    await user.click(screen.getByRole("button", { name: "Save edit" }));
    expect(requests).toHaveLength(0);
    expect(screen.getByLabelText("Edit the opening line")).toHaveFocus();
    expect(screen.getByLabelText("Edit the opening line")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    await user.type(screen.getByLabelText("Edit the opening line"), saved);
    expect(
      screen.queryByText("Enter an opening line before saving."),
    ).toBeNull();
    expect(opening()).not.toHaveTextContent(saved);
    await user.click(screen.getByRole("button", { name: "Save edit" }));
    await waitFor(() => expect(opening()).toHaveTextContent(saved));

    await selectClient(/Abdullah/);
    expect(opening()).not.toHaveTextContent(saved);
    await selectClient(/Margarethe/);
    expect(opening()).toHaveTextContent(saved);
    expect(screen.getByText("Edited by the RM")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Edit" }));
    expect(screen.getByLabelText("Edit the opening line")).toHaveValue(saved);
    await user.clear(screen.getByLabelText("Edit the opening line"));
    await user.type(screen.getByLabelText("Edit the opening line"), "   ");
    await user.click(screen.getByRole("button", { name: "Save edit" }));
    expect(requests).toHaveLength(1);
    expect(opening()).toHaveTextContent(saved);
    expect(screen.getByText("Edited by the RM")).toBeVisible();
    await user.clear(screen.getByLabelText("Edit the opening line"));
    await user.type(
      screen.getByLabelText("Edit the opening line"),
      "Unsaved replacement",
    );
    failSave = true;
    await user.click(screen.getByRole("button", { name: "Save edit" }));
    await screen.findByRole("alert");
    expect(opening()).toHaveTextContent(saved);
    expect(opening()).not.toHaveTextContent("Unsaved replacement");

    const requestCount = requests.length;
    await user.click(screen.getByRole("button", { name: "Cancel edit" }));
    expect(screen.queryByLabelText("Edit the opening line")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("button", { name: "Edit" })).toHaveFocus();
    expect(screen.getByText("Edited by the RM")).toBeVisible();
    expect(requests).toHaveLength(requestCount);
    await user.click(screen.getByRole("button", { name: "Edit" }));
    expect(screen.getByLabelText("Edit the opening line")).toHaveValue(saved);
    await user.click(screen.getByRole("button", { name: "Cancel edit" }));

    failSave = false;
    await user.click(screen.getByRole("button", { name: "Approve pre-read" }));
    await screen.findByText("Approved by the RM");
    expect(requests.at(-1)).toEqual({
      client_id: "CL-0003",
      action: "Approve",
      text: saved,
    });
    expect(opening()).toHaveTextContent(saved);
    await selectClient(/Abdullah/);
    await selectClient(/Margarethe/);
    expect(opening()).toHaveTextContent(saved);
    await user.click(screen.getByRole("tab", { name: "Insights" }));
    expect(screen.getByRole("tabpanel")).toHaveTextContent(saved);
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
    expect(
      screen.getByRole("button", { name: "Approve pre-read" }),
    ).toHaveFocus();
  });
});

describe("measure", () => {
  const gap = (
    numbers: Partial<
      Extract<ProjectionFact, { kind: "mandate_gap" }>["numbers"]
    >,
  ) =>
    measure({
      id: "f",
      kind: "mandate_gap",
      what: "",
      source_rows: [],
      event_ids: [],
      confidence: "high",
      numbers: {
        asset_class: "Equity",
        actual_pct: 71.5,
        limit_pct: 30,
        boundary: "maximum",
        gap_pct: 41.5,
        scope: "Household look-through",
        ...numbers,
      },
    });

  it("scales past the larger of the value and the limit", () => {
    // 71.5 against a 30% cap: the fill sits near the end and the marker at 38%.
    expect(gap({})).toMatchObject({ actual: 71.5, limit: 30, scale: 78.65 });
  });

  it("reads the breach in the direction the boundary points", () => {
    expect(gap({})?.breached).toBe(true);
    expect(gap({ actual_pct: 12.8, limit_pct: 20 })?.breached).toBe(false);
    // A minimum band is breached from below, not above.
    expect(gap({ boundary: "minimum", actual_pct: 23.4 })?.breached).toBe(true);
    expect(
      gap({ boundary: "minimum", actual_pct: 7.1, limit_pct: 0 })?.breached,
    ).toBe(false);
  });

  it("draws nothing for a degenerate 0% against 0% band", () => {
    // Several clients carry one; without this the fill width is NaN%.
    expect(
      gap({ boundary: "minimum", actual_pct: 0, limit_pct: 0 }),
    ).toBeUndefined();
  });
});
