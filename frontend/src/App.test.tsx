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

    const why = (await screen.findAllByRole("button", { name: "Why?" }))[0];
    await user.click(why);
    const dialog = screen.getByRole("dialog", { name: "Why?" });
    expect(dialog).toBeVisible();
    expect(screen.getByText("Current equity holding")).toBeVisible();
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

    expect(await screen.findByText(/CL-9999 was not found/)).toHaveAttribute(
      "role",
      "status",
    );
    expect(
      screen.getByRole("heading", {
        name: "Calls to make. Meetings to prepare.",
      }),
    ).toBeVisible();
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
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "Review ledger unavailable",
      ),
    );
    expect(
      screen.getByRole("heading", { name: "Margarethe Voss-Brenner" }),
    ).toBeVisible();
  });
});
