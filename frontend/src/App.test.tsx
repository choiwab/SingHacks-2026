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

    await user.click(
      await screen.findByRole("button", { name: /Margarethe Voss-Brenner/ }),
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
