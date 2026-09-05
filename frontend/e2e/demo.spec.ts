import { expect, test } from "@playwright/test";
import { projectionFixture } from "../src/test/fixture";

test("disconnected dashboard shows the API error without fabricated data", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("Not found");
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Margarethe Voss-Brenner/ }),
  ).toHaveCount(0);
});

test("fixture-driven UI remains navigable with the live review API", async ({
  page,
}) => {
  // The data-team cutover removed the projection API. Exercise the retained
  // screens with the explicit UI fixture; review persistence is not mocked.
  await page.route("**/api/monday-brief", (route) =>
    route.fulfill({ json: projectionFixture }),
  );
  await page.goto("/");
  await page.getByRole("button", { name: /Margarethe Voss-Brenner/ }).click();
  await page.getByRole("button", { name: "Why?" }).first().click();
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

  await page.goto("/clients/CL-0019/scenario");
  await expect(page.getByText("Abdullah Al-Mansoori")).toBeVisible();
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
