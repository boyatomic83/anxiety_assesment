import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/** Answer N questions of one questionnaire with the keyboard (key "k" = option k). */
async function answer(page: Page, name: string, keys: string[], startAt = 1, total = keys.length + startAt - 1) {
  for (let i = 0; i < keys.length; i++) {
    await expect(page.getByText(`${name} · Question ${startAt + i} of ${total}`)).toBeVisible();
    await page.keyboard.press(keys[i]);
  }
}

async function start(page: Page) {
  await page.goto("/");
  await page.getByRole("link", { name: "Start a check-in" }).click();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Begin" }).click();
  await page.getByRole("button", { name: "25-34" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
}

test("full assessment shows validated scores, AI estimate and disclaimer", async ({ page }) => {
  await start(page);
  await answer(page, "GAD-2", ["3", "3"]); // 2 + 2 = 4 -> continue
  await answer(page, "GAD-7", ["3", "2", "2", "2", "2"], 3, 7); // 4 + 2+1+1+1+1 = 10
  await answer(page, "PHQ-9", ["2", "2", "2", "2", "1", "2", "2", "1", "1"]); // item 9 = 0
  await answer(page, "OASIS", ["3", "3", "2", "2", "2"]);
  await page.getByRole("button", { name: "Skip" }).click();
  await page.getByRole("button", { name: "See my results" }).click();

  await expect(page).toHaveURL(/\/results\//);
  await expect(page.getByRole("heading", { name: "Your results" })).toBeVisible();
  await expect(page.getByText("Validated score · GAD-7")).toBeVisible();
  await expect(page.getByRole("img", { name: /GAD-7 score 10 of 21: Moderate/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "AI-assisted estimate" })).toBeVisible();
  await expect(page.getByText("What drove this estimate")).toBeVisible();
  await expect(page.getByText(/screening tool, not a diagnosis/)).toBeVisible();
  await expect(page.getByRole("alertdialog")).toHaveCount(0); // no crisis screen

  const a11y = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag22aa"]).analyze();
  expect(a11y.violations.map((v) => v.id)).toEqual([]);
});

test("PHQ-9 item 9 shows the crisis screen first, then the results", async ({ page }) => {
  await start(page);
  await answer(page, "GAD-2", ["2", "3"]);
  await answer(page, "GAD-7", ["2", "2", "2", "2", "2"], 3, 7);
  await answer(page, "PHQ-9", ["2", "2", "2", "2", "2", "2", "2", "2", "2"]); // item 9 = 1
  await answer(page, "OASIS", ["2", "2", "2", "2", "2"]);
  await page.getByRole("button", { name: "Skip" }).click();
  await page.getByRole("button", { name: "See my results" }).click();

  const dialog = page.getByRole("alertdialog");
  await expect(dialog.getByRole("heading", { name: "You don't have to go through this alone." })).toBeVisible();
  await expect(dialog.getByRole("link", { name: "Call 14416" })).toBeVisible();
  await expect(dialog.getByRole("link", { name: "Call 112" })).toBeVisible();
  await dialog.getByRole("button", { name: "Continue to my results" }).click();
  await expect(page.getByRole("heading", { name: "Your results" })).toBeVisible();
  await expect(page.getByText("Support is available right now:")).toBeVisible();
});

test("low GAD-2 gives a short result", async ({ page }) => {
  await start(page);
  await answer(page, "GAD-2", ["1", "2"]); // 0 + 1 = 1
  await expect(page.getByRole("heading", { name: "Low likelihood of an anxiety disorder" })).toBeVisible();
  await page.getByRole("button", { name: "See my result" }).click();
  await expect(page.getByText("Validated score · GAD-2")).toBeVisible();
});

for (const path of ["/", "/about", "/consent", "/login", "/register"]) {
  test(`no WCAG 2.2 AA violations on ${path}`, async ({ page }) => {
    await page.goto(path);
    const a11y = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag22aa"]).analyze();
    expect(a11y.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
  });
}
