import { expect, test } from "@playwright/test";

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

  // The Insights tab carries the insights the top three pushed below the fold.
  await page.getByRole("tab", { name: "Insights" }).click();
  const alsoActive = page.getByRole("region", { name: "Also active" });
  await expect(alsoActive.getByRole("article")).toHaveCount(3);
  await expect(top.getByRole("article")).toHaveCount(3);
  await page.getByRole("tab", { name: "Overview" }).click();

  // The meeting brief opens on PRD 5.5's summary, agenda and commitments.
  const summary = page.getByRole("region", { name: "Two-minute summary" });
  await expect(summary).toContainText("You meet Margarethe Voss-Brenner");
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

  // Selecting a meeting switches the whole dashboard to that client (PRD 5.3).
  await calendar.getByRole("button", { name: /Abdullah Al-Mansoori/ }).click();
  await expect(
    page.getByRole("heading", { name: "Abdullah Al-Mansoori" }),
  ).toBeVisible();

  await page.goto("/clients/CL-0019/scenario");
  await expect(
    page.locator("#main").getByText("Precomputed · Abdullah Al-Mansoori"),
  ).toBeVisible();
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
