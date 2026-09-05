import { expect, test } from "@playwright/test";

test("presentation preserves draft/review state, isolates print, and restores preparation", async ({
  page,
}) => {
  await page.goto("/clients/CL-0003");
  await page.getByRole("button", { name: "Present Meeting Brief" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("status")).toHaveText(
    "Draft: needs Relationship Manager review",
  );
  await expect(
    dialog.getByRole("heading", { name: /A conversation with/ }),
  ).toBeVisible();
  await expect(
    dialog.getByText(/Connected Record · notes · Cached/),
  ).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Approve Meeting Brief" }),
  ).toHaveCount(0);
  await page.emulateMedia({ media: "print" });
  await expect(
    dialog.getByRole("button", { name: "Print Meeting Brief" }),
  ).toBeHidden();
  await expect(page.locator(".live-topbar")).toBeHidden();
  await expect(
    dialog.getByRole("heading", { name: "Supporting Evidence" }),
  ).toBeVisible();
  await expect(dialog.getByRole("status")).toHaveText(
    "Draft: needs Relationship Manager review",
  );
  await page.emulateMedia({ media: "screen" });
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Present Meeting Brief" }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Approve Meeting Brief" }).click();
  await expect(
    page.getByText("Reviewed meeting pack", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Present Meeting Brief" }).click();
  await expect(dialog.getByRole("status")).toHaveText("Reviewed Meeting Brief");
  await expect(
    dialog.getByText(/Current Review Decision: Approve/),
  ).toBeVisible();
});
