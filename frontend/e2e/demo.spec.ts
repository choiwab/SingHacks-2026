import { expect, test } from "@playwright/test";

for (const width of [1280, 390]) {
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
  await page.getByRole("button", { name: "Approve pre-read" }).click();
  await expect(page.getByRole("status").last()).toContainText("Approved");

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
