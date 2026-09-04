import { expect, test } from "@playwright/test";

import { projectionFixture } from "../src/test/fixture";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/monday-brief", async (route) => {
    await route.fulfill({ json: projectionFixture });
  });
  await page.route("**/api/reviews", async (route) => {
    const review = route.request().postDataJSON() as Record<string, string>;
    await route.fulfill({
      json: {
        review: {
          ...review,
          review_id: "review-1",
          rm: "Priscilla Ong",
          timestamp: "2026-08-31T01:30:00Z",
        },
      },
    });
  });
});

test("judge demo path remains navigable and responsive", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Margarethe Voss-Brenner/ }).click();
  await page.getByRole("button", { name: "Why?" }).first().click();
  await expect(page.getByRole("dialog", { name: "Why?" })).toContainText(
    "Current equity holding",
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

  await page.goto("/clients/CL-0019/scenario");
  await expect(page.getByText("Abdullah Al-Nuaimi")).toBeVisible();
  await page.getByRole("button", { name: "Strait escalates" }).click();
  await expect(page.locator(".scenario-label")).toHaveText("Strait escalates");
  await page.getByRole("button", { name: "Strait reopens" }).click();
  await expect(page.locator(".scenario-label")).toHaveText("Strait reopens");

  for (const viewport of [
    { width: 1280, height: 800 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    const overflows = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    );
    expect(overflows).toBe(false);
  }
});
