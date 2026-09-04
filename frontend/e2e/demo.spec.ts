import { expect, test } from "@playwright/test";

for (const width of [1280, 390]) {
  test(`client search tolerates name separators at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/");
    const switcher = page.getByRole("navigation", { name: "Client switcher" });
    const search = switcher.getByRole("searchbox", { name: "Search clients" });
    for (const query of [
      "Voss Brenner",
      "  VOSS   BRENNER  ",
      "Voss-Brenner",
      "Voss\u2011Brenner",
    ]) {
      await search.fill(query);
      await expect(switcher.getByRole("status")).toHaveText(
        "1 of 20 clients shown",
      );
      await expect(switcher.getByRole("listitem")).toHaveCount(1);
      await expect(
        switcher.getByRole("button", { name: /Margarethe Voss-Brenner/ }),
      ).toBeVisible();
      await expect(search).toBeFocused();
    }
    await switcher
      .getByRole("button", { name: /Margarethe Voss-Brenner/ })
      .click();
    await expect(
      page.getByRole("heading", {
        name: "Margarethe Voss-Brenner",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      switcher.getByRole("button", { name: /Margarethe Voss-Brenner/ }),
    ).toHaveAttribute("aria-current", "true");
    await search.fill("Al Mansoori");
    await expect(switcher.getByRole("status")).toHaveText(
      "1 of 20 clients shown",
    );
    await switcher
      .getByRole("button", { name: /Abdullah Al-Mansoori/ })
      .click();
    await expect(
      page.getByRole("heading", { name: "Abdullah Al-Mansoori", exact: true }),
    ).toBeVisible();
    await search.focus();
    await switcher.getByRole("button", { name: "clear", exact: true }).click();
    await expect(switcher.getByRole("status")).toHaveText(
      "20 clients, ranked by priority",
    );
    await expect(switcher.getByRole("listitem").first()).toContainText(
      "Margarethe Voss-Brenner",
    );
    await expect(search).toBeFocused();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`client profile sources are reachable from every tab at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const why = page.getByRole("button", { name: "Why this profile?" });
    const drawer = page.getByRole("dialog", { name: "Why?" });
    for (const tab of ["Overview", "Insights", "Data", "Memory"]) {
      await page.getByRole("tab", { name: tab, exact: true }).click();
      await why.focus();
      await page.keyboard.press("Enter");
      await expect(drawer).toContainText(
        "Margarethe Voss-Brenner has a Conservative profile.",
      );
      await expect(drawer).toContainText(
        "data/clients.csv · row clients:CL-0003",
      );
      await expect(drawer).toContainText("risk tolerance score");
      await expect(drawer).not.toContainText("data/holdings.csv");
      await page.keyboard.press("Escape");
      await expect(why).toBeFocused();
      await expect(page.getByRole("tabpanel", { name: tab })).toBeVisible();
    }
    await page
      .getByRole("navigation", { name: "Client switcher" })
      .getByRole("button", { name: /Alistair Pemberton-Hale/ })
      .click();
    await why.click();
    await expect(drawer).toContainText("Alistair Pemberton-Hale");
    await expect(drawer).toContainText(
      "data/clients.csv · row clients:CL-0007",
    );
    await expect(drawer).not.toContainText("CL-0003");
    expect(
      await drawer.evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBe(true);
    await page.keyboard.press("Escape");
    await expect(why).toBeFocused();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`within-limit mandates do not displace active topics at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0019/pre-read");
    const top = page.getByRole("region", { name: "Top insights", exact: true });
    const topics = page.getByRole("region", {
      name: "Three discussion topics",
    });
    await expect(top.getByRole("heading", { level: 3 })).toHaveCount(3);
    await expect(top).not.toContainText("Structured Products");
    await expect(top).toContainText("Connected positions represent 42.1%");
    await expect(topics).not.toContainText("Structured Products");

    await page.getByRole("tab", { name: "Insights", exact: true }).click();
    const mandate = page.getByRole("article").filter({
      has: page.getByRole("heading", {
        name: "Structured Products is 12.9% against a 15% maximum.",
        exact: true,
      }),
    });
    await expect(mandate).toContainText("Within limit");
    await expect(mandate).toContainText("Within the 15% maximum");
    await expect(mandate).toContainText(
      "Does the 15% maximum for Structured Products still fit your objectives?",
    );
    await expect(mandate).not.toContainText("brought back inside");
    await mandate.getByRole("button", { name: "Why?" }).click();
    const drawer = page.getByRole("dialog", { name: "Why?" });
    await expect(drawer).toContainText("Structured Products is 12.9%");
    await expect(drawer).toContainText("data/mandates.csv");
    await page.keyboard.press("Escape");
    await expect(mandate.getByRole("button", { name: "Why?" })).toBeFocused();
    expect(
      await mandate.evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBe(true);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);

    await page.goto("/clients/CL-0003/pre-read");
    const breached = top.getByRole("article").first();
    await expect(breached).toContainText("High");
    await expect(breached).toContainText(
      "Equity is 71.5% against a 30% maximum.",
    );
    await expect(breached).toContainText("brought back inside");
  });

  test(`client search reports results without moving focus at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/");
    const switcher = page.getByRole("navigation", { name: "Client switcher" });
    const search = switcher.getByRole("searchbox", { name: "Search clients" });
    const results = switcher.getByRole("status");
    await expect(results).toHaveText("20 clients, ranked by priority");

    await search.fill("Margarethe");
    await expect(results).toHaveText("1 of 20 clients shown");
    await expect(results).toHaveAttribute("aria-atomic", "true");
    await expect(switcher.getByRole("listitem")).toHaveCount(1);
    await expect(search).toBeFocused();

    await search.fill("nobody");
    await expect(results).toHaveText("0 of 20 clients shown");
    await expect(switcher.getByText("No match for “nobody”.")).toBeVisible();
    await expect(search).toBeFocused();
    await search.press("ControlOrMeta+A");
    await search.press("Backspace");
    await expect(results).toHaveText("20 clients, ranked by priority");
    await expect(search).toBeFocused();
    await expect(switcher.getByRole("listitem")).toHaveCount(20);

    await search.fill("   ");
    await expect(results).toHaveText("20 clients, ranked by priority");
    await switcher.getByRole("button", { name: "clear", exact: true }).click();
    await expect(search).toHaveValue("");
    await expect(search).toBeFocused();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
    ).toBe(false);
  });

  test(`short Memory queries filter notes at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0007/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const searchRegion = page.getByRole("region", {
      name: "Search the client memory",
    });
    const search = searchRegion.getByRole("searchbox");
    const notes = page.getByRole("region", { name: "RM notes", exact: true });
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(2);
    await search.fill("UK");
    await expect(searchRegion.getByRole("status")).toContainText(
      "1 of 2 notes",
    );
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(1);
    await expect(notes.locator("mark")).toHaveText("UK");
    await expect(notes).toContainText("tax questions remain unresolved");
    await expect(notes).not.toContainText("additional gold purchase");
    await notes.getByRole("button", { name: "Why?" }).click();
    await expect(page.getByRole("dialog", { name: "Why?" })).toContainText(
      "N-011",
    );
    await page.keyboard.press("Escape");
    await expect(notes.getByRole("button", { name: "Why?" })).toBeFocused();
    await expect(search).toHaveValue("UK");
    await search.fill("FX");
    await expect(notes).toContainText("No note mentions fx. Try another word.");
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(0);
    await searchRegion
      .getByRole("button", { name: "clear", exact: true })
      .click();
    await expect(search).toHaveValue("");
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(2);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`incomplete evidence is disclosed at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.route("**/api/monday-brief", async (route) => {
      const response = await route.fetch();
      const projection = await response.json();
      const fact = projection.facts["CL-0003"].find(
        (item: { kind: string }) => item.kind === "mandate_gap",
      );
      // One missing source and event must not disappear behind the valid rows.
      fact.source_rows.push(
        "holdings:missing-source",
        "holdings:missing-source",
      );
      fact.event_ids.push("event:missing-event");
      await route.fulfill({ response, json: projection });
    });
    await page.goto("/clients/CL-0003/pre-read");
    const why = page
      .getByRole("region", { name: "Top insights", exact: true })
      .getByRole("button", { name: "Why?" });
    await why.first().click();
    const drawer = page.getByRole("dialog", { name: "Why?" });
    const warning = drawer.getByRole("alert");
    await expect(warning).toContainText("Evidence trail is incomplete");
    await expect(warning.getByRole("listitem")).toHaveCount(2);
    await expect(warning).toContainText("holdings:missing-source");
    await expect(warning).toContainText("event:missing-event");
    await expect(drawer).toContainText("Deterministic fact");
    await expect(drawer).toContainText("data/holdings.csv");
    expect(
      await warning.evaluate(
        (element) => element.scrollWidth <= element.clientWidth,
      ),
    ).toBe(true);
    expect(
      await warning.evaluate(
        (element) => element.scrollHeight <= element.clientHeight,
      ),
    ).toBe(true);
    await page.keyboard.press("Escape");
    await expect(why.first()).toBeFocused();
    await why.nth(1).click();
    await expect(drawer).toBeVisible();
    await expect(drawer.getByRole("alert")).toHaveCount(0);
  });

  test(`RM note sources preserve search and keyboard focus at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const notes = page.getByRole("region", { name: "RM notes", exact: true });
    const sources = notes.getByRole("button", { name: "Why?" });
    await expect(sources).toHaveCount(2);
    const search = page.getByRole("searchbox", {
      name: "Search this client's RM notes",
    });

    for (const [query, date, otherDate] of [
      ["risk", "2026-02-16", "2026-05-29"],
      ["boring", "2026-05-29", "2026-02-16"],
    ]) {
      await search.fill(query);
      await expect(sources).toHaveCount(1);
      await sources.focus();
      await page.keyboard.press("Enter");
      const drawer = page.getByRole("dialog", { name: "Why?" });
      await expect(drawer).toBeVisible();
      await expect(drawer.getByRole("article")).toHaveCount(1);
      await expect(drawer).toContainText("data/rm_notes.json · row rm_notes:");
      await expect(drawer).toContainText(date);
      await expect(drawer).not.toContainText(otherDate);
      await expect(drawer).toContainText("CL-0003");
      await expect(drawer).toContainText("Priscilla Ong");
      await expect(
        drawer.getByRole("region", { name: "Generated claim" }),
      ).toHaveCount(0);
      expect(
        await drawer.evaluate(
          (element) => element.scrollWidth <= element.clientWidth,
        ),
      ).toBe(true);
      await page.keyboard.press("Escape");
      await expect(drawer).toHaveCount(0);
      await expect(sources).toBeFocused();
      await expect(search).toHaveValue(query);
      await expect(notes.locator("mark").first()).toContainText(query);
    }
  });

  test(`client navigation moves keyboard focus into the new screen at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/");
    const main = page.getByRole("main");
    await expect(main).toBeVisible();
    await expect(main).not.toBeFocused();
    const switcher = page.getByRole("navigation", { name: "Client switcher" });
    await switcher.getByRole("button", { name: /Margarethe/ }).focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/CL-0003\/pre-read$/);
    await expect(main).toBeFocused();
    await expect(main).toHaveCSS("outline-style", "solid");
    await page.keyboard.press("Tab");
    await expect(
      main.getByRole("button", { name: /RM dashboard/ }),
    ).toBeFocused();

    // The meeting that triggered navigation unmounts with its old client.
    const meetings = page.getByRole("navigation", {
      name: "This week's meetings",
    });
    await meetings.getByRole("button", { name: /Abdullah/ }).focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/CL-0019\/pre-read$/);
    await expect(main).toBeFocused();
    await expect(main).toHaveJSProperty("scrollTop", 0);

    await page.getByRole("tab", { name: "Scenario rehearsal" }).focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/CL-0019\/scenario$/);
    await expect(main).toBeFocused();
    await page.goBack();
    await expect(page).toHaveURL(/CL-0019\/pre-read$/);
    await expect(main).toBeFocused();
    await main.getByRole("button", { name: /RM dashboard/ }).press("Enter");
    await expect(page).toHaveURL(/\/$/);
    await expect(main).toBeFocused();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
    ).toBe(false);
  });

  test(`dashboard tabs lead keyboard users into their named panel at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    await page.getByRole("tab", { name: "Overview", exact: true }).click();

    for (const name of ["Overview", "Insights", "Data", "Memory"]) {
      const tab = page.getByRole("tab", { name, exact: true });
      await expect(tab).toBeFocused();
      await tab.press("Enter");
      await expect(tab).toHaveAttribute("aria-selected", "true");
      const panel = page.getByRole("tabpanel", { name, exact: true });
      await page.keyboard.press("Tab");
      await expect(panel).toBeFocused();
      await expect(tab).toHaveAttribute(
        "aria-controls",
        await panel.evaluate((element) => element.id),
      );
      await expect(panel).toHaveCSS("outline-style", "solid");
      await page.keyboard.press("Tab");
      expect(
        await panel.evaluate((element) =>
          element.contains(document.activeElement),
        ),
      ).toBe(true);
      await page.keyboard.press("Shift+Tab");
      await expect(panel).toBeFocused();
      await page.keyboard.press("Shift+Tab");
      await expect(tab).toBeFocused();
      await page.keyboard.press("ArrowRight");
    }
    await expect(
      page.getByRole("tab", { name: "Overview", exact: true }),
    ).toBeFocused();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
      ),
    ).toBe(false);
  });

  test(`review decisions require saving or cancelling the opening edit at ${width}px`, async ({
    page,
  }) => {
    const submitted: { action: string; text: string }[] = [];
    let failSave = true;
    await page.route("**/api/reviews", async (route) => {
      const request = route.request().postDataJSON();
      submitted.push(request);
      await route.fulfill({
        status: request.action === "Edit" && failSave ? 503 : 200,
        contentType: "application/json",
        body: JSON.stringify(
          request.action === "Edit" && failSave
            ? { detail: "Ledger unavailable" }
            : {
                review: {
                  ...request,
                  review_id: "edit-before-review",
                  rm: "Priscilla Ong",
                  timestamp: "2026-09-05T09:00:00+00:00",
                },
              },
        ),
      });
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const edit = page.getByRole("button", { name: "Edit", exact: true });
    const approve = page.getByRole("button", { name: "Approve pre-read" });
    const reject = page.getByRole("button", { name: "Reject", exact: true });
    const editor = page.getByLabel("Edit the opening line");
    await edit.click();
    const original = await editor.inputValue();
    await editor.fill("Unsaved draft");
    for (const button of [approve, reject]) {
      await expect(button).toBeDisabled();
      await expect(button).toHaveAccessibleDescription(
        "Save or cancel your edit before approving or rejecting.",
      );
      await button.focus();
      await button.press("Enter");
      await button.press("Space");
      await button.evaluate((element: HTMLButtonElement) => element.click());
    }
    await expect(editor).toHaveValue("Unsaved draft");
    await expect(
      page.getByText("Generated · awaiting RM review"),
    ).toBeVisible();
    expect(submitted).toHaveLength(0);
    await page.getByRole("button", { name: "Cancel edit" }).click();
    await expect(approve).toBeEnabled();
    await expect(reject).toBeEnabled();
    await reject.click();
    await expect(page.getByText("Rejected by the RM")).toBeVisible();
    expect(submitted.at(-1)).toMatchObject({
      action: "Reject",
      text: original,
    });

    await edit.click();
    await editor.fill("Saved wording for approval");
    await page.getByRole("button", { name: "Save edit" }).click();
    await expect(page.getByRole("alert")).toContainText("Ledger unavailable");
    await expect(approve).toBeDisabled();
    await expect(reject).toBeDisabled();
    await expect(editor).toHaveValue("Saved wording for approval");
    failSave = false;
    await page.getByRole("button", { name: "Save edit" }).click();
    await expect(editor).toHaveCount(0);
    await expect(approve).toBeEnabled();
    await expect(reject).toBeEnabled();
    await approve.click();
    await expect(page.getByText("Approved by the RM")).toBeVisible();
    expect(submitted.at(-1)).toMatchObject({
      action: "Approve",
      text: "Saved wording for approval",
    });
    expect(submitted.map((request) => request.action)).toEqual([
      "Reject",
      "Edit",
      "Edit",
      "Approve",
    ]);
  });

  test(`pending opening saves protect wording and recover at ${width}px`, async ({
    page,
  }) => {
    let finishReview!: () => void;
    let failSave = true;
    const submitted: string[] = [];
    await page.route("**/api/reviews", async (route) => {
      const request = route.request().postDataJSON();
      submitted.push(request.text);
      await new Promise<void>((resolve) => {
        finishReview = resolve;
      });
      await route.fulfill({
        status: failSave ? 503 : 200,
        contentType: "application/json",
        body: JSON.stringify(
          failSave
            ? { detail: "Ledger unavailable" }
            : {
                review: {
                  ...request,
                  review_id: "pending-edit",
                  rm: "Priscilla Ong",
                  timestamp: "2026-09-05T09:00:00+00:00",
                },
              },
        ),
      });
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const edit = page.getByRole("button", { name: "Edit", exact: true });
    await edit.click();
    const editor = page.getByLabel("Edit the opening line");
    const checkpoint = page.getByRole("region", { name: "RM checkpoint" });
    await editor.fill("Submitted wording");
    for (const wording of ["Submitted wording", "Corrected wording"]) {
      await page.getByRole("button", { name: "Save edit" }).click();
      await expect(checkpoint).toHaveAttribute("aria-busy", "true");
      await expect.poll(() => submitted.at(-1)).toBe(wording);
      await expect(editor).not.toBeEditable();
      await editor.focus();
      await editor.press("End");
      await page.keyboard.type(" extra unsaved wording");
      await expect(editor).toHaveValue(wording);
      finishReview();
      await expect(checkpoint).toHaveAttribute("aria-busy", "false");
      if (failSave) {
        await expect(page.getByRole("alert")).toContainText(
          "Ledger unavailable",
        );
        await expect(editor).toBeEditable();
        await expect(editor).toBeFocused();
        await editor.fill("Corrected wording");
        failSave = false;
      }
    }
    await expect(editor).toHaveCount(0);
    await expect(edit).toBeFocused();
    await expect(edit).toBeInViewport();
    await expect(
      page.getByRole("region", { name: "Suggested opening" }),
    ).toContainText("Corrected wording");
    expect(submitted).toEqual(["Submitted wording", "Corrected wording"]);
    await edit.click();
    await expect(editor).toBeEditable();
    await expect(editor).toHaveValue("Corrected wording");
  });

  test(`blank opening edits preserve the brief at ${width}px`, async ({
    page,
  }) => {
    let reviewRequests = 0;
    page.on("request", (request) => {
      if (request.url().endsWith("/api/reviews")) reviewRequests += 1;
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const edit = page.getByRole("button", { name: "Edit", exact: true });
    await edit.click();
    const editor = page.getByLabel("Edit the opening line");
    const original = await editor.inputValue();
    for (const blank of ["", "   \n  "]) {
      await editor.fill(blank);
      const save = page.getByRole("button", { name: "Save edit" });
      await save.focus();
      await save.press("Enter");
      await expect(editor).toBeFocused();
      await expect(editor).toHaveAttribute("aria-invalid", "true");
      await expect(editor).toHaveAccessibleDescription(
        /Enter an opening line before saving/,
      );
      await expect(
        page.getByText("Enter an opening line before saving."),
      ).toBeInViewport();
      await expect(
        page.getByRole("region", { name: "Suggested opening" }),
      ).toContainText(original);
      await expect(
        page.getByText("Generated · awaiting RM review"),
      ).toBeVisible();
    }
    expect(reviewRequests).toBe(0);
    await editor.fill("A valid opening");
    await expect(editor).not.toHaveAttribute("aria-invalid", "true");
    await editor.fill("");
    await page.getByRole("button", { name: "Save edit" }).click();
    await page.getByRole("button", { name: "Cancel edit" }).click();
    await edit.click();
    await expect(editor).toHaveValue(original);
    await expect(editor).not.toHaveAttribute("aria-invalid", "true");
    expect(reviewRequests).toBe(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
    ).toBe(false);
  });

  test(`cancel opening edit restores wording and focus at ${width}px`, async ({
    page,
  }) => {
    let reviewRequests = 0;
    page.on("request", (request) => {
      if (request.url().endsWith("/api/reviews")) reviewRequests += 1;
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const edit = page.getByRole("button", { name: "Edit", exact: true });
    await edit.click();
    const editor = page.getByLabel("Edit the opening line");
    const original = await editor.inputValue();
    await editor.fill("Discard this unsaved draft");
    const cancel = page.getByRole("button", { name: "Cancel edit" });
    await cancel.focus();
    await cancel.press("Enter");
    await expect(editor).toHaveCount(0);
    await expect(edit).toBeFocused();
    await expect(edit).toBeInViewport();
    await expect(
      page.getByRole("region", { name: "Suggested opening" }),
    ).toContainText(original);
    await expect(
      page.getByText("Generated · awaiting RM review"),
    ).toBeVisible();
    await edit.press("Enter");
    await expect(editor).toHaveValue(original);
    await expect(cancel).toBeInViewport();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
    ).toBe(false);
    expect(reviewRequests).toBe(0);
  });

  test(`review shortcut reaches the checkpoint from every tab at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");

    for (const tab of ["Memory", "Data", "Insights", "Overview"]) {
      await page.getByRole("tab", { name: tab, exact: true }).click();
      const shortcut = page.getByRole("button", {
        name: "Review meeting brief",
      });
      await shortcut.focus();
      await shortcut.press("Enter");

      await expect(
        page.getByRole("tab", { name: "Overview", exact: true }),
      ).toHaveAttribute("aria-selected", "true");
      await expect(
        page.getByRole("button", { name: "Approve pre-read" }),
      ).toBeInViewport();
      await expect(
        page.getByRole("region", { name: "RM checkpoint" }),
      ).toBeFocused();
      await page.keyboard.press("Tab");
      await expect(
        page.getByRole("button", { name: "Reject", exact: true }),
      ).toBeFocused();
    }
  });
}

