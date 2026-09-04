import { expect, test } from "@playwright/test";
import type { MondayBriefProjection } from "../src/contracts";

for (const width of [1280, 390]) {
  test(`data status explains its supporting facts at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const why = page.getByRole("button", { name: "Why this data status?" });
    const drawer = page.getByRole("dialog", { name: "Why?", exact: true });
    for (const tab of ["Overview", "Insights", "Data", "Memory"]) {
      await page.getByRole("tab", { name: tab, exact: true }).click();
      await expect(
        page.getByText(
          "No client facts are marked low confidence in this snapshot.",
          { exact: true },
        ),
      ).toBeVisible();
      await why.focus();
      await page.keyboard.press("Enter");
      await expect(drawer).toContainText(
        "Margarethe Voss-Brenner: Data Current.",
      );
      await expect(drawer).toContainText(
        "This status reflects fact confidence, not a live data refresh.",
      );
      await expect(drawer).toContainText(
        "Confidence medium · as of 2026-08-26",
      );
      await expect(drawer).toContainText(
        "data/clients.csv · row clients:CL-0003",
      );
      await expect(drawer).toContainText("data/holdings.csv");
      expect(
        await drawer.evaluate((el) => el.scrollWidth <= el.clientWidth),
      ).toBe(true);
      await page.keyboard.press("Escape");
      await expect(why).toBeFocused();
    }
    await page
      .getByRole("navigation", { name: "Client switcher" })
      .getByRole("button", { name: /Alistair Pemberton-Hale/ })
      .click();
    await why.click();
    await expect(drawer).toContainText(
      "Alistair Pemberton-Hale: Data Current.",
    );
    await expect(drawer).not.toContainText("CL-0003");
    await page.keyboard.press("Escape");
    await expect(why).toBeFocused();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`data status explains low-confidence and missing facts at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    let missing = false;
    await page.route("**/api/monday-brief", async (route) => {
      const response = await route.fetch();
      const projection: MondayBriefProjection = await response.json();
      const facts = projection.facts["CL-0003"];
      const deadline = facts.find((fact) => fact.kind === "deadline")!;
      deadline.confidence = "low";
      if (missing) projection.facts["CL-0003"] = [];
      await route.fulfill({ response, json: projection });
    });
    await page.goto("/clients/CL-0003/pre-read");
    await expect(
      page.getByText("Data Needs confirmation", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText(
        "Some client facts have low confidence and need confirmation.",
        { exact: true },
      ),
    ).toBeVisible();
    const why = page.getByRole("button", { name: "Why this data status?" });
    await why.click();
    const drawer = page.getByRole("dialog", { name: "Why?", exact: true });
    await expect(drawer).toContainText(
      "Margarethe Voss-Brenner: Data Needs confirmation.",
    );
    await expect(drawer).toContainText("Confidence low · as of 2026-08-26");
    await expect(drawer).toContainText("data/planned_cash_needs.csv");
    await expect(drawer).not.toContainText("Confidence high");
    await expect(drawer).not.toContainText("Confidence medium");
    await page.keyboard.press("Escape");
    await expect(why).toBeFocused();
    missing = true;
    await page.reload();
    await expect(
      page.getByText("No client facts are available in this snapshot.", {
        exact: true,
      }),
    ).toBeVisible();
    await expect(why).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`Memory retrieves exact quoted phrases at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const panel = page.getByRole("tabpanel", { name: "Memory" });
    const search = panel.getByRole("searchbox");
    const notes = panel.getByRole("region", { name: "RM notes", exact: true });
    const beliefs = panel.getByRole("region", { name: "Extracted beliefs" });
    await expect(search).toHaveAccessibleDescription(
      "Search by topic, or use double quotes for an exact phrase.",
    );
    for (const query of [
      '"risk with money"',
      "“RISK WITH MONEY”",
      '"risk   with money"',
    ]) {
      await search.fill(query);
      await expect(panel.getByRole("status")).toHaveText(
        '1 of 2 notes and 1 of 1 belief mention "risk with money".',
      );
      await expect(notes.locator("mark")).toHaveText("risk with money");
      await expect(beliefs.locator("mark")).toHaveText("risk with money");
      await expect(search).toHaveValue(query);
      await expect(search).toBeFocused();
    }
    for (const query of [
      '"risk with cash"',
      '"risk with mone"',
      '"gold position"',
      '"risk with money.*"',
      '"4m"',
      '"4m falls"',
      '"EUR 3"',
      '"2026-05"',
      '"006"',
      // Separate source fields must not create a phrase absent from the note.
      '"conservative. Meeting"',
      '"Email 2026-05-29"',
      '"2026-05-29 N-006"',
      '"N-006 Priscilla"',
      '"money. N-005"',
    ]) {
      await search.fill(query);
      await expect(panel.getByRole("status")).toHaveText(
        `0 of 2 notes and 0 of 1 belief mention ${query.toLowerCase()}.`,
      );
      await expect(panel.locator("mark")).toHaveCount(0);
    }
    for (const wording of [
      "3.4m",
      "EUR 3.4m",
      "2026-05-29",
      "N-006",
      "Email",
    ]) {
      await search.fill(`"${wording}"`);
      await expect(panel.getByRole("status")).toHaveText(
        `1 of 2 notes and 0 of 1 belief mention "${wording.toLowerCase()}".`,
      );
      await expect(notes.locator("mark")).toHaveText(wording);
      await expect(search).toBeFocused();
    }
    await search.fill('"Priscilla Ong"');
    await expect(panel.getByRole("status")).toHaveText(
      '2 of 2 notes and 0 of 1 belief mention "priscilla ong".',
    );
    await expect(notes.locator("mark")).toHaveText([
      "Priscilla Ong",
      "Priscilla Ong",
    ]);
    await search.fill('"safe and boring"');
    await expect(notes.locator("mark")).toHaveText("safe and boring");
    await expect(beliefs.locator("mark")).toHaveCount(0);
    const why = notes.getByRole("button", { name: "Why?", exact: true });
    await why.click();
    await expect(
      page.getByRole("dialog", { name: "Why?", exact: true }),
    ).toContainText("N-006");
    await page.keyboard.press("Escape");
    await expect(why).toBeFocused();
    // Unquoted topics retain the existing OR behavior alongside phrases.
    await search.fill('"safe and boring" risk');
    await expect(panel.getByRole("status")).toHaveText(
      '2 of 2 notes and 1 of 1 belief mention "safe and boring" or risk.',
    );
    // Unfinished quotes remain usable while the RM is typing.
    await search.fill('"risk');
    await expect(panel.getByRole("status")).toHaveText(
      "1 of 2 notes and 1 of 1 belief mention risk.",
    );
    await panel.getByRole("button", { name: "Clear note search" }).click();
    await expect(search).toBeFocused();
    await expect(
      notes.getByRole("button", { name: "Why?", exact: true }),
    ).toHaveCount(2);
    expect(
      await panel.evaluate(
        (element) => element.scrollWidth <= element.clientWidth,
      ),
    ).toBe(true);
  });

  test(`Memory retrieves notes by their RM author at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const panel = page.getByRole("tabpanel", { name: "Memory" });
    const search = panel.getByRole("searchbox");
    const notes = panel.getByRole("region", { name: "RM notes", exact: true });
    for (const query of ["Priscilla", "PRISCILLA", "Ong"]) {
      await search.fill(query);
      await expect(panel.getByRole("status")).toHaveText(
        `2 of 2 notes and 0 of 1 belief mention ${query.toLowerCase()}.`,
      );
      await expect(notes.locator("mark")).toHaveText(
        query === "Ong" ? ["Ong", "Ong"] : ["Priscilla", "Priscilla"],
      );
      await expect(search).toHaveValue(query);
      await expect(search).toBeFocused();
      await expect(notes).toContainText("N-005");
      await expect(notes).toContainText("N-006");
    }
    const why = notes
      .getByRole("button", { name: "Why?", exact: true })
      .first();
    await why.click();
    const drawer = page.getByRole("dialog", { name: "Why?", exact: true });
    await expect(drawer).toContainText("Priscilla Ong");
    await expect(drawer).toContainText("N-005");
    await page.keyboard.press("Escape");
    await expect(why).toBeFocused();
    await search.fill("Alex");
    await expect(panel.getByRole("status")).toHaveText(
      "0 of 2 notes and 0 of 1 belief mention alex.",
    );
    await expect(panel.locator("mark")).toHaveCount(0);
    await panel.getByRole("button", { name: "Clear note search" }).click();
    await expect(search).toBeFocused();
    await expect(
      notes.getByRole("button", { name: "Why?", exact: true }),
    ).toHaveCount(2);
    await expect(panel.locator("mark")).toHaveCount(0);
    expect(
      await panel.evaluate(
        (element) => element.scrollWidth <= element.clientWidth,
      ),
    ).toBe(true);
  });

  test(`Memory retrieves complete note references at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const panel = page.getByRole("tabpanel", { name: "Memory" });
    const search = panel.getByRole("searchbox");
    const notes = panel.getByRole("region", { name: "RM notes", exact: true });
    const beliefs = panel.getByRole("region", { name: "Extracted beliefs" });
    for (const query of ["N-005", "n-005"]) {
      await search.fill(query);
      await expect(panel.getByRole("status")).toHaveText(
        "1 of 2 notes and 1 of 1 belief mention n-005.",
      );
      await expect(notes).toContainText("2026-02-16");
      await expect(notes).not.toContainText("2026-05-29");
      await expect(notes.locator("mark")).toHaveText("N-005");
      await expect(beliefs.locator("mark")).toHaveText("N-005");
      await expect(search).toHaveValue(query);
      await expect(search).toBeFocused();
    }
    for (const region of [notes, beliefs]) {
      const why = region.getByRole("button", { name: "Why?", exact: true });
      await why.click();
      const drawer = page.getByRole("dialog", { name: "Why?", exact: true });
      await expect(drawer).toContainText("N-005");
      await expect(drawer).toContainText(
        "First meeting following the transfer in.",
      );
      await page.keyboard.press("Escape");
      await expect(why).toBeFocused();
    }
    // Reject partial references and notes belonging to another client.
    for (const query of ["N-00", "N-0050", "N-024"]) {
      await search.fill(query);
      await expect(panel.getByRole("status")).toHaveText(
        `0 of 2 notes and 0 of 1 belief mention ${query.toLowerCase()}.`,
      );
      await expect(panel.locator("mark")).toHaveCount(0);
    }
    await search.fill("N-006");
    await expect(panel.getByRole("status")).toHaveText(
      "1 of 2 notes and 0 of 1 belief mention n-006.",
    );
    await expect(notes.locator("mark")).toHaveText("N-006");
    await expect(notes).toContainText("2026-05-29");
    await panel.getByRole("button", { name: "Clear note search" }).click();
    await expect(search).toBeFocused();
    await expect(search).toHaveValue("");
    await expect(
      notes.getByRole("button", { name: "Why?", exact: true }),
    ).toHaveCount(2);
    await expect(panel.locator("mark")).toHaveCount(0);
    expect(
      await panel.evaluate(
        (element) => element.scrollWidth <= element.clientWidth,
      ),
    ).toBe(true);
  });

  test(`saved opening references wrap in the evidence drawer at ${width}px`, async ({
    page,
  }) => {
    await page.route("**/api/reviews", async (route) => {
      await route.fulfill({
        json: {
          review: {
            ...route.request().postDataJSON(),
            timestamp: "2026-09-05T10:00:00Z",
            rm: "Priscilla Ong",
          },
        },
      });
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    await page.getByRole("button", { name: "Edit", exact: true }).click();
    const wording = `Please review reference ${"REFERENCE".repeat(30)}.`;
    await page.getByLabel("Edit the opening line").fill(wording);
    await page.getByRole("button", { name: "Save edit" }).click();
    const opening = page.getByRole("region", { name: "Suggested opening" });
    await expect(opening).toContainText(wording);
    const why = opening.getByRole("button", { name: "Why?", exact: true });
    await why.click();
    const drawer = page.getByRole("dialog", { name: "Why?", exact: true });
    await expect(drawer.getByText(wording, { exact: true })).toBeVisible();
    await expect(
      drawer.getByText("Edited by the RM", { exact: true }),
    ).toBeVisible();
    const body = drawer.locator(".fui-DrawerBody");
    expect(
      await body.evaluate(
        (element) => element.scrollWidth <= element.clientWidth,
      ),
    ).toBe(true);
    await page.keyboard.press("Escape");
    await expect(drawer).not.toBeVisible();
    await expect(why).toBeFocused();
    expect(
      await page
        .getByRole("main")
        .evaluate((element) => element.scrollWidth <= element.clientWidth),
    ).toBe(true);
    await expect(opening).toContainText(wording);
  });

  test(`Memory wraps long search feedback at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const panel = page.getByRole("tabpanel", { name: "Memory", exact: true });
    const search = panel.getByRole("searchbox");
    const query = "unmatched".repeat(30);
    await search.fill(query);
    await expect(panel.getByRole("status")).toHaveText(
      `0 of 2 notes and 0 of 1 belief mention ${query}.`,
    );
    await expect(
      panel.getByRole("region", { name: "Extracted beliefs" }),
    ).toContainText(`No recorded belief mentions ${query}.`);
    await expect(panel.getByRole("region", { name: "RM notes" })).toContainText(
      `No note mentions ${query}. Try another word.`,
    );
    await expect(search).toBeFocused();
    for (const region of [
      "Search the client memory",
      "Extracted beliefs",
      "RM notes",
    ]) {
      expect(
        await panel
          .getByRole("region", { name: region })
          .evaluate((element) => element.scrollWidth <= element.clientWidth),
      ).toBe(true);
    }
    expect(
      await page
        .getByRole("main")
        .evaluate((element) => element.scrollWidth <= element.clientWidth),
    ).toBe(true);
    await panel.getByRole("button", { name: "Clear note search" }).click();
    await expect(search).toHaveValue("");
    await expect(search).toBeFocused();
    await expect(panel.getByRole("status")).toHaveText(
      "Searching 2 notes and 1 extracted belief for this client.",
    );
    await expect(panel.getByRole("region", { name: "RM notes" })).toContainText(
      "2026-05-29",
    );
  });

  test(`memory questions ignore pronouns when retrieving topics at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0001/pre-read");
    await page.getByRole("tab", { name: "Memory" }).click();
    const search = page.getByRole("searchbox", {
      name: "Search this client's RM notes",
    });
    const status = page
      .getByRole("region", { name: "Search the client memory" })
      .getByRole("status");
    const notes = page.getByRole("region", { name: "RM notes" });
    const beliefs = page.getByRole("region", { name: "Extracted beliefs" });

    for (const pronoun of ["he", "she", "they"]) {
      await search.fill(`What did ${pronoun} say about coal?`);
      await expect(status).toHaveText(
        "1 of 2 notes and 0 of 1 belief mention coal.",
      );
      await expect(notes).toContainText("2026-04-14");
      await expect(notes).not.toContainText("2026-01-08");
      await expect(notes.locator("mark")).toHaveText(["coal"]);
      await expect(beliefs).toContainText("No recorded belief mentions coal.");
      await expect(search).toBeFocused();
    }

    await search.fill("What did he say?");
    await expect(status).toContainText(
      "Add a topic such as risk, tax, or cash",
    );
    await expect(status).toContainText("Showing all 2 notes");
    await expect(notes).toContainText("2026-01-08");
    await expect(notes).toContainText("2026-04-14");
    await expect(notes.locator("mark")).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`calendar reveals the selected meeting without moving page focus at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0019/pre-read");
    const calendar = page.getByRole("navigation", {
      name: "This week's meetings",
    });
    const selected = calendar.locator('button[aria-current="true"]');
    const main = page.getByRole("main");
    const assertMeetingVisible = async (name: string) => {
      await expect(selected).toContainText(name);
      await expect(selected).toBeInViewport({ ratio: 1 });
      await expect
        .poll(() => main.evaluate((element) => element.scrollTop))
        .toBe(0);
    };
    await assertMeetingVisible("Abdullah Al-Mansoori");
    await expect(page.locator("body")).toBeFocused();

    for (const name of [
      "Lau Chi Ming",
      "Margarethe Voss-Brenner",
      "Abdullah Al-Mansoori",
    ]) {
      await page
        .getByRole("navigation", { name: "Client switcher" })
        .getByRole("button", { name: new RegExp(name) })
        .click();
      await assertMeetingVisible(name);
      await expect(main).toBeFocused();
    }
    await page.goBack();
    await assertMeetingVisible("Margarethe Voss-Brenner");
    await expect(main).toBeFocused();
    await page.goForward();
    await assertMeetingVisible("Abdullah Al-Mansoori");
    await expect(main).toBeFocused();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`source trail identifies its client without a generated claim at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    for (const client of [
      { name: "Margarethe Voss-Brenner", id: "CL-0003", query: "boring" },
      { name: "Abdullah Al-Mansoori", id: "CL-0019", query: "Gulf" },
    ]) {
      await page
        .getByRole("navigation", { name: "Client switcher" })
        .getByRole("button", { name: new RegExp(client.name) })
        .click();
      await page.getByRole("tab", { name: "Memory", exact: true }).click();
      const search = page.getByRole("searchbox", {
        name: "Search this client's RM notes",
      });
      await search.fill(client.query);
      const why = page
        .getByRole("region", { name: "RM notes", exact: true })
        .getByRole("button", { name: "Why?", exact: true })
        .first();
      await why.focus();
      await why.press("Enter");
      const drawer = page.getByRole("dialog", { name: "Why?", exact: true });
      const identity = `${client.name} · ${client.id}`;
      await expect(drawer).toHaveAccessibleDescription(identity);
      await expect(
        drawer.getByText(identity, { exact: true }),
      ).toBeInViewport();
      await expect(drawer).toContainText("data/rm_notes.json");
      await expect(
        drawer.getByRole("region", { name: "Generated claim" }),
      ).toHaveCount(0);
      expect(
        await drawer.evaluate(
          (element) => element.scrollWidth <= element.clientWidth,
        ),
      ).toBe(true);
      await page.keyboard.press("Escape");
      await expect(drawer).toHaveCount(0);
      await expect(why).toBeFocused();
      await expect(search).toHaveValue(client.query);
    }
  });

  test(`Memory explains searches without topic words at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const searchRegion = page.getByRole("region", {
      name: "Search the client memory",
    });
    const search = searchRegion.getByRole("searchbox");
    const status = searchRegion.getByRole("status");
    const notes = page.getByRole("region", { name: "RM notes", exact: true });
    const guidance = "Add a topic such as risk, tax, or cash to search.";
    for (const query of ["What did she say?", "?!", "a"]) {
      await search.fill(query);
      await expect(search).toBeFocused();
      await expect(status).toContainText(guidance);
      await expect(status).toContainText(
        "Showing all 2 notes and 1 extracted belief",
      );
      await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(2);
      await expect(notes.locator("mark")).toHaveCount(0);
      expect(
        await searchRegion.evaluate(
          (element) => element.scrollWidth <= element.clientWidth,
        ),
      ).toBe(true);
    }
    await search.fill("What did she say about risk?");
    await expect(status).not.toContainText(guidance);
    await expect(status).toContainText("1 of 2 notes");
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(1);
    await expect(notes.locator("mark")).toHaveCount(2);
    await search.fill("What did she say?");
    await expect(status).toContainText(guidance);
    await searchRegion
      .getByRole("button", { name: "Clear note search", exact: true })
      .click();
    await expect(search).toBeFocused();
    await expect(status).not.toContainText(guidance);
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(2);
    await search.fill("   ");
    await expect(status).not.toContainText(guidance);
  });

  test(`Memory highlights matching note channels at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const searchRegion = page.getByRole("region", {
      name: "Search the client memory",
    });
    const search = searchRegion.getByRole("searchbox");
    const notes = page.getByRole("region", { name: "RM notes", exact: true });
    for (const channel of ["Email", "Meeting"]) {
      const matches =
        channel === "Meeting" ? ["Meeting", "meeting"] : ["Email"];
      await search.fill(channel.toLowerCase());
      await expect(search).toBeFocused();
      await expect(searchRegion.getByRole("status")).toContainText(
        "1 of 2 notes",
      );
      await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(1);
      await expect(notes.locator("mark")).toHaveText(matches);
      await notes.getByRole("button", { name: "Why?" }).click();
      const drawer = page.getByRole("dialog", { name: "Why?", exact: true });
      await expect(drawer).toContainText("data/rm_notes.json");
      await expect(drawer).toContainText(channel);
      await page.keyboard.press("Escape");
      await expect(drawer).toHaveCount(0);
      await expect(notes.getByRole("button", { name: "Why?" })).toBeFocused();
      await expect(notes.locator("mark")).toHaveText(matches);
    }
    await search.fill("email risk");
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(2);
    await expect(notes.locator("mark")).toHaveText(["risk", "Risk", "Email"]);
    await searchRegion
      .getByRole("button", { name: "Clear note search", exact: true })
      .click();
    await expect(search).toBeFocused();
    await expect(notes.locator("mark")).toHaveCount(0);
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(2);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`dismissing an earlier review failure returns to an unfinished edit at ${width}px`, async ({
    page,
  }) => {
    const submitted: { action: string; text: string }[] = [];
    await page.route("**/api/reviews", async (route) => {
      submitted.push(route.request().postDataJSON());
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Review ledger unavailable" }),
      });
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const opening = page.getByRole("region", { name: "Suggested opening" });
    const original = await opening.innerText();
    for (const label of ["Approve pre-read", "Reject"]) {
      const decision = page.getByRole("button", { name: label, exact: true });
      await decision.click();
      const alert = page.getByRole("alert");
      await expect(alert).toContainText("Review ledger unavailable");
      await page.getByRole("button", { name: "Edit", exact: true }).click();
      const editor = page.getByLabel("Edit the opening line");
      await editor.fill("Keep my unfinished opening");
      await expect(decision).toBeDisabled();
      const requestCount = submitted.length;
      const dismiss = alert.getByRole("button", {
        name: "Dismiss the review error",
      });
      await dismiss.focus();
      await dismiss.press("Enter");
      await expect(alert).toHaveCount(0);
      await expect(editor).toBeFocused();
      await expect(editor).toBeInViewport();
      await expect(editor).toHaveValue("Keep my unfinished opening");
      await editor.press("End");
      await page.keyboard.type(" updated");
      await expect(editor).toHaveValue("Keep my unfinished opening updated");
      expect(submitted).toHaveLength(requestCount);
      expect(await opening.innerText()).toBe(original);
      await page.getByRole("button", { name: "Cancel edit" }).click();
      await expect(decision).toBeEnabled();
    }
    expect(submitted.map((request) => request.action)).toEqual([
      "Approve",
      "Reject",
    ]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`scenario changes announce their result without moving focus at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0019/scenario");
    const announcement = page.getByRole("main").getByRole("status");
    await expect(announcement).toContainText("Abdullah Al-Mansoori");
    await expect(announcement).toHaveAttribute("aria-atomic", "true");
    // Keep the same live region mounted so assistive technology observes updates.
    const originalRegion = await announcement.elementHandle();
    for (const scenario of ["Strait escalates", "Strait reopens"]) {
      const toggle = page.getByRole("button", { name: scenario, exact: true });
      await toggle.focus();
      await toggle.press("Enter");
      await expect(toggle).toBeFocused();
      await expect(toggle).toHaveAttribute("aria-pressed", "true");
      const selector = page.getByRole("group", {
        name: "Scenario",
        exact: true,
      });
      await expect(selector.getByRole("button", { pressed: true })).toHaveCount(
        1,
      );
      // Re-selecting the active scenario must never leave the range unselected.
      await toggle.press("Space");
      await expect(toggle).toBeFocused();
      await expect(toggle).toHaveAttribute("aria-pressed", "true");
      await expect(
        selector.getByRole("button", { pressed: false }),
      ).toHaveCount(1);
      const valueRange = await page.locator(".range-value").innerText();
      const percentRange = await page.locator(".range-percent").innerText();
      const baseline = await page.locator(".scenario-baseline").innerText();
      const chartDescription = `${scenario}: ${percentRange}. ${baseline} Estimated range · not a forecast. Scale: −20% to +20%.`;
      const chart = page.getByRole("img", {
        name: chartDescription,
        exact: true,
      });
      await expect(chart).toBeVisible();
      await expect(chart).toMatchAriaSnapshot(
        `- ${JSON.stringify(`img "${chartDescription}"`)}`,
      );
      await expect(announcement).toHaveText(
        `Abdullah Al-Mansoori · ${scenario}: ${valueRange} (${percentRange}). ${baseline} Estimated range · not a forecast.`,
      );
      expect(
        await announcement.evaluate(
          (element, original) => element === original,
          originalRegion,
        ),
      ).toBe(true);
      await expect(announcement).toMatchAriaSnapshot(`
        - status: /Abdullah Al-Mansoori/
      `);
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`scenario sector evidence retains client, scenario, and caveat at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0019/scenario");
    for (const client of ["Abdullah Al-Mansoori", "Margarethe Voss-Brenner"]) {
      if (client === "Margarethe Voss-Brenner") {
        await page
          .getByRole("navigation", { name: "Client switcher" })
          .getByRole("button", { name: new RegExp(client) })
          .click();
        await page.getByRole("tab", { name: "Scenario rehearsal" }).click();
      }
      for (const scenario of ["Strait reopens", "Strait escalates"]) {
        await page.getByRole("button", { name: scenario, exact: true }).click();
        const baseline = await page.locator(".scenario-baseline").innerText();
        const cards = page
          .getByRole("region", { name: "What changes", exact: true })
          .getByRole("listitem");
        expect(await cards.count()).toBeGreaterThan(0);
        for (const card of await cards.all()) {
          const sector = await card.locator("span").first().innerText();
          const why = card.getByRole("button", { name: "Why?", exact: true });
          await why.focus();
          await why.press("Enter");
          const drawer = page.getByRole("dialog", {
            name: "Why?",
            exact: true,
          });
          await expect(
            drawer.getByRole("region", { name: "Generated claim" }),
          ).toHaveText(
            `Claim on the dashboard${client} · ${scenario}. ${baseline} Estimated range · not a forecast. ${sector}`,
          );
          await expect(drawer).toContainText("data/holdings.csv");
          await expect(drawer).toContainText("data/event_log.csv");
          expect(
            await drawer.evaluate(
              (element) => element.scrollWidth <= element.clientWidth,
            ),
          ).toBe(true);
          await page.keyboard.press("Escape");
          await expect(drawer).not.toBeVisible();
          await expect(why).toBeFocused();
        }
        await expect(
          page.getByRole("button", { name: scenario, exact: true }),
        ).toHaveAttribute("aria-pressed", "true");
      }
    }
  });

  test(`data evidence retains the selected client and fact at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    for (const client of ["Margarethe Voss-Brenner", "Abdullah Al-Mansoori"]) {
      await page
        .getByRole("navigation", { name: "Client switcher" })
        .getByRole("button", { name: new RegExp(client) })
        .click();
      await page.getByRole("tab", { name: "Data", exact: true }).click();
      const data = page.getByRole("tabpanel", { name: "Data", exact: true });
      const card = data
        .getByRole("region", { name: "Concentration", exact: true })
        .getByRole("article");
      const headline = await card.locator("span").first().innerText();
      expect(headline).toMatch(/^Connected positions represent/);
      const why = card.getByRole("button", { name: "Why?", exact: true });
      await why.focus();
      await why.press("Enter");
      const drawer = page.getByRole("dialog", { name: "Why?", exact: true });
      await expect(
        drawer.getByRole("region", { name: "Generated claim" }),
      ).toHaveText(`Claim on the dashboard${client} · ${headline}`);
      await expect(drawer).toContainText("Deterministic fact");
      await expect(drawer).toContainText("Calculation inputs and result");
      await expect(drawer).toContainText("data/holdings.csv · row holdings:");
      await expect(drawer).toContainText("as of 2026-08-26");
      if (client === "Abdullah Al-Mansoori") {
        await expect(drawer).not.toContainText("Margarethe");
      }
      expect(
        await drawer.evaluate(
          (element) => element.scrollWidth <= element.clientWidth,
        ),
      ).toBe(true);
      await page.keyboard.press("Escape");
      await expect(drawer).not.toBeVisible();
      await expect(why).toBeFocused();
      await expect(data).toBeVisible();
    }
  });

  test(`insight evidence retains questions, uncertainty, and review at ${width}px`, async ({
    page,
  }) => {
    await page.route("**/api/reviews", async (route) => {
      await route.fulfill({
        json: {
          review: {
            ...route.request().postDataJSON(),
            timestamp: "2026-09-05T10:00:00Z",
            rm: "Priscilla Ong",
          },
        },
      });
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    await page.getByRole("tab", { name: "Insights", exact: true }).click();
    const drawer = page.getByRole("dialog", { name: "Why?", exact: true });
    for (const region of ["Top insights", "Also active"]) {
      const card = page
        .getByRole("region", { name: region })
        .getByRole("article")
        .first();
      const headline = await card.getByRole("heading").innerText();
      const paragraphs = await card.locator("p").allTextContents();
      expect(paragraphs).toHaveLength(2);
      const caveat =
        region === "Also active"
          ? await card.getByText(/^To confirm:/).innerText()
          : undefined;
      const why = card.getByRole("button", { name: "Why?", exact: true });
      await why.focus();
      await why.press("Enter");
      const claim = drawer.getByRole("region", { name: "Generated claim" });
      await expect(claim).toContainText("Margarethe Voss-Brenner");
      await expect(claim).toContainText(headline);
      await expect(claim).toContainText(paragraphs[0]);
      await expect(claim).toContainText(`Ask: ${paragraphs[1]}`);
      if (caveat) {
        await expect(claim).toContainText(caveat);
        await expect(drawer).toContainText("data/event_log.csv");
        await expect(claim).toContainText("Changed");
      } else {
        await expect(claim).not.toContainText("To confirm:");
        await expect(claim).toContainText("Unchanged");
      }
      await expect(drawer).toContainText("Generated · awaiting RM review");
      await expect(drawer).toContainText("Calculation inputs and result");
      await expect(drawer).toContainText("data/holdings.csv · row holdings:");
      await expect(drawer).toContainText("as of 2026-08-26");
      expect(
        await drawer.evaluate(
          (element) => element.scrollWidth <= element.clientWidth,
        ),
      ).toBe(true);
      await page.keyboard.press("Escape");
      await expect(drawer).not.toBeVisible();
      await expect(why).toBeFocused();
    }
    await page.getByRole("button", { name: "Approve pre-read" }).click();
    await expect(page.getByRole("status").last()).toContainText("Approved");
    for (const region of ["Top insights", "Also active"]) {
      await page
        .getByRole("region", { name: region })
        .getByRole("article")
        .first()
        .getByRole("button", { name: "Why?", exact: true })
        .click();
      await expect(drawer).toContainText("Approved by the RM");
      await page.keyboard.press("Escape");
      await expect(drawer).not.toBeVisible();
    }
    await page
      .getByRole("navigation", { name: "Client switcher" })
      .getByRole("button", { name: /Abdullah Al-Mansoori/ })
      .click();
    await page
      .getByRole("region", { name: "Top insights" })
      .getByRole("article")
      .first()
      .getByRole("button", { name: "Why?", exact: true })
      .click();
    await expect(
      drawer.getByRole("region", { name: "Generated claim" }),
    ).toContainText("Abdullah Al-Mansoori");
    await expect(drawer).toContainText("Generated · awaiting RM review");
    await expect(drawer).not.toContainText("Margarethe");
  });

  test(`discussion evidence retains the agenda and review at ${width}px`, async ({
    page,
  }) => {
    await page.route("**/api/reviews", async (route) => {
      await route.fulfill({
        json: {
          review: {
            ...route.request().postDataJSON(),
            timestamp: "2026-09-05T10:00:00Z",
            rm: "Priscilla Ong",
          },
        },
      });
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const topics = page
      .getByRole("region", { name: "Three discussion topics" })
      .getByRole("listitem");
    await expect(topics).toHaveCount(3);
    const drawer = page.getByRole("dialog", { name: "Why?", exact: true });
    for (let index = 0; index < 3; index += 1) {
      const topic = topics.nth(index);
      const headline = await topic.getByRole("heading").innerText();
      const paragraphs = await topic.locator("p").allTextContents();
      expect(paragraphs).toHaveLength(2);
      const why = topic.getByRole("button", { name: "Why?", exact: true });
      await why.focus();
      await why.press("Enter");
      const claim = drawer.getByRole("region", { name: "Generated claim" });
      await expect(claim).toContainText(
        `Margarethe Voss-Brenner · Topic ${index + 1} · ${headline}`,
      );
      await expect(claim).toContainText(paragraphs[0]);
      await expect(claim).toContainText(`Ask: ${paragraphs[1]}`);
      await expect(drawer).toContainText("Generated · awaiting RM review");
      await expect(drawer).toContainText("Calculation inputs and result");
      await expect(drawer).toContainText(
        index === 1
          ? "data/planned_cash_needs.csv · row planned_cash_needs:CN-004"
          : "data/holdings.csv · row holdings:",
      );
      await expect(drawer).toContainText("as of 2026-08-26");
      expect(
        await drawer.evaluate(
          (element) => element.scrollWidth <= element.clientWidth,
        ),
      ).toBe(true);
      await page.keyboard.press("Escape");
      await expect(drawer).not.toBeVisible();
      await expect(why).toBeFocused();
    }
    await page.getByRole("button", { name: "Approve pre-read" }).click();
    await expect(page.getByRole("status").last()).toContainText("Approved");
    await topics
      .first()
      .getByRole("button", { name: "Why?", exact: true })
      .click();
    await expect(drawer).toContainText("Approved by the RM");
    await page.keyboard.press("Escape");
    await expect(drawer).not.toBeVisible();
    await page
      .getByRole("navigation", { name: "Client switcher" })
      .getByRole("button", { name: /Abdullah Al-Mansoori/ })
      .click();
    await topics
      .first()
      .getByRole("button", { name: "Why?", exact: true })
      .click();
    await expect(drawer).toContainText("Abdullah Al-Mansoori · Topic 1");
    await expect(drawer).toContainText("Generated · awaiting RM review");
    await expect(drawer).not.toContainText("Margarethe");
  });

  test(`commitment evidence retains the client and cash-need terms at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const commitments = page.getByRole("region", { name: "Open commitments" });
    await expect(commitments).toContainText(
      "Planned cash needs cited in this brief. Private-fund commitments are not included.",
    );
    const description = "German inheritance tax instalment";
    const timing = "Due 2026-10-01 to 2026-12-31 · Confirmed";
    await expect(commitments).toContainText(description);
    await expect(commitments).toContainText("€3,400,000");
    await expect(commitments).toContainText(timing);
    const why = commitments.getByRole("button", { name: "Why?", exact: true });
    await why.focus();
    await why.press("Enter");
    const drawer = page.getByRole("dialog", { name: "Why?", exact: true });
    await expect(
      drawer.getByRole("region", { name: "Generated claim" }),
    ).toHaveText(
      `Claim on the dashboardMargarethe Voss-Brenner · ${description} · €3,400,000 · ${timing}`,
    );
    await expect(drawer).toContainText(
      "data/planned_cash_needs.csv · row planned_cash_needs:CN-004",
    );
    expect(
      await drawer.evaluate(
        (element) => element.scrollWidth <= element.clientWidth,
      ),
    ).toBe(true);
    await page.keyboard.press("Escape");
    await expect(drawer).not.toBeVisible();
    await expect(why).toBeFocused();
    await expect(commitments).toContainText(timing);
    await page
      .getByRole("navigation", { name: "Client switcher" })
      .getByRole("button", { name: /Abdullah Al-Mansoori/ })
      .click();
    await expect(commitments).toContainText(
      "Seed capital for Singapore family office entity",
    );
    await why.click();
    await expect(
      drawer.getByRole("region", { name: "Generated claim" }),
    ).toHaveText(
      "Claim on the dashboardAbdullah Al-Mansoori · Seed capital for Singapore family office entity · $5,000,000 · Due 2027-01-01 to 2027-12-31 · Likely",
    );
    await expect(drawer).toContainText("planned_cash_needs:CN-017");
    await expect(drawer).not.toContainText("Margarethe");
    await page.keyboard.press("Escape");
    await expect(drawer).not.toBeVisible();
    await expect(why).toBeFocused();
  });

  test(`workflow evidence retains the client, status, and review at ${width}px`, async ({
    page,
  }) => {
    await page.route("**/api/reviews", async (route) => {
      await route.fulfill({
        json: {
          review: {
            ...route.request().postDataJSON(),
            timestamp: "2026-09-05T10:00:00Z",
            rm: "Priscilla Ong",
          },
        },
      });
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    for (const client of [
      {
        name: "Margarethe Voss-Brenner",
        system: "CRM",
        status: "Email logged 2026-05-29",
        source: "data/rm_notes.json · row rm_notes:N-006",
      },
      {
        name: "Abdullah Al-Mansoori",
        system: "Gmail",
        status: "No thread linked",
        source: "data/clients.csv · row clients:CL-0019",
      },
    ]) {
      await page
        .getByRole("navigation", { name: "Client switcher" })
        .getByRole("button", { name: new RegExp(client.name) })
        .click();
      const workflow = page.getByRole("region", { name: "Where you left off" });
      const item = workflow
        .getByRole("listitem")
        .filter({ hasText: client.status });
      const why = item.getByRole("button", { name: "Why?", exact: true });
      for (const authorship of [
        "Generated · awaiting RM review",
        "Approved by the RM",
      ]) {
        if (authorship === "Approved by the RM") {
          await page.getByRole("button", { name: "Approve pre-read" }).click();
          await expect(page.getByRole("status").last()).toContainText(
            "Approved",
          );
        }
        await why.focus();
        await why.press("Enter");
        const drawer = page.getByRole("dialog", { name: "Why?", exact: true });
        const claim = drawer.getByRole("region", { name: "Generated claim" });
        await expect(claim).toContainText(
          `${client.name} · ${client.system}: ${client.status}`,
        );
        await expect(claim).toContainText(authorship);
        await expect(drawer).toContainText(client.source);
        expect(
          await drawer.evaluate(
            (element) => element.scrollWidth <= element.clientWidth,
          ),
        ).toBe(true);
        await page.keyboard.press("Escape");
        await expect(drawer).not.toBeVisible();
        await expect(why).toBeFocused();
        await expect(item).toContainText(client.status);
      }
    }
  });

  test(`discrepancy evidence retains both sides of the comparison at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    for (const client of [
      {
        name: "Margarethe Voss-Brenner",
        belief: "I have never taken a risk with money.",
        data: "Equity is 71.5% against a 30% limit.",
        note: "rm_notes:N-005",
        fact: "CL-0003:fact:mandate-gap",
      },
      {
        name: "Abdullah Al-Mansoori",
        belief:
          "The Asia portfolio should be uncorrelated with the Gulf business.",
        data: "Shipping and energy-linked positions are 42.1% of the portfolio.",
        note: "rm_notes:N-025",
        fact: "CL-0019:fact:concentration",
      },
    ]) {
      await page
        .getByRole("navigation", { name: "Client switcher" })
        .getByRole("button", { name: new RegExp(client.name) })
        .click();
      await expect(
        page.getByRole("heading", { name: client.name, exact: true }),
      ).toBeVisible();
      const comparison = page.getByRole("region", {
        name: "You said / Data says",
      });
      const why = comparison.getByRole("button", { name: "Why?", exact: true });
      await why.focus();
      await why.press("Enter");
      const drawer = page.getByRole("dialog", { name: "Why?", exact: true });
      const claim = drawer.getByRole("region", { name: "Generated claim" });
      await expect(claim).toContainText(
        `${client.name} · You said: “${client.belief}” Data says: ${client.data}`,
      );
      await expect(claim).toContainText("Generated · awaiting RM review");
      await expect(drawer).toContainText(
        `data/rm_notes.json · row ${client.note}`,
      );
      await expect(drawer).toContainText(client.fact);
      expect(
        await drawer.evaluate(
          (element) => element.scrollWidth <= element.clientWidth,
        ),
      ).toBe(true);
      await page.keyboard.press("Escape");
      await expect(drawer).not.toBeVisible();
      await expect(why).toBeFocused();
      await expect(comparison).toContainText(client.belief);
    }
  });

  test(`Memory evidence retains the extracted belief and client at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    for (const client of [
      {
        name: "Margarethe Voss-Brenner",
        query: "risk",
        belief: "I have never taken a risk with money.",
        source: "rm_notes:N-005",
      },
      {
        name: "Abdullah Al-Mansoori",
        query: "Gulf",
        belief:
          "The Asia portfolio should be uncorrelated with the Gulf business.",
        source: "rm_notes:N-025",
      },
    ]) {
      await page
        .getByRole("navigation", { name: "Client switcher" })
        .getByRole("button", { name: new RegExp(client.name) })
        .click();
      await page.getByRole("tab", { name: "Memory", exact: true }).click();
      const search = page.getByRole("searchbox", {
        name: "Search this client's RM notes",
      });
      await search.fill(client.query);
      const beliefs = page.getByRole("region", { name: "Extracted beliefs" });
      const why = beliefs.getByRole("button", { name: "Why?", exact: true });
      await why.focus();
      await why.press("Enter");
      const drawer = page.getByRole("dialog", { name: "Why?", exact: true });
      await expect(
        drawer.getByRole("region", { name: "Generated claim" }),
      ).toHaveText(
        `Claim on the dashboard${client.name} · Extracted belief: “${client.belief}”`,
      );
      await expect(drawer).toContainText(
        `data/rm_notes.json · row ${client.source}`,
      );
      expect(
        await drawer.evaluate(
          (element) => element.scrollWidth <= element.clientWidth,
        ),
      ).toBe(true);
      await page.keyboard.press("Escape");
      await expect(drawer).not.toBeVisible();
      await expect(why).toBeFocused();
      await expect(search).toHaveValue(client.query);
      await expect(beliefs.locator("mark")).toContainText(client.query);
    }
  });

  test(`browser history dismisses evidence from the previous route at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    await page
      .getByRole("navigation", { name: "Client switcher" })
      .getByRole("button", { name: /Abdullah Al-Mansoori/ })
      .click();
    const whyProfile = page.getByRole("button", { name: "Why this profile?" });
    const drawer = page.getByRole("dialog", { name: "Why?", exact: true });
    await whyProfile.click();
    await expect(drawer).toContainText("clients:CL-0019");

    await page.goBack();
    await expect(page).toHaveURL(/\/clients\/CL-0003\/pre-read$/);
    await expect(drawer).not.toBeVisible();
    await expect(page.getByRole("main")).toBeFocused();
    await whyProfile.click();
    await expect(drawer).toContainText("clients:CL-0003");
    await expect(drawer).not.toContainText("clients:CL-0019");

    await page.goForward();
    await expect(page).toHaveURL(/\/clients\/CL-0019\/pre-read$/);
    await expect(drawer).not.toBeVisible();
    await expect(page.getByRole("main")).toBeFocused();
    await page.getByRole("tab", { name: "Scenario rehearsal" }).click();
    await page.getByRole("button", { name: "Why this range?" }).click();
    await expect(drawer).toContainText("Estimated range · not a forecast.");
    await page.goBack();
    await expect(drawer).not.toBeVisible();
    await expect(page.getByRole("main")).toBeFocused();
    await page.goForward();
    await expect(drawer).not.toBeVisible();
    const whyRange = page.getByRole("button", { name: "Why this range?" });
    await whyRange.focus();
    await whyRange.press("Enter");
    await expect(drawer).toContainText("Abdullah Al-Mansoori");
    await page.keyboard.press("Escape");
    await expect(drawer).not.toBeVisible();
    await expect(whyRange).toBeFocused();
  });

  test(`scenario evidence retains the selected range and caveat at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    const projection = await page.request
      .get("/api/monday-brief")
      .then((response) => response.json());
    for (const client of [
      { id: "CL-0003", name: "Margarethe Voss-Brenner", currency: "EUR" },
      { id: "CL-0014", name: "Lau Chi Ming", currency: "HKD" },
      { id: "CL-0019", name: "Abdullah Al-Mansoori", currency: "USD" },
    ]) {
      await page.goto(`/clients/${client.id}/scenario`);
      for (const scenario of ["Strait reopens", "Strait escalates"]) {
        await page.getByRole("button", { name: scenario, exact: true }).click();
        const result = page.getByRole("region", {
          name: scenario,
          exact: true,
        });
        const range = await result.locator(".range-value").innerText();
        const percentage = await result.locator(".range-percent").innerText();
        const baseline = result.locator(".scenario-baseline");
        const portfolioValue =
          projection.scenarios[client.id].reopens.portfolio_value;
        const baselineText = `Portfolio baseline: ${client.currency} ${portfolioValue.toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} · as of ${projection.as_of}.`;
        await expect(baseline).toHaveText(baselineText);
        await expect(baseline).toBeVisible();
        await expect(result).not.toContainText("today's portfolio");
        const why = result.getByRole("button", { name: "Why this range?" });
        await why.focus();
        await why.press("Enter");
        const drawer = page.getByRole("dialog", { name: "Why?", exact: true });
        const claim = drawer.getByRole("region", { name: "Generated claim" });
        await expect(claim).toContainText(client.name);
        await expect(claim).toContainText(scenario);
        await expect(claim).toContainText(range);
        await expect(claim).toContainText(client.currency);
        await expect(claim).toContainText(percentage);
        await expect(claim).toContainText(baselineText);
        await expect(claim).toContainText("Estimated range · not a forecast.");
        await expect(
          drawer.getByText(/data\/event_log\.csv · row /).first(),
        ).toBeVisible();
        expect(
          await drawer.evaluate(
            (element) => element.scrollWidth <= element.clientWidth,
          ),
        ).toBe(true);
        await page.keyboard.press("Escape");
        await expect(drawer).not.toBeVisible();
        await expect(why).toBeFocused();
      }
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`the switcher reveals the selected client after meeting navigation at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/");
    const clients = page.getByRole("navigation", { name: "Client switcher" });
    const selected = clients.locator('button[aria-current="true"]');
    const expectSelectionInView = async () => {
      await expect
        .poll(() =>
          selected.evaluate((button) => {
            const row = button.getBoundingClientRect();
            const list = button.closest("ul")!.getBoundingClientRect();
            return (
              row.top >= list.top - 1 &&
              row.bottom <= list.bottom + 1 &&
              row.left >= list.left - 1 &&
              row.right <= list.right + 1
            );
          }),
        )
        .toBe(true);
    };
    await page
      .getByRole("navigation", { name: "This week's meetings" })
      .getByRole("button", { name: /Abdullah Al-Mansoori/ })
      .click();
    await expect(selected).toContainText("Abdullah Al-Mansoori");
    await expectSelectionInView();
    await expect(page.getByRole("main")).toBeFocused();

    const search = clients.getByRole("searchbox");
    await search.fill("Margarethe");
    await expect(selected).toHaveCount(0);
    await clients
      .getByRole("button", { name: "Clear client search", exact: true })
      .click();
    await expectSelectionInView();
    await expect(search).toBeFocused();

    await page
      .getByRole("navigation", { name: "This week's meetings" })
      .getByRole("button", { name: /Margarethe Voss-Brenner/ })
      .click();
    await expect(selected).toContainText("Margarethe Voss-Brenner");
    await expectSelectionInView();
    await expect(page.getByRole("main")).toBeFocused();
    await page.goBack();
    await expect(selected).toContainText("Abdullah Al-Mansoori");
    await expectSelectionInView();
    await page.reload();
    await expect(selected).toContainText("Abdullah Al-Mansoori");
    await expectSelectionInView();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
    ).toBe(false);
  });

  test(`reopening the editor uses a save completed after navigation at ${width}px`, async ({
    page,
  }) => {
    const submitted: { action: string; text: string }[] = [];
    let finishSave = () => {};
    const saveGate = new Promise<void>((resolve) => {
      finishSave = resolve;
    });
    await page.route("**/api/reviews", async (route) => {
      const request = route.request().postDataJSON();
      submitted.push(request);
      await saveGate;
      await route.fulfill({
        json: {
          review: {
            ...request,
            timestamp: "2026-09-05T10:00:00Z",
            rm: "Priscilla Ong",
          },
        },
      });
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const edit = page.getByRole("button", { name: "Edit", exact: true });
    const editor = page.getByLabel("Edit the opening line");
    const saved = "Let us discuss your cash needs before the next meeting.";
    await edit.click();
    await editor.fill(saved);
    await page.getByRole("button", { name: "Save edit" }).click();
    await expect.poll(() => submitted.length).toBe(1);

    const clients = page.getByRole("navigation", { name: "Client switcher" });
    await clients.getByRole("button", { name: /Abdullah Al-Mansoori/ }).click();
    await clients
      .getByRole("button", { name: /Margarethe Voss-Brenner/ })
      .click();
    await expect(edit).toBeVisible();
    finishSave();
    const opening = page.getByRole("region", { name: "Suggested opening" });
    await expect(opening).toContainText(saved);
    await edit.click();
    await expect(editor).toBeFocused();
    await expect(editor).toHaveValue(saved);

    await editor.fill(`${saved} Then confirm the timing.`);
    await page.getByRole("tab", { name: "Data", exact: true }).click();
    await page.getByRole("tab", { name: "Overview", exact: true }).click();
    await expect(editor).toHaveValue(`${saved} Then confirm the timing.`);
    await page.getByRole("button", { name: "Cancel edit" }).click();
    await expect(edit).toBeFocused();
    await edit.click();
    await expect(editor).toHaveValue(saved);
    await page.getByRole("button", { name: "Save edit" }).click();
    await expect(edit).toBeFocused();
    expect(submitted).toHaveLength(2);
    expect(submitted[1].text).toBe(saved);
    await expect(opening).toContainText(saved);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
    ).toBe(false);
  });

  test(`Memory distinguishes missing beliefs from search misses at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.route("**/api/monday-brief", async (route) => {
      const response = await route.fetch();
      const projection = await response.json();
      projection.pre_reads["CL-0003"].beliefs = [];
      await route.fulfill({ response, json: projection });
    });
    await page.goto("/clients/CL-0003/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const beliefs = page.getByRole("region", { name: "Extracted beliefs" });
    const notes = page.getByRole("region", { name: "RM notes", exact: true });
    const searchRegion = page.getByRole("region", {
      name: "Search the client memory",
    });
    const search = searchRegion.getByRole("searchbox");
    await expect(beliefs).toContainText("No extracted beliefs available.");
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(2);
    await search.fill("unmatchedword");
    await expect(beliefs).toContainText("No extracted beliefs available.");
    await expect(notes).toContainText(
      "No note mentions unmatchedword. Try another word.",
    );
    await expect(search).toBeFocused();
    await searchRegion
      .getByRole("button", { name: "Clear note search", exact: true })
      .click();
    await expect(search).toBeFocused();
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(2);

    await page
      .getByRole("navigation", { name: "Client switcher" })
      .getByRole("button", { name: /Alistair Pemberton-Hale/ })
      .click();
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    await expect(beliefs.getByRole("article")).toHaveCount(1);
    await search.fill("unmatchedword");
    await expect(beliefs).toContainText(
      "No recorded belief mentions unmatchedword.",
    );
    await expect(beliefs).not.toContainText("No extracted beliefs available.");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`Memory search survives tab changes and stays client scoped at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const memory = page.getByRole("tab", { name: "Memory", exact: true });
    await memory.click();
    const searchRegion = page.getByRole("region", {
      name: "Search the client memory",
    });
    const search = searchRegion.getByRole("searchbox");
    const notes = page.getByRole("region", { name: "RM notes", exact: true });
    await search.fill("risk");

    for (const tab of ["Data", "Insights", "Overview"]) {
      await page.getByRole("tab", { name: tab, exact: true }).click();
      await memory.focus();
      await memory.press("Enter");
      await expect(memory).toBeFocused();
      await expect(search).toHaveValue("risk");
      await expect(searchRegion.getByRole("status")).toContainText(
        "1 of 2 notes",
      );
      await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(1);
      await expect(notes.locator("mark")).toHaveCount(2);
      await expect(notes).not.toContainText("safe and boring");
    }

    await search.focus();
    await searchRegion
      .getByRole("button", { name: "Clear note search", exact: true })
      .click();
    await expect(search).toBeFocused();
    await page.getByRole("tab", { name: "Data", exact: true }).click();
    await memory.click();
    await expect(search).toHaveValue("");
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(2);

    await search.fill("risk");
    const switcher = page.getByRole("navigation", { name: "Client switcher" });
    for (const client of [
      /Alistair Pemberton-Hale/,
      /Margarethe Voss-Brenner/,
    ]) {
      await switcher.getByRole("button", { name: client }).click();
      await memory.click();
      await expect(search).toHaveValue("");
      await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(2);
      await expect(notes.locator("mark")).toHaveCount(0);
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`selected meeting opens the brief from every tab at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const meeting = page
      .getByRole("navigation", { name: "This week's meetings" })
      .getByRole("button", { name: /Margarethe/ });
    const historyLength = await page.evaluate(() => history.length);

    // Reopening this meeting must preserve an unfinished opening edit.
    await page.getByRole("button", { name: "Edit", exact: true }).click();
    const draft = page.getByRole("textbox", { name: "Edit the opening line" });
    await draft.fill("An unfinished meeting opening.");

    for (const tab of ["Memory", "Data", "Insights", "Overview"]) {
      await page.getByRole("tab", { name: tab, exact: true }).click();
      await meeting.focus();
      await meeting.press("Enter");
      await expect(
        page.getByRole("tab", { name: "Overview", exact: true }),
      ).toHaveAttribute("aria-selected", "true");
      const panel = page.getByRole("tabpanel", { name: "Overview" });
      await expect(panel).toBeFocused();
      await expect(panel).toHaveCSS("outline-style", "solid");
      await expect(
        page.getByRole("heading", { name: "Two-minute summary" }),
      ).toBeInViewport();
      await expect(draft).toHaveValue("An unfinished meeting opening.");
      await expect(
        page.getByRole("button", { name: "Approve pre-read" }),
      ).toBeDisabled();
    }
    expect(await page.evaluate(() => history.length)).toBe(historyLength);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`client search matches names and IDs in any order at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/");
    const switcher = page.getByRole("navigation", { name: "Client switcher" });
    const search = switcher.getByRole("searchbox", { name: "Search clients" });
    for (const query of [
      "Voss Brenner",
      "  VOSS   BRENNER  ",
      "Voss-Brenner",
      "Voss\u2011Brenner",
      "Margarethe Brenner",
      "  BRENNER   margarethe  ",
      "Bren Marg",
      "CL-0003",
      "  cl-0003  ",
      "0003",
      "0003 Margarethe",
      "Brenner CL-0003",
    ]) {
      await search.fill(query);
      await expect(switcher.getByRole("status")).toHaveText(
        "1 of 20 clients shown",
      );
      await expect(switcher.getByRole("listitem")).toHaveCount(1);
      await expect(
        switcher.getByRole("button", { name: /Margarethe Voss-Brenner/ }),
      ).toBeVisible();
      await expect(search).toBeFocused();
    }
    for (const query of [
      "Nguyễn",
      "NGUYỄN".normalize("NFD"),
      "Trần Nguyễn",
      "CL-0006 Nguyễn",
    ]) {
      await search.fill(query);
      await expect(switcher.getByRole("status")).toHaveText(
        "1 of 20 clients shown",
      );
      await expect(switcher.getByRole("listitem")).toHaveCount(1);
      await expect(
        switcher.getByRole("button", { name: /Nguyen Thi Bao Tran/ }),
      ).toBeVisible();
      await expect(search).toHaveValue(query);
      await expect(search).toBeFocused();
    }
    await switcher.getByRole("button", { name: /Nguyen Thi Bao Tran/ }).click();
    await expect(
      page.getByRole("heading", { name: "Nguyen Thi Bao Tran", exact: true }),
    ).toBeVisible();
    await expect(
      switcher.getByRole("button", { name: /Nguyen Thi Bao Tran/ }),
    ).toHaveAttribute("aria-current", "true");
    for (const query of [
      "Nguyễn CL-0003",
      "Nguyễn Abdullah",
      "Margarethe Abdullah",
      "Margarethe CL-0019",
      "CL-9999",
      "abcdefghijklmnopqrstuvwxyz".repeat(3),
    ]) {
      await search.fill(query);
      await expect(switcher.getByRole("status")).toHaveText(
        "0 of 20 clients shown",
      );
      await expect(switcher.getByRole("listitem")).toHaveText(
        `No match for “${query}”.`,
      );
      await expect(search).toBeFocused();
      expect(
        await switcher.getByRole("list").evaluate((list) => {
          const message = list.querySelector("li")!;
          return (
            list.scrollWidth <= list.clientWidth &&
            message.scrollWidth <= message.clientWidth
          );
        }),
      ).toBe(true);
    }
    await search.fill("CL-0003");
    await switcher
      .getByRole("button", { name: /Margarethe Voss-Brenner/ })
      .click();
    await expect(
      page.getByRole("heading", {
        name: "Margarethe Voss-Brenner",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      switcher.getByRole("button", { name: /Margarethe Voss-Brenner/ }),
    ).toHaveAttribute("aria-current", "true");
    await search.fill("CL-0019 Abdullah");
    await expect(switcher.getByRole("status")).toHaveText(
      "1 of 20 clients shown",
    );
    await switcher
      .getByRole("button", { name: /Abdullah Al-Mansoori/ })
      .click();
    await expect(
      page.getByRole("heading", { name: "Abdullah Al-Mansoori", exact: true }),
    ).toBeVisible();
    await search.focus();
    await switcher
      .getByRole("button", { name: "Clear client search", exact: true })
      .click();
    await expect(switcher.getByRole("status")).toHaveText(
      "20 clients, ranked by priority",
    );
    await expect(switcher.getByRole("listitem").first()).toContainText(
      "Margarethe Voss-Brenner",
    );
    await expect(search).toBeFocused();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`client profile sources are reachable from every tab at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const why = page.getByRole("button", { name: "Why this profile?" });
    const drawer = page.getByRole("dialog", { name: "Why?" });
    for (const tab of ["Overview", "Insights", "Data", "Memory"]) {
      await page.getByRole("tab", { name: tab, exact: true }).click();
      await why.focus();
      await page.keyboard.press("Enter");
      await expect(drawer).toContainText(
        "Margarethe Voss-Brenner has a Conservative profile.",
      );
      await expect(drawer).toContainText(
        "data/clients.csv · row clients:CL-0003",
      );
      await expect(drawer).toContainText("risk tolerance score");
      await expect(drawer).not.toContainText("data/holdings.csv");
      await page.keyboard.press("Escape");
      await expect(why).toBeFocused();
      await expect(page.getByRole("tabpanel", { name: tab })).toBeVisible();
    }
    await page
      .getByRole("navigation", { name: "Client switcher" })
      .getByRole("button", { name: /Alistair Pemberton-Hale/ })
      .click();
    await why.click();
    await expect(drawer).toContainText("Alistair Pemberton-Hale");
    await expect(drawer).toContainText(
      "data/clients.csv · row clients:CL-0007",
    );
    await expect(drawer).not.toContainText("CL-0003");
    expect(
      await drawer.evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBe(true);
    await page.keyboard.press("Escape");
    await expect(why).toBeFocused();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`within-limit mandates do not displace active topics at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0019/pre-read");
    const top = page.getByRole("region", { name: "Top insights", exact: true });
    const topics = page.getByRole("region", {
      name: "Three discussion topics",
    });
    await expect(top.getByRole("heading", { level: 3 })).toHaveCount(3);
    await expect(top).not.toContainText("Structured Products");
    await expect(top).toContainText("Connected positions represent 42.1%");
    await expect(topics).not.toContainText("Structured Products");

    await page.getByRole("tab", { name: "Insights", exact: true }).click();
    const mandate = page.getByRole("article").filter({
      has: page.getByRole("heading", {
        name: "Structured Products is 12.9% against a 15% maximum.",
        exact: true,
      }),
    });
    await expect(mandate).toContainText("Within limit");
    await expect(mandate).toContainText("Within the 15% maximum");
    await expect(mandate).toContainText(
      "Does the 15% maximum for Structured Products still fit your objectives?",
    );
    await expect(mandate).not.toContainText("brought back inside");
    await mandate.getByRole("button", { name: "Why?" }).click();
    const drawer = page.getByRole("dialog", { name: "Why?" });
    await expect(drawer).toContainText("Structured Products is 12.9%");
    await expect(drawer).toContainText("data/mandates.csv");
    await page.keyboard.press("Escape");
    await expect(mandate.getByRole("button", { name: "Why?" })).toBeFocused();
    expect(
      await mandate.evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBe(true);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);

    await page.goto("/clients/CL-0003/pre-read");
    const breached = top.getByRole("article").first();
    await expect(breached).toContainText("High");
    await expect(breached).toContainText(
      "Equity is 71.5% against a 30% maximum.",
    );
    await expect(breached).toContainText("brought back inside");
  });

  test(`client search reports results without moving focus at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/");
    const switcher = page.getByRole("navigation", { name: "Client switcher" });
    const search = switcher.getByRole("searchbox", { name: "Search clients" });
    const results = switcher.getByRole("status");
    await expect(results).toHaveText("20 clients, ranked by priority");

    await search.fill("Margarethe");
    await expect(results).toHaveText("1 of 20 clients shown");
    await expect(results).toHaveAttribute("aria-atomic", "true");
    await expect(switcher.getByRole("listitem")).toHaveCount(1);
    await expect(search).toBeFocused();

    await search.fill("nobody");
    await expect(results).toHaveText("0 of 20 clients shown");
    await expect(switcher.getByText("No match for “nobody”.")).toBeVisible();
    await expect(search).toBeFocused();
    await search.press("ControlOrMeta+A");
    await search.press("Backspace");
    await expect(results).toHaveText("20 clients, ranked by priority");
    await expect(search).toBeFocused();
    await expect(switcher.getByRole("listitem")).toHaveCount(20);

    await search.fill("   ");
    await expect(results).toHaveText("20 clients, ranked by priority");
    await switcher
      .getByRole("button", { name: "Clear client search", exact: true })
      .click();
    await expect(search).toHaveValue("");
    await expect(search).toBeFocused();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
    ).toBe(false);
  });

  test(`Memory retrieves notes by their complete date at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const searchRegion = page.getByRole("region", {
      name: "Search the client memory",
    });
    const search = searchRegion.getByRole("searchbox");
    const notes = page.getByRole("region", { name: "RM notes", exact: true });
    for (const query of [
      "2026-05-28",
      "2025-05-29",
      "2026-02-29",
      "2026",
      "29",
    ]) {
      await search.fill(query);
      await expect(searchRegion.getByRole("status")).toContainText(
        `0 of 2 notes and 0 of 1 belief mention ${query}.`,
      );
      await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(0);
      await expect(notes.locator("mark")).toHaveCount(0);
    }
    for (const [date, excerpt, noteId] of [
      ["2026-02-16", "Risk profiling completed as Conservative.", "N-005"],
      ["2026-05-29", "EUR 3.4m falls due before year end.", "N-006"],
    ]) {
      const query = `What did she say on ${date}?`;
      await search.fill(query);
      await expect(searchRegion.getByRole("status")).toContainText(
        `1 of 2 notes and 0 of 1 belief mention ${date}.`,
      );
      await expect(notes.locator("mark")).toHaveText(date);
      await expect(notes).toContainText(excerpt);
      await expect(search).toHaveValue(query);
      await expect(search).toBeFocused();
      const why = notes.getByRole("button", { name: "Why?" });
      await why.click();
      const drawer = page.getByRole("dialog", { name: "Why?" });
      await expect(drawer).toContainText(noteId);
      await expect(drawer).toContainText(date);
      await expect(drawer).toContainText(excerpt);
      await page.keyboard.press("Escape");
      await expect(why).toBeFocused();
      await expect(notes.locator("mark")).toHaveText(date);
    }
    await search.focus();
    await searchRegion
      .getByRole("button", { name: "Clear note search" })
      .click();
    await expect(search).toHaveValue("");
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(2);
    await expect(notes.locator("mark")).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`Memory amount searches preserve decimals at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const searchRegion = page.getByRole("region", {
      name: "Search the client memory",
    });
    const search = searchRegion.getByRole("searchbox");
    const notes = page.getByRole("region", { name: "RM notes", exact: true });
    for (const query of ["9.4m", "4m", "13.4m", "3.45m", "34m", "3", "4"]) {
      await search.fill(query);
      await expect(searchRegion.getByRole("status")).toContainText(
        `0 of 2 notes and 0 of 1 belief mention ${query}.`,
      );
      await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(0);
      await expect(notes.locator("mark")).toHaveCount(0);
      await expect(search).toHaveValue(query);
      await expect(search).toBeFocused();
    }
    for (const query of ["3.4m", "What did she say about 3.4M?"]) {
      await search.fill(query);
      await expect(searchRegion.getByRole("status")).toContainText(
        "1 of 2 notes and 0 of 1 belief mention 3.4m.",
      );
      await expect(notes.locator("mark")).toHaveText("3.4m");
      await expect(notes).toContainText("EUR 3.4m falls due before year end.");
      await expect(notes).not.toContainText("Risk profiling completed");
      await expect(search).toHaveValue(query);
    }
    const why = notes.getByRole("button", { name: "Why?" });
    await why.click();
    const drawer = page.getByRole("dialog", { name: "Why?" });
    await expect(drawer).toContainText("N-006");
    await expect(drawer).toContainText("EUR 3.4m falls due before year end.");
    await page.keyboard.press("Escape");
    await expect(why).toBeFocused();
    await expect(notes.locator("mark")).toHaveText("3.4m");
    await search.focus();
    await searchRegion
      .getByRole("button", { name: "Clear note search" })
      .click();
    await expect(search).toHaveValue("");
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(2);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`numeric Memory searches preserve percentage units at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0011/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const ageSearch = page.getByRole("region", {
      name: "Search the client memory",
    });
    const ageNotes = page.getByRole("region", {
      name: "RM notes",
      exact: true,
    });
    for (const query of ["78%", "78 %", "78\u00a0%", "78\u202f%"]) {
      await ageSearch.getByRole("searchbox").fill(query);
      await expect(ageSearch.getByRole("status")).toHaveText(
        "0 of 1 note and 0 of 1 belief mention 78%.",
      );
      await expect(ageNotes.getByRole("button", { name: "Why?" })).toHaveCount(
        0,
      );
      await expect(ageSearch.getByRole("searchbox")).toHaveValue(query);
      await expect(ageSearch.getByRole("searchbox")).toBeFocused();
    }
    await ageSearch.getByRole("searchbox").fill("78");
    await expect(ageNotes.locator("mark")).toHaveText("78");
    await expect(ageNotes).toContainText(
      "Client is 78 and in declining health.",
    );
    await page.goto("/clients/CL-0018/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const searchRegion = page.getByRole("region", {
      name: "Search the client memory",
    });
    const search = searchRegion.getByRole("searchbox");
    const notes = page.getByRole("region", { name: "RM notes", exact: true });
    for (const query of [
      "9%",
      "-5%",
      "−5%",
      "+5%",
      "0",
      "15",
      "5.5",
      "5.5%",
      ".5%",
      ".5 %",
      "-.5%",
      "−.5%",
      "+.5%",
      "0.5%",
      "5.5 %",
      "15%",
      "15 %",
      "5,000",
    ]) {
      await search.fill(query);
      await expect(searchRegion.getByRole("status")).toContainText(
        "0 of 1 note and 0 of 1 belief mention",
      );
      await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(0);
    }
    for (const query of [
      "5",
      "5%",
      "5 %",
      "5\u00a0%",
      "5\u202f%",
      "What did she say about 5 %?",
    ]) {
      const term = query === "5" ? "5" : "5%";
      await search.fill(query);
      await expect(searchRegion.getByRole("status")).toHaveText(
        `1 of 1 note and 0 of 1 belief mention ${term}.`,
      );
      await expect(notes.locator("mark")).toHaveText(term);
      await expect(notes).toContainText(
        "She originally sized it as a 5% hedge.",
      );
      await expect(search).toHaveValue(query);
      await expect(search).toBeFocused();
    }
    const why = notes.getByRole("button", { name: "Why?" });
    await why.click();
    const drawer = page.getByRole("dialog", { name: "Why?" });
    await expect(drawer).toContainText("N-024");
    await expect(drawer).toContainText(
      "She originally sized it as a 5% hedge.",
    );
    await page.keyboard.press("Escape");
    await expect(why).toBeFocused();
    await expect(notes.locator("mark")).toHaveText("5%");
    await search.focus();
    await searchRegion
      .getByRole("button", { name: "Clear note search" })
      .click();
    await expect(search).toHaveValue("");
    await expect(search).toBeFocused();
    await expect(searchRegion.getByRole("status")).toHaveText(
      "Searching 1 note and 1 extracted belief for this client.",
    );
    await expect(notes.locator("mark")).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`Memory preserves signed amounts at ${width}px`, async ({ page }) => {
    const wording =
      "Recorded -5% performance, +3.4m inflows, and −12,500.50 in fees. A 0.5% fee, -.25% adjustment, and +.75m inflow.";
    await page.route("**/api/monday-brief", async (route) => {
      const response = await route.fetch();
      const projection = await response.json();
      projection.evidence["rm_notes:N-024"].record.note = wording;
      await route.fulfill({ response, json: projection });
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0018/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const searchRegion = page.getByRole("region", {
      name: "Search the client memory",
    });
    const search = searchRegion.getByRole("searchbox");
    const notes = page.getByRole("region", { name: "RM notes", exact: true });
    for (const query of [
      "5%",
      "+5%",
      "-3.4m",
      "3.4m",
      "12,500.50",
      "+12,500.50",
      "-500.50",
    ]) {
      await search.fill(query);
      await expect(searchRegion.getByRole("status")).toContainText(
        "0 of 1 note and 0 of 1 belief mention",
      );
      await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(0);
      await expect(notes.locator("mark")).toHaveCount(0);
    }
    for (const [query, highlight] of [
      [".5%", "0.5%"],
      ["0.5 %", "0.5%"],
      ["-.25%", "-.25%"],
      ["−0.25 %", "-.25%"],
      ["+.75m", "+.75m"],
      ["+0.75M", "+.75m"],
      ["-5%", "-5%"],
      ["−5 %", "-5%"],
      ["+3.4M", "+3.4m"],
      ["-12500.50", "−12,500.50"],
      ["−12,500.50", "−12,500.50"],
    ]) {
      await search.fill(query);
      await expect(searchRegion.getByRole("status")).toContainText(
        "1 of 1 note and 0 of 1 belief mention",
      );
      await expect(notes.locator("mark")).toHaveText(highlight);
      await expect(search).toHaveValue(query);
      await expect(search).toBeFocused();
    }
    const why = notes.getByRole("button", { name: "Why?" });
    await why.click();
    await expect(page.getByRole("dialog", { name: "Why?" })).toContainText(
      wording,
    );
    await page.keyboard.press("Escape");
    await expect(why).toBeFocused();
    await search.focus();
    await searchRegion
      .getByRole("button", { name: "Clear note search" })
      .click();
    await expect(search).toHaveValue("");
    await expect(notes).toContainText(wording);
    await expect(notes.locator("mark")).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`Memory matches whole grouped amounts at ${width}px`, async ({
    page,
  }) => {
    const wording =
      "Requested EUR 5,000 for travel, 12500 for repairs, and 1,250,000.50 for a purchase.";
    await page.route("**/api/monday-brief", async (route) => {
      const response = await route.fetch();
      const projection = await response.json();
      projection.evidence["rm_notes:N-024"].record.note = wording;
      await route.fulfill({ response, json: projection });
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0018/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const searchRegion = page.getByRole("region", {
      name: "Search the client memory",
    });
    const search = searchRegion.getByRole("searchbox");
    const notes = page.getByRole("region", { name: "RM notes", exact: true });
    for (const query of [
      "5",
      "000",
      "250",
      "1,250",
      "15,000",
      "5,001",
      "1,250,000",
      "1,250,000.51",
    ]) {
      await search.fill(query);
      await expect(searchRegion.getByRole("status")).toContainText(
        "0 of 1 note and 0 of 1 belief mention",
      );
      await expect(notes.locator("mark")).toHaveCount(0);
      await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(0);
    }
    for (const [query, highlight] of [
      ["5,000", "5,000"],
      ["5000", "5,000"],
      ["12,500", "12500"],
      ["12500", "12500"],
      ["1,250,000.50", "1,250,000.50"],
      ["1250000.50", "1,250,000.50"],
    ]) {
      await search.fill(query);
      await expect(searchRegion.getByRole("status")).toContainText(
        "1 of 1 note and 0 of 1 belief mention",
      );
      await expect(notes.locator("mark")).toHaveText(highlight);
      await expect(notes).toContainText(wording);
      await expect(search).toHaveValue(query);
      await expect(search).toBeFocused();
    }
    const why = notes.getByRole("button", { name: "Why?" });
    await why.click();
    await expect(page.getByRole("dialog", { name: "Why?" })).toContainText(
      wording,
    );
    await page.keyboard.press("Escape");
    await expect(why).toBeFocused();
    await expect(notes.locator("mark")).toHaveText("1,250,000.50");
    expect(
      await page
        .getByRole("main")
        .evaluate((element) => element.scrollWidth <= element.clientWidth),
    ).toBe(true);
  });

  test(`short Memory queries filter notes at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0007/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const searchRegion = page.getByRole("region", {
      name: "Search the client memory",
    });
    const search = searchRegion.getByRole("searchbox");
    const notes = page.getByRole("region", { name: "RM notes", exact: true });
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(2);
    for (const query of ["U.K.", "u.k", "What did he say about U.K.?"]) {
      await search.fill(query);
      await expect(searchRegion.getByRole("status")).toContainText(
        "1 of 2 notes and 0 of 1 belief mention uk.",
      );
      await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(1);
      await expect(notes.locator("mark")).toHaveText("UK");
      await expect(notes).not.toContainText("additional gold purchase");
      await expect(search).toHaveValue(query);
      await expect(search).toBeFocused();
    }
    await search.fill("UK");
    await expect(searchRegion.getByRole("status")).toContainText(
      "1 of 2 notes",
    );
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(1);
    await expect(notes.locator("mark")).toHaveText("UK");
    await expect(notes).toContainText("tax questions remain unresolved");
    await expect(notes).not.toContainText("additional gold purchase");
    await notes.getByRole("button", { name: "Why?" }).click();
    await expect(page.getByRole("dialog", { name: "Why?" })).toContainText(
      "N-011",
    );
    await page.keyboard.press("Escape");
    await expect(notes.getByRole("button", { name: "Why?" })).toBeFocused();
    await expect(search).toHaveValue("UK");
    await search.fill("FX");
    await expect(notes).toContainText("No note mentions fx. Try another word.");
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(0);
    await searchRegion
      .getByRole("button", { name: "Clear note search", exact: true })
      .click();
    await expect(search).toHaveValue("");
    await expect(notes.getByRole("button", { name: "Why?" })).toHaveCount(2);
    await page.goto("/clients/CL-0006/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    for (const query of ["U.S.", "u.s", "What did she say to us about U.S.?"]) {
      await search.fill(query);
      await expect(searchRegion.getByRole("status")).toContainText(
        "1 of 1 note and 1 of 1 belief mention us.",
      );
      await expect(notes.locator("mark")).toHaveText(["US", "US"]);
      await expect(notes).toContainText("first US tuition instalment");
      await expect(search).toHaveValue(query);
      await expect(search).toBeFocused();
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

  test(`incomplete evidence is disclosed at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.route("**/api/monday-brief", async (route) => {
      const response = await route.fetch();
      const projection = await response.json();
      const fact = projection.facts["CL-0003"].find(
        (item: { kind: string }) => item.kind === "mandate_gap",
      );
      // One missing source and event must not disappear behind the valid rows.
      fact.source_rows.push(
        "holdings:missing-source",
        "holdings:missing-source",
      );
      fact.event_ids.push("event:missing-event");
      await route.fulfill({ response, json: projection });
    });
    await page.goto("/clients/CL-0003/pre-read");
    const why = page
      .getByRole("region", { name: "Top insights", exact: true })
      .getByRole("button", { name: "Why?" });
    await why.first().click();
    const drawer = page.getByRole("dialog", { name: "Why?" });
    const warning = drawer.getByRole("alert");
    await expect(warning).toContainText("Evidence trail is incomplete");
    await expect(warning.getByRole("listitem")).toHaveCount(2);
    await expect(warning).toContainText("holdings:missing-source");
    await expect(warning).toContainText("event:missing-event");
    await expect(drawer).toContainText("Deterministic fact");
    await expect(drawer).toContainText("data/holdings.csv");
    expect(
      await warning.evaluate(
        (element) => element.scrollWidth <= element.clientWidth,
      ),
    ).toBe(true);
    expect(
      await warning.evaluate(
        (element) => element.scrollHeight <= element.clientHeight,
      ),
    ).toBe(true);
    await page.keyboard.press("Escape");
    await expect(why.first()).toBeFocused();
    await why.nth(1).click();
    await expect(drawer).toBeVisible();
    await expect(drawer.getByRole("alert")).toHaveCount(0);
  });

  test(`RM note sources preserve search and keyboard focus at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    const notes = page.getByRole("region", { name: "RM notes", exact: true });
    const sources = notes.getByRole("button", { name: "Why?" });
    await expect(sources).toHaveCount(2);
    const search = page.getByRole("searchbox", {
      name: "Search this client's RM notes",
    });

    for (const [query, date, otherDate] of [
      ["risk", "2026-02-16", "2026-05-29"],
      ["boring", "2026-05-29", "2026-02-16"],
    ]) {
      await search.fill(query);
      await expect(sources).toHaveCount(1);
      await sources.focus();
      await page.keyboard.press("Enter");
      const drawer = page.getByRole("dialog", { name: "Why?" });
      await expect(drawer).toBeVisible();
      await expect(drawer.getByRole("article")).toHaveCount(1);
      await expect(drawer).toContainText("data/rm_notes.json · row rm_notes:");
      await expect(drawer).toContainText(date);
      await expect(drawer).not.toContainText(otherDate);
      await expect(drawer).toContainText("CL-0003");
      await expect(drawer).toContainText("Priscilla Ong");
      await expect(
        drawer.getByRole("region", { name: "Generated claim" }),
      ).toHaveCount(0);
      expect(
        await drawer.evaluate(
          (element) => element.scrollWidth <= element.clientWidth,
        ),
      ).toBe(true);
      await page.keyboard.press("Escape");
      await expect(drawer).toHaveCount(0);
      await expect(sources).toBeFocused();
      await expect(search).toHaveValue(query);
      await expect(notes.locator("mark").first()).toContainText(query);
    }
  });

  test(`client navigation updates the title and moves keyboard focus at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/");
    const main = page.getByRole("main");
    await expect(main).toBeVisible();
    await expect(main).not.toBeFocused();
    await expect(page).toHaveTitle("RM dashboard | Wealth Intelligence");
    const workspace = page
      .getByRole("navigation", { name: "Workspace navigation" })
      .getByRole("tablist", { name: "Workspace views" });
    await expect(workspace).toHaveAttribute("aria-orientation", "vertical");
    await expect(
      workspace.getByRole("tab", { name: "RM dashboard" }),
    ).toHaveAttribute("aria-selected", "true");
    await expect(
      workspace.getByRole("tab", { name: "Pre-read", exact: true }),
    ).toBeDisabled();
    const switcher = page.getByRole("navigation", { name: "Client switcher" });
    await switcher.getByRole("button", { name: /Margarethe/ }).focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/CL-0003\/pre-read$/);
    await expect(page).toHaveTitle(
      "Margarethe Voss-Brenner | Pre-read | Wealth Intelligence",
    );
    await expect(main).toBeFocused();
    await expect(main).toHaveCSS("outline-style", "solid");
    await page.keyboard.press("Tab");
    await expect(
      main.getByRole("button", { name: /RM dashboard/ }),
    ).toBeFocused();

    // The meeting that triggered navigation unmounts with its old client.
    const meetings = page.getByRole("navigation", {
      name: "This week's meetings",
    });
    await meetings.getByRole("button", { name: /Abdullah/ }).focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/CL-0019\/pre-read$/);
    await expect(page).toHaveTitle(
      "Abdullah Al-Mansoori | Pre-read | Wealth Intelligence",
    );
    await expect(main).toBeFocused();
    await expect(main).toHaveJSProperty("scrollTop", 0);

    await workspace.getByRole("tab", { name: "Pre-read", exact: true }).focus();
    await page.keyboard.press("ArrowDown");
    await expect(
      workspace.getByRole("tab", { name: "Scenario rehearsal" }),
    ).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/CL-0019\/scenario$/);
    await expect(page).toHaveTitle(
      "Abdullah Al-Mansoori | Scenario rehearsal | Wealth Intelligence",
    );
    await expect(main).toBeFocused();
    await page.goBack();
    await expect(page).toHaveURL(/CL-0019\/pre-read$/);
    await expect(page).toHaveTitle(
      "Abdullah Al-Mansoori | Pre-read | Wealth Intelligence",
    );
    await expect(main).toBeFocused();
    await main.getByRole("button", { name: /RM dashboard/ }).press("Enter");
    await expect(page).toHaveURL(/\/$/);
    await expect(page).toHaveTitle("RM dashboard | Wealth Intelligence");
    await expect(main).toBeFocused();
    await page.goto("/clients/CL-0003/scenario");
    await expect(page).toHaveTitle(
      "Margarethe Voss-Brenner | Scenario rehearsal | Wealth Intelligence",
    );
    await page.reload();
    await expect(page).toHaveTitle(
      "Margarethe Voss-Brenner | Scenario rehearsal | Wealth Intelligence",
    );
    await page.goto("/clients/CL-9999/pre-read");
    await expect(page).toHaveURL(/\/$/);
    await expect(page).toHaveTitle("RM dashboard | Wealth Intelligence");
    await expect(main.getByRole("status")).toContainText(
      "CL-9999 was not found",
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
    ).toBe(false);
  });

  test(`dashboard tabs lead keyboard users into their named panel at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    await page.getByRole("tab", { name: "Overview", exact: true }).click();

    for (const name of ["Overview", "Insights", "Data", "Memory"]) {
      const tab = page.getByRole("tab", { name, exact: true });
      await expect(tab).toBeFocused();
      await tab.press("Enter");
      await expect(tab).toHaveAttribute("aria-selected", "true");
      const panel = page.getByRole("tabpanel", { name, exact: true });
      await page.keyboard.press("Tab");
      await expect(panel).toBeFocused();
      await expect(tab).toHaveAttribute(
        "aria-controls",
        await panel.evaluate((element) => element.id),
      );
      await expect(panel).toHaveCSS("outline-style", "solid");
      await page.keyboard.press("Tab");
      expect(
        await panel.evaluate((element) =>
          element.contains(document.activeElement),
        ),
      ).toBe(true);
      await page.keyboard.press("Shift+Tab");
      await expect(panel).toBeFocused();
      await page.keyboard.press("Shift+Tab");
      await expect(tab).toBeFocused();
      await page.keyboard.press("ArrowRight");
    }
    await expect(
      page.getByRole("tab", { name: "Overview", exact: true }),
    ).toBeFocused();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
      ),
    ).toBe(false);
  });

  test(`review decisions require saving or cancelling the opening edit at ${width}px`, async ({
    page,
  }) => {
    const submitted: { action: string; text: string }[] = [];
    let failSave = true;
    await page.route("**/api/reviews", async (route) => {
      const request = route.request().postDataJSON();
      submitted.push(request);
      await route.fulfill({
        status: request.action === "Edit" && failSave ? 503 : 200,
        contentType: "application/json",
        body: JSON.stringify(
          request.action === "Edit" && failSave
            ? { detail: "Ledger unavailable" }
            : {
                review: {
                  ...request,
                  review_id: "edit-before-review",
                  rm: "Priscilla Ong",
                  timestamp: "2026-09-05T09:00:00+00:00",
                },
              },
        ),
      });
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const edit = page.getByRole("button", { name: "Edit", exact: true });
    const approve = page.getByRole("button", { name: "Approve pre-read" });
    const reject = page.getByRole("button", { name: "Reject", exact: true });
    const editor = page.getByLabel("Edit the opening line");
    await edit.click();
    const original = await editor.inputValue();
    await editor.fill("Unsaved draft");
    for (const button of [approve, reject]) {
      await expect(button).toBeDisabled();
      await expect(button).toHaveAccessibleDescription(
        "Save or cancel your edit before approving or rejecting.",
      );
      await button.focus();
      await button.press("Enter");
      await button.press("Space");
      await button.evaluate((element: HTMLButtonElement) => element.click());
    }
    await expect(editor).toHaveValue("Unsaved draft");
    await expect(
      page.getByText("Generated · awaiting RM review"),
    ).toBeVisible();
    expect(submitted).toHaveLength(0);
    await page.getByRole("button", { name: "Cancel edit" }).click();
    await expect(approve).toBeEnabled();
    await expect(reject).toBeEnabled();
    await reject.click();
    await expect(page.getByText("Rejected by the RM")).toBeVisible();
    expect(submitted.at(-1)).toMatchObject({
      action: "Reject",
      text: original,
    });

    await edit.click();
    await editor.fill("Saved wording for approval");
    await page.getByRole("button", { name: "Save edit" }).click();
    await expect(page.getByRole("alert")).toContainText("Ledger unavailable");
    await expect(approve).toBeDisabled();
    await expect(reject).toBeDisabled();
    await expect(editor).toHaveValue("Saved wording for approval");
    failSave = false;
    await page.getByRole("button", { name: "Save edit" }).click();
    await expect(editor).toHaveCount(0);
    await expect(approve).toBeEnabled();
    await expect(reject).toBeEnabled();
    await approve.click();
    await expect(page.getByText("Approved by the RM")).toBeVisible();
    expect(submitted.at(-1)).toMatchObject({
      action: "Approve",
      text: "Saved wording for approval",
    });
    expect(submitted.map((request) => request.action)).toEqual([
      "Reject",
      "Edit",
      "Edit",
      "Approve",
    ]);
  });

  test(`dismissing review failures returns focus for retry at ${width}px`, async ({
    page,
  }) => {
    const submitted: { action: string; text: string }[] = [];
    const errorMessage = `Review ledger unavailable for reference ${"REFERENCE".repeat(30)}.`;
    await page.route("**/api/reviews", async (route) => {
      submitted.push(route.request().postDataJSON());
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: errorMessage }),
      });
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const opening = page.getByRole("region", { name: "Suggested opening" });
    const original = await opening.innerText();

    for (const [action, label] of [
      ["Approve", "Approve pre-read"],
      ["Reject", "Reject"],
      ["Edit", "Save edit"],
    ]) {
      if (action === "Edit") {
        await page.getByRole("button", { name: "Edit", exact: true }).click();
        await page.getByLabel("Edit the opening line").fill("Retained draft");
      }
      const retry = page.getByRole("button", { name: label, exact: true });
      await retry.click();
      for (let attempt = 0; attempt < 2; attempt += 1) {
        const alert = page.getByRole("alert");
        await expect(alert).toContainText(errorMessage);
        for (const container of [alert, page.getByRole("main")]) {
          await expect
            .poll(() =>
              container.evaluate(
                (element) => element.scrollWidth <= element.clientWidth,
              ),
            )
            .toBe(true);
        }
        const requestCount = submitted.length;
        const dismiss = alert.getByRole("button", {
          name: "Dismiss the review error",
        });
        await dismiss.focus();
        await expect(dismiss).toBeInViewport();
        await page.keyboard.press("Enter");
        await expect(alert).toHaveCount(0);
        await expect(retry).toBeFocused();
        await expect(retry).toBeInViewport();
        expect(submitted).toHaveLength(requestCount);
        expect(submitted.at(-1)?.action).toBe(action);
        expect(await opening.innerText()).toBe(original);
        await expect(
          page.getByText("Generated · awaiting RM review", { exact: true }),
        ).toBeVisible();
        if (action === "Edit") {
          await expect(page.getByLabel("Edit the opening line")).toHaveValue(
            "Retained draft",
          );
        }
        if (attempt === 0) await page.keyboard.press("Enter");
      }
    }
    expect(submitted.map((request) => request.action)).toEqual([
      "Approve",
      "Approve",
      "Reject",
      "Reject",
      "Edit",
      "Edit",
    ]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
    ).toBe(false);
  });

  test(`pending opening saves protect wording and recover at ${width}px`, async ({
    page,
  }) => {
    let finishReview!: () => void;
    let failSave = true;
    const submitted: string[] = [];
    await page.route("**/api/reviews", async (route) => {
      const request = route.request().postDataJSON();
      submitted.push(request.text);
      await new Promise<void>((resolve) => {
        finishReview = resolve;
      });
      await route.fulfill({
        status: failSave ? 503 : 200,
        contentType: "application/json",
        body: JSON.stringify(
          failSave
            ? { detail: "Ledger unavailable" }
            : {
                review: {
                  ...request,
                  review_id: "pending-edit",
                  rm: "Priscilla Ong",
                  timestamp: "2026-09-05T09:00:00+00:00",
                },
              },
        ),
      });
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const edit = page.getByRole("button", { name: "Edit", exact: true });
    await edit.click();
    const editor = page.getByLabel("Edit the opening line");
    const checkpoint = page.getByRole("region", { name: "RM checkpoint" });
    await editor.fill("Submitted wording");
    for (const wording of ["Submitted wording", "Corrected wording"]) {
      await page.getByRole("button", { name: "Save edit" }).click();
      await expect(checkpoint).toHaveAttribute("aria-busy", "true");
      await expect.poll(() => submitted.at(-1)).toBe(wording);
      await expect(editor).not.toBeEditable();
      await editor.focus();
      await editor.press("End");
      await page.keyboard.type(" extra unsaved wording");
      await expect(editor).toHaveValue(wording);
      finishReview();
      await expect(checkpoint).toHaveAttribute("aria-busy", "false");
      if (failSave) {
        await expect(page.getByRole("alert")).toContainText(
          "Ledger unavailable",
        );
        await expect(editor).toBeEditable();
        await expect(editor).toBeFocused();
        await editor.fill("Corrected wording");
        failSave = false;
      }
    }
    await expect(editor).toHaveCount(0);
    await expect(edit).toBeFocused();
    await expect(edit).toBeInViewport();
    await expect(
      page.getByRole("region", { name: "Suggested opening" }),
    ).toContainText("Corrected wording");
    expect(submitted).toEqual(["Submitted wording", "Corrected wording"]);
    await edit.click();
    await expect(editor).toBeEditable();
    await expect(editor).toHaveValue("Corrected wording");
  });

  test(`blank opening edits preserve the brief at ${width}px`, async ({
    page,
  }) => {
    let reviewRequests = 0;
    page.on("request", (request) => {
      if (request.url().endsWith("/api/reviews")) reviewRequests += 1;
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const edit = page.getByRole("button", { name: "Edit", exact: true });
    await edit.click();
    const editor = page.getByLabel("Edit the opening line");
    const original = await editor.inputValue();
    for (const blank of ["", "   \n  "]) {
      await editor.fill(blank);
      const save = page.getByRole("button", { name: "Save edit" });
      await save.focus();
      await save.press("Enter");
      await expect(editor).toBeFocused();
      await expect(editor).toHaveAttribute("aria-invalid", "true");
      await expect(editor).toHaveAccessibleDescription(
        /Enter an opening line before saving/,
      );
      await expect(
        page.getByText("Enter an opening line before saving."),
      ).toBeInViewport();
      await expect(
        page.getByRole("region", { name: "Suggested opening" }),
      ).toContainText(original);
      await expect(
        page.getByText("Generated · awaiting RM review"),
      ).toBeVisible();
    }
    expect(reviewRequests).toBe(0);
    await editor.fill("A valid opening");
    await expect(editor).not.toHaveAttribute("aria-invalid", "true");
    await editor.fill("");
    await page.getByRole("button", { name: "Save edit" }).click();
    await page.getByRole("button", { name: "Cancel edit" }).click();
    await edit.click();
    await expect(editor).toHaveValue(original);
    await expect(editor).not.toHaveAttribute("aria-invalid", "true");
    expect(reviewRequests).toBe(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
    ).toBe(false);
  });

  test(`cancel opening edit restores wording and focus at ${width}px`, async ({
    page,
  }) => {
    let reviewRequests = 0;
    page.on("request", (request) => {
      if (request.url().endsWith("/api/reviews")) reviewRequests += 1;
    });
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");
    const edit = page.getByRole("button", { name: "Edit", exact: true });
    await edit.click();
    const editor = page.getByLabel("Edit the opening line");
    const original = await editor.inputValue();
    await editor.fill("Discard this unsaved draft");
    const cancel = page.getByRole("button", { name: "Cancel edit" });
    await cancel.focus();
    await cancel.press("Enter");
    await expect(editor).toHaveCount(0);
    await expect(edit).toBeFocused();
    await expect(edit).toBeInViewport();
    await expect(
      page.getByRole("region", { name: "Suggested opening" }),
    ).toContainText(original);
    await expect(
      page.getByText("Generated · awaiting RM review"),
    ).toBeVisible();
    await edit.press("Enter");
    await expect(editor).toHaveValue(original);
    await expect(cancel).toBeInViewport();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
    ).toBe(false);
    expect(reviewRequests).toBe(0);
  });

  test(`review shortcut reaches the checkpoint from every tab at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/clients/CL-0003/pre-read");

    for (const tab of ["Memory", "Data", "Insights", "Overview"]) {
      await page.getByRole("tab", { name: tab, exact: true }).click();
      const shortcut = page.getByRole("button", {
        name: "Review meeting brief",
      });
      await shortcut.focus();
      await shortcut.press("Enter");

      await expect(
        page.getByRole("tab", { name: "Overview", exact: true }),
      ).toHaveAttribute("aria-selected", "true");
      await expect(
        page.getByRole("button", { name: "Approve pre-read" }),
      ).toBeInViewport();
      await expect(
        page.getByRole("region", { name: "RM checkpoint" }),
      ).toBeFocused();
      await page.keyboard.press("Tab");
      await expect(
        page.getByRole("button", { name: "Reject", exact: true }),
      ).toBeFocused();
    }
  });
}

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
  // Each card carries the question to put to the client (PRD 5.4).
  await expect(top).toContainText(
    "Do you want Equity brought back inside the 30% maximum",
  );
  // The mandate card draws the 71.5% fill past the 30% limit marker; the two
  // cards whose facts carry no scale draw nothing.
  await expect(
    top.getByText("Equity allocation against the 30% maximum"),
  ).toBeVisible();
  const fill = top.locator('[aria-hidden="true"] > div').first();
  const [fillBox, trackBox] = [
    await fill.boundingBox(),
    await top.locator('[aria-hidden="true"]').first().boundingBox(),
  ];
  expect(fillBox!.width / trackBox!.width).toBeCloseTo(71.5 / (71.5 * 1.1), 2);

  // The Insights tab carries the insights the top three pushed below the fold.
  await page.getByRole("tab", { name: "Insights" }).click();
  const alsoActive = page.getByRole("region", { name: "Also active" });
  await expect(alsoActive.getByRole("article")).toHaveCount(3);
  // The brief's uncertainty names the three snapshot deltas, so it rides those
  // cards rather than the whole dashboard.
  await expect(alsoActive.getByText(/^To confirm: /)).toHaveCount(3);
  await expect(top.getByRole("article")).toHaveCount(3);
  await page.getByRole("tab", { name: "Overview" }).click();

  // The meeting brief opens on PRD 5.5's summary, agenda and commitments.
  const summary = page.getByRole("region", { name: "Two-minute summary" });
  await expect(summary).toContainText("The meeting is Mon");
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
  const opening = page.getByRole("region", { name: "Suggested opening" });
  await expect(opening).toContainText("May I walk you through the gap?");
  await switcher.getByRole("button", { name: /Abdullah Al-Mansoori/ }).click();
  await expect(opening).not.toContainText("May I walk you through the gap?");
  await switcher
    .getByRole("button", { name: /Margarethe Voss-Brenner/ })
    .click();
  await expect(opening).toContainText("May I walk you through the gap?");
  const approval = page.waitForRequest(
    (request) =>
      request.url().endsWith("/api/reviews") && request.method() === "POST",
  );
  await page.getByRole("button", { name: "Approve pre-read" }).click();
  expect((await approval).postDataJSON()).toMatchObject({
    action: "Approve",
    text: "May I walk you through the gap?",
  });
  await expect(page.getByRole("status").last()).toContainText("Approved");
  await expect(opening).toContainText("May I walk you through the gap?");
  await page
    .getByRole("button", { name: "Rehearse a Strait scenario →" })
    .click();
  await page.getByRole("tab", { name: "Pre-read", exact: true }).click();
  await expect(opening).toContainText("May I walk you through the gap?");
  await opening.getByRole("button", { name: "Why?" }).click();
  await expect(page.getByRole("dialog", { name: "Why?" })).toContainText(
    "May I walk you through the gap?",
  );
  await expect(page.getByRole("dialog", { name: "Why?" })).toContainText(
    "Approved by the RM",
  );
  await page.getByRole("button", { name: "Close source trail" }).click();

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

  // The Memory tab answers a plain question over this client's notes (PRD 4).
  await page.getByRole("tab", { name: "Memory" }).click();
  const notes = page.getByRole("region", { name: "RM notes" });
  await expect(notes).toContainText("never taken a risk with money");
  await expect(notes).toContainText("safe and boring");
  await page
    .getByRole("searchbox", { name: "Search this client's RM notes" })
    .fill("What did she say about risk?");
  await expect(
    page.getByRole("region", { name: "Search the client memory" }),
  ).toContainText("1 of 2 notes");
  await expect(notes).toContainText("never taken a risk with money");
  await expect(notes).not.toContainText("safe and boring");
  // Both occurrences of the retrieved word are marked in the surviving note.
  await expect(notes.locator("mark")).toHaveCount(2);
  await page.getByRole("tab", { name: "Overview" }).click();

  // Selecting a meeting switches the whole dashboard to that client (PRD 5.3).
  await calendar.getByRole("button", { name: /Abdullah Al-Mansoori/ }).click();
  await expect(
    page.getByRole("heading", { name: "Abdullah Al-Mansoori" }),
  ).toBeVisible();

  await page.goto("/clients/CL-0019/scenario");
  await expect(
    page.getByRole("main").getByText("Abdullah Al-Mansoori", { exact: true }),
  ).toHaveText("Abdullah Al-Mansoori");
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

test("the shell fits the viewport and scrolls its own panes", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 800 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Who needs you this week" }),
  ).toBeVisible();

  // The shell is 100vh with overflow hidden, so anything taller than the
  // viewport is unreachable rather than scrollable.
  const fits = await page.evaluate(() => {
    const main = document.getElementById("main");
    return main !== null && main.clientHeight <= window.innerHeight;
  });
  expect(fits, "main pane fits the viewport").toBe(true);

  // The last client sits below the fold, so the switcher list must scroll to it
  // and the RM footer must stay pinned in view.
  const list = page
    .getByRole("navigation", { name: "Client switcher" })
    .getByRole("list");
  await expect(page.getByText("Priscilla Ong · Asia desk")).toBeInViewport();
  const last = list.getByRole("listitem").last();
  await expect(last).not.toBeInViewport();
  await last.scrollIntoViewIfNeeded();
  await expect(last).toBeInViewport();

  // The RM checkpoint sits at the end of the longest screen; the main pane has
  // to reach it.
  await page.goto("/clients/CL-0003/pre-read");
  const approve = page.getByRole("button", { name: "Approve pre-read" });
  await approve.scrollIntoViewIfNeeded();
  await expect(approve).toBeInViewport();
});
