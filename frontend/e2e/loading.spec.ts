import { expect, test } from "@playwright/test";

for (const width of [1280, 390]) {
  test(`dashboard retries preserve keyboard focus at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    const errorDetail = `Temporary outage: ${"UpstreamUnavailable_".repeat(18)}`;
    let fail = true;
    let responseGate = Promise.resolve();
    await page.route("**/preview/dashboard", async (route) => {
      await responseGate;
      if (fail) {
        await route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ detail: errorDetail }),
        });
      } else {
        await route.continue();
      }
    });

    for (const path of ["/", "/clients/CL-0003/pre-read"]) {
      fail = true;
      await page.goto(path);
      const retry = page.getByRole("button", { name: "Try again" });
      const alert = page.getByRole("alert");
      const expectContainedError = async () => {
        await expect(alert).toContainText(errorDetail);
        await expect
          .poll(() =>
            alert.evaluate((element) => ({
              fits: element.scrollWidth <= element.clientWidth,
              pageFits: document.documentElement.scrollWidth <= innerWidth,
            })),
          )
          .toEqual({ fits: true, pageFits: true });
        await expect(retry).toBeInViewport();
      };
      await expectContainedError();
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
          await expectContainedError();
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
