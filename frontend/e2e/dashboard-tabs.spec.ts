import { expect, test } from "@playwright/test";

for (const width of [320, 390, 1280]) {
  test(`dashboard tabs fit with wider fonts and retain keyboard navigation at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const tabs = page.getByRole("tablist", { name: "Client intelligence" });
    await expect(tabs).toBeVisible();
    // Exercise wider font metrics on every OS, including macOS where the
    // default system font masked the Linux mobile overflow.
    await page.addStyleTag({
      content:
        ".dashboard-tabs .fui-Tab { font-family: monospace; font-size: 16px; }",
    });
    await tabs.getByRole("tab", { name: "Overview", exact: true }).focus();
    for (const name of ["Overview", "Insights", "Data", "Memory"]) {
      const tab = tabs.getByRole("tab", { name, exact: true });
      await expect(tab).toBeFocused();
      await page.keyboard.press("Enter");
      await expect(tab).toHaveAttribute("aria-selected", "true");
      await expect(
        page.getByRole("tabpanel", { name, exact: true }),
      ).toBeVisible();
      await expect(tab).toBeInViewport({ ratio: 1 });
      expect(
        await tabs.evaluate((element) => {
          const bounds = element.getBoundingClientRect();
          return [...element.querySelectorAll('[role="tab"]')].every((item) => {
            const tabBounds = item.getBoundingClientRect();
            return (
              tabBounds.left >= bounds.left && tabBounds.right <= bounds.right
            );
          });
        }),
      ).toBe(true);
      expect(
        await page
          .getByRole("main")
          .evaluate((element) => element.scrollWidth <= element.clientWidth),
      ).toBe(true);
      await page.keyboard.press("ArrowRight");
    }
    await expect(
      tabs.getByRole("tab", { name: "Overview", exact: true }),
    ).toBeFocused();
  });
}
