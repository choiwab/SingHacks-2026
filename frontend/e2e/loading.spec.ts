import { expect, test } from "@playwright/test";

for (const width of [1280, 390]) {
  test(`dashboard retries preserve keyboard focus at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    let fail = true;
    let responseGate = Promise.resolve();
    await page.route("**/api/monday-brief", async (route) => {
      await responseGate;
      if (fail) {
        await route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Temporary outage" }),
        });
      } else {
        await route.continue();
      }
    });

    for (const path of ["/", "/clients/CL-0003/pre-read"]) {
      fail = true;
      await page.goto(path);
      const retry = page.getByRole("button", { name: "Try again" });
      await expect(page.getByRole("alert")).toContainText("Temporary outage");
      // Initial loading still respects the browser's default focus.
      await expect(page.locator("body")).toBeFocused();
      await page.keyboard.press("Tab");
      await expect(retry).toBeFocused();

      for (const outcome of ["failure", "success"]) {
        fail = outcome === "failure";
        let releaseResponse!: () => void;
        responseGate = new Promise<void>((resolve) => {
          releaseResponse = resolve;
        });
        await page.keyboard.press("Enter");
        await expect(page.getByRole("status")).toHaveText(
          "Loading the dashboard…",
        );
        await expect(page.getByRole("main")).toBeFocused();
        releaseResponse();

        if (fail) {
          await expect(page.getByRole("alert")).toContainText(
            "Temporary outage",
          );
          await expect(retry).toBeFocused();
          await expect(retry).toBeInViewport();
        } else {
          await expect(page.locator("#main")).toBeFocused();
          await expect(page.getByRole("heading", { level: 1 })).toHaveText(
            path === "/"
              ? "Who needs you this week"
              : "Margarethe Voss-Brenner",
          );
          await page.keyboard.press("Tab");
          await expect(page.locator("#main :focus")).toHaveCount(1);
        }
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        ).toBe(true);
      }
    }
  });
}