test("the first screen is an RM dashboard, not a calendar", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Who needs you this week" }),
  ).toBeVisible();
  const queue = page.getByRole("list", { name: "Priority queue" });
  await expect(queue.getByRole("listitem")).toHaveCount(5);
  await queue.getByRole("button").first().click();
  await expect(
    page.getByRole("heading", { name: "Margarethe Voss-Brenner" }),
  ).toBeVisible();

  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/");
    const overflows = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    );
    expect(overflows, `home at ${width}px`).toBe(false);
  }
});

test("judge demo path remains navigable and responsive", async ({ page }) => {
  await page.goto("/");
  const switcher = page.getByRole("navigation", { name: "Client switcher" });
  await switcher
    .getByRole("button", { name: /Margarethe Voss-Brenner/ })
    .click();
  // The top three insights are visible without opening a tab (PRD 5.4/12).
  const top = page.getByRole("region", { name: "Top insights" });
  await expect(top.getByRole("article")).toHaveCount(3);
  await expect(top).toContainText("Equity is 71.5% against a 30% maximum.");
  // Each card carries the question to put to the client (PRD 5.4).
  await expect(top).toContainText(
    "Do you want Equity brought back inside the 30% maximum",
  );
  // The mandate card draws the 71.5% fill past the 30% limit marker; the two
  // cards whose facts carry no scale draw nothing.
  await expect(
    top.getByText("Equity allocation against the 30% maximum"),
  ).toBeVisible();
  const fill = top.locator('[aria-hidden="true"] > div').first();
  const [fillBox, trackBox] = [
    await fill.boundingBox(),
    await top.locator('[aria-hidden="true"]').first().boundingBox(),
  ];
  expect(fillBox!.width / trackBox!.width).toBeCloseTo(71.5 / (71.5 * 1.1), 2);

  // The Insights tab carries the insights the top three pushed below the fold.
  await page.getByRole("tab", { name: "Insights" }).click();
  const alsoActive = page.getByRole("region", { name: "Also active" });
  await expect(alsoActive.getByRole("article")).toHaveCount(3);
  // The brief's uncertainty names the three snapshot deltas, so it rides those
  // cards rather than the whole dashboard.
  await expect(alsoActive.getByText(/^To confirm: /)).toHaveCount(3);
  await expect(top.getByRole("article")).toHaveCount(3);
  await page.getByRole("tab", { name: "Overview" }).click();

  // The meeting brief opens on PRD 5.5's summary, agenda and commitments.
  const summary = page.getByRole("region", { name: "Two-minute summary" });
  await expect(summary).toContainText("The meeting is Mon");
  await expect(
    page
      .getByRole("region", { name: "Three discussion topics" })
      .getByRole("listitem"),
  ).toHaveCount(3);
  await expect(
    page.getByRole("region", { name: "Open commitments" }),
  ).toContainText("German inheritance tax instalment");

  await page
    .getByRole("region", { name: "What changed" })
    .getByRole("button", { name: "Why?" })
    .first()
    .click();
  await expect(page.getByRole("dialog", { name: "Why?" })).toContainText(
    "data/holdings.csv",
  );
  await page
    .getByRole("dialog", { name: "Why?" })
    .getByRole("button", { name: "Close source trail" })
    .click();

  await page.getByRole("button", { name: "Edit" }).click();
  await page
    .getByLabel("Edit the opening line")
    .fill("May I walk you through the gap?");
  await page.getByRole("button", { name: "Save edit" }).click();
  await expect(page.getByRole("status").last()).toContainText("Edited");
  const opening = page.getByRole("region", { name: "Suggested opening" });
  await expect(opening).toContainText("May I walk you through the gap?");
  await switcher.getByRole("button", { name: /Abdullah Al-Mansoori/ }).click();
  await expect(opening).not.toContainText("May I walk you through the gap?");
  await switcher
    .getByRole("button", { name: /Margarethe Voss-Brenner/ })
    .click();
  await expect(opening).toContainText("May I walk you through the gap?");
  const approval = page.waitForRequest(
    (request) =>
      request.url().endsWith("/api/reviews") && request.method() === "POST",
  );
  await page.getByRole("button", { name: "Approve pre-read" }).click();
  expect((await approval).postDataJSON()).toMatchObject({
    action: "Approve",
    text: "May I walk you through the gap?",
  });
  await expect(page.getByRole("status").last()).toContainText("Approved");
  await expect(opening).toContainText("May I walk you through the gap?");
  await page
    .getByRole("button", { name: "Rehearse a Strait scenario →" })
    .click();
  await page.getByRole("tab", { name: "Pre-read", exact: true }).click();
  await expect(opening).toContainText("May I walk you through the gap?");
  await opening.getByRole("button", { name: "Why?" }).click();
  await expect(page.getByRole("dialog", { name: "Why?" })).toContainText(
    "May I walk you through the gap?",
  );
  await expect(page.getByRole("dialog", { name: "Why?" })).toContainText(
    "Approved by the RM",
  );
  await page.getByRole("button", { name: "Close source trail" }).click();

  // The compact calendar tracks brief readiness across the dashboard (PRD 5.3).
  const calendar = page.getByRole("navigation", {
    name: "This week's meetings",
  });
  await expect(
    calendar.getByRole("button", { name: /Margarethe Voss-Brenner/ }),
  ).toContainText("Ready");
  await expect(
    calendar.getByRole("button", { name: /Abdullah Al-Mansoori/ }),
  ).toContainText("Needs review");

  // The evidence trail reports who authored the approved claim (PRD 5.7).
  await page
    .getByRole("region", { name: "What changed" })
    .getByRole("button", { name: "Why?" })
    .first()
    .click();
  await expect(page.getByRole("dialog", { name: "Why?" })).toContainText(
    "Approved by the RM",
  );
  await page
    .getByRole("dialog", { name: "Why?" })
    .getByRole("button", { name: "Close source trail" })
    .click();

  // The Memory tab answers a plain question over this client's notes (PRD 4).
  await page.getByRole("tab", { name: "Memory" }).click();
  const notes = page.getByRole("region", { name: "RM notes" });
  await expect(notes).toContainText("never taken a risk with money");
  await expect(notes).toContainText("safe and boring");
  await page
    .getByRole("searchbox", { name: "Search this client's RM notes" })
    .fill("What did she say about risk?");
  await expect(
    page.getByRole("region", { name: "Search the client memory" }),
  ).toContainText("1 of 2 notes");
  await expect(notes).toContainText("never taken a risk with money");
  await expect(notes).not.toContainText("safe and boring");
  // Both occurrences of the retrieved word are marked in the surviving note.
  await expect(notes.locator("mark")).toHaveCount(2);
  await page.getByRole("tab", { name: "Overview" }).click();

  // Selecting a meeting switches the whole dashboard to that client (PRD 5.3).
  await calendar.getByRole("button", { name: /Abdullah Al-Mansoori/ }).click();
  await expect(
    page.getByRole("heading", { name: "Abdullah Al-Mansoori" }),
  ).toBeVisible();

  await page.goto("/clients/CL-0019/scenario");
  await expect(page.locator("#main .scenario-heading .eyebrow")).toHaveText(
    "Abdullah Al-Mansoori",
  );
  await page.getByRole("button", { name: "Strait escalates" }).click();
  await expect(page.locator(".scenario-label")).toHaveText("Strait escalates");
  await page.getByRole("button", { name: "Strait reopens" }).click();
  await expect(page.locator(".scenario-label")).toHaveText("Strait reopens");

  await page.goto("/clients/CL-0003/pre-read");
  for (const viewport of [
    { width: 1280, height: 800 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    for (const tab of ["Overview", "Insights", "Data", "Memory"]) {
      await page.getByRole("tab", { name: tab }).click();
      const overflows = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
      );
      expect(overflows, `${tab} at ${viewport.width}px`).toBe(false);
    }
  }
});

test("the shell fits the viewport and scrolls its own panes", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 800 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Who needs you this week" }),
  ).toBeVisible();

  // The shell is 100vh with overflow hidden, so anything taller than the
  // viewport is unreachable rather than scrollable.
  const fits = await page.evaluate(() => {
    const main = document.getElementById("main");
    return main !== null && main.clientHeight <= window.innerHeight;
  });
  expect(fits, "main pane fits the viewport").toBe(true);

  // The last client sits below the fold, so the switcher list must scroll to it
  // and the RM footer must stay pinned in view.
  const list = page
    .getByRole("navigation", { name: "Client switcher" })
    .getByRole("list");
  await expect(page.getByText("Priscilla Ong · Asia desk")).toBeInViewport();
  const last = list.getByRole("listitem").last();
  await expect(last).not.toBeInViewport();
  await last.scrollIntoViewIfNeeded();
  await expect(last).toBeInViewport();

  // The RM checkpoint sits at the end of the longest screen; the main pane has
  // to reach it.
  await page.goto("/clients/CL-0003/pre-read");
  const approve = page.getByRole("button", { name: "Approve pre-read" });
  await approve.scrollIntoViewIfNeeded();
  await expect(approve).toBeInViewport();
});
