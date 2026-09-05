import { expect, test } from "@playwright/test";

// Uses the actual API and ledger behind tests/browser_app.py. The generation and
// verification providers are explicit test doubles, never production wiring.
test("approved seed Brief stays historical after a Controlled Update and reset restores it", async ({
  page,
  request,
}) => {
  const api = "http://127.0.0.1:8016";
  const clientId = "CL-0003";
  // Ensure the updated run needs review even if another test already visited it.
  const updated = await (
    await request.post(`${api}/api/demo/update`, { data: { action: "apply" } })
  ).json();
  const rejected = await request.post(`${api}/api/reviews`, {
    data: {
      action: "Reject",
      run_id: updated.run_id,
      client_id: clientId,
      brief_version: updated.clients[clientId].brief_version,
      text: "Reset test review state",
    },
  });
  expect(rejected.ok()).toBeTruthy();
  const seeded = await (
    await request.post(`${api}/api/demo/update`, { data: { action: "reset" } })
  ).json();
  expect(seeded.run_id).not.toBe(updated.run_id);

  await page.goto(`/clients/${clientId}/pre-read`);
  await page
    .getByRole("button", { name: "Approve Meeting Brief", exact: true })
    .click();
  await expect(
    page.getByText("Reviewed meeting pack", { exact: true }),
  ).toBeVisible();
  const panel = page.getByRole("region", {
    name: "What changed in the Meeting Brief?",
  });
  await expect(
    panel.getByRole("article", { name: "Current Meeting Brief", exact: true }),
  ).toContainText(seeded.run_id);
  await panel.getByRole("button", { name: "Apply Controlled Update" }).click();
  const earlier = panel.getByRole("article", {
    name: "Earlier Meeting Brief",
    exact: true,
  });
  const current = panel.getByRole("article", {
    name: "Current Meeting Brief",
    exact: true,
  });
  await expect(earlier).toContainText(seeded.run_id);
  await expect(current).toContainText(updated.run_id);
  await expect(current).toContainText(
    "Could we review the earlier payment date together?",
  );
  await expect(current.locator(".is-changed")).not.toHaveCount(0);
  await expect(panel).toContainText("Current Meeting Brief: Needs review");
  await earlier
    .getByText("Review Decisions for this version", { exact: true })
    .click();
  await expect(earlier).toContainText("Approve");
  await expect(current).not.toContainText("Approve");
  await page.reload();
  await expect(
    page.getByRole("region", { name: "What changed in the Meeting Brief?" }),
  ).toContainText("Current Meeting Brief: Needs review");
  await page.getByRole("button", { name: "Reset to seed run" }).click();
  await expect(
    page.getByText("Reviewed meeting pack", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("article", { name: "Current Meeting Brief", exact: true }),
  ).toContainText(seeded.run_id);
  await expect(current).not.toContainText(updated.run_id);
});
