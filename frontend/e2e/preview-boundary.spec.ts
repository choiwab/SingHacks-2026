import { expect, test } from "@playwright/test";

test("preview is disclosed and review actions never reach the live ledger", async ({
  page,
}) => {
  const liveReviews: string[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/reviews")) liveReviews.push(request.url());
  });
  await page.goto("/clients/CL-0003/pre-read");
  await expect(
    page.getByRole("note", { name: "Fixture preview" }),
  ).toContainText("Reviews are simulated and unsaved.");
  await page
    .getByRole("button", { name: "Approve pre-read", exact: true })
    .click();
  await expect(page.getByText(/Preview review · Approved/)).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Approve pre-read", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Preview review · Approved/)).toHaveCount(0);
  expect(liveReviews).toEqual([]);
});

test("normal runtime renders the live backend without touching the fixture", async ({
  page,
}) => {
  const previewRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/preview/"))
      previewRequests.push(request.url());
  });
  await page.goto("http://127.0.0.1:4174/");
  await expect(
    page.getByRole("heading", { name: "Who needs you this week" }),
  ).toBeVisible();
  await expect(page.getByRole("note", { name: "Fixture preview" })).toHaveCount(
    0,
  );
  // The pipeline controls only exist against the live backend.
  await expect(
    page.getByRole("button", { name: "Run pipeline", exact: true }),
  ).toBeVisible();
  expect(previewRequests).toEqual([]);
  const oldApi = await page.request.get(
    "http://127.0.0.1:4174/api/monday-brief",
  );
  expect(oldApi.status()).toBe(404);
  const fixture = await page.request.get(
    "http://127.0.0.1:4174/preview/dashboard",
  );
  expect(fixture.headers()["content-type"]).not.toContain("application/json");
});

test("preview review endpoint rejects malformed and invalid decisions", async ({
  request,
}) => {
  for (const data of [
    { client_id: "CL-9999", action: "Approve", text: "Draft" },
    { client_id: "CL-0003", action: "Unknown", text: "Draft" },
    { client_id: "CL-0003", action: "Edit", text: "  " },
    { client_id: "CL-0003", action: "Edit", text: "x".repeat(1201) },
  ]) {
    const response = await request.post("/preview/reviews", { data });
    expect(response.status()).toBe(422);
  }
  const malformed = await request.post("/preview/reviews", {
    data: Buffer.from("{"),
    headers: { "Content-Type": "application/json" },
  });
  expect(malformed.status()).toBe(400);
});
