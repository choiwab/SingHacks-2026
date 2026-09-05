import { expect, test } from "@playwright/test";

/** These tests call the real API. Only generation/verification is injected. */
test("meeting preparation persists reviews and recovers from stale and failed edits", async ({
  page,
  context,
}) => {
  const reset = await page.request.post("/api/demo/update", {
    data: { action: "reset" },
  });
  expect(reset.ok()).toBeTruthy();
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Margarethe Voss-Brenner", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Booked meetings" }),
  ).toContainText("Cached");
  await expect(
    page.getByRole("heading", { name: "Since we last spoke" }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "Meeting Brief", exact: true })
      .getByText("Could we review your planned payment together?", {
        exact: true,
      }),
  ).toBeVisible();

  const interaction = page.locator("article").filter({
    has: page.getByRole("heading", { name: "Last dated interaction" }),
  });
  await interaction.getByRole("button", { name: /Evidence/ }).click();
  await expect(page.getByRole("dialog")).toContainText("Cached");
  await page.getByRole("button", { name: "Close", exact: true }).click();

  await page
    .getByRole("button", { name: "Approve Meeting Brief", exact: true })
    .click();
  await expect(
    page.getByText("Reviewed meeting pack", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Reviewed meeting pack", { exact: true }),
  ).toBeVisible();
  const approved = await (await page.request.get("/api/app")).json();
  const oldVersion = approved.clients["CL-0003"].brief_version;

  const staleTab = await context.newPage();
  await staleTab.goto("/");
  await expect(
    staleTab.getByText("Reviewed meeting pack", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Edit wording", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Approve Meeting Brief", exact: true }),
  ).toBeDisabled();
  await page
    .getByLabel("Relationship Manager wording")
    .fill("Could we confirm the available funding together?");
  await page
    .getByRole("button", { name: "Save edited version", exact: true })
    .click();
  await expect(
    page
      .getByRole("region", { name: "Meeting Brief", exact: true })
      .getByText("Could we confirm the available funding together?", {
        exact: true,
      }),
  ).toBeVisible();
  await expect(
    page.getByText("Reviewed meeting pack", { exact: true }),
  ).toHaveCount(0);
  const edited = await (await page.request.get("/api/app")).json();
  expect(edited.run_id).toBe(approved.run_id);
  expect(edited.clients["CL-0003"].brief_version).toBeGreaterThan(oldVersion);
  expect(edited.clients["CL-0003"].brief_status).toBe("Needs review");

  await staleTab
    .getByRole("button", { name: "Approve Meeting Brief", exact: true })
    .click();
  await expect(
    staleTab.getByText(/Reload the current version before trying again/),
  ).toBeVisible();
  await staleTab
    .getByRole("button", { name: "Reload current version", exact: true })
    .click();
  await expect(
    staleTab
      .getByRole("region", { name: "Meeting Brief", exact: true })
      .getByText("Could we confirm the available funding together?", {
        exact: true,
      }),
  ).toBeVisible();
  await staleTab.close();

  // Fail verification on the updated run, retaining a valid seed for other specs.
  expect(
    (
      await page.request.post("/api/demo/update", { data: { action: "apply" } })
    ).ok(),
  ).toBeTruthy();
  await page.reload();
  await expect(
    page
      .getByRole("region", { name: "Meeting Brief", exact: true })
      .getByText("Could we review the earlier payment date together?", {
        exact: true,
      }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Edit wording", exact: true }).click();
  await page
    .getByLabel("Relationship Manager wording")
    .fill("unsupported browser test claim");
  await page
    .getByRole("button", { name: "Save edited version", exact: true })
    .click();
  await expect(
    page.getByText(/No verified Meeting Brief is available/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve Meeting Brief", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByText("unsupported browser test claim", { exact: true }),
  ).toHaveCount(0);
});
