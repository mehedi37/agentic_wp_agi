import { expect, Page, test } from "@playwright/test";

/**
 * Smoke test (T4.6): login -> overview renders KPIs -> approve an action ->
 * ask the assistant a question.
 *
 * Requires a running backend with seeded data (`make up && make seed`, or
 * the equivalent host-run scripts.seed) -- see e2e/README.md. LLM_PROVIDER
 * may be "fake" (the default): the assistant step only checks that an
 * answer renders, not what it says, so the deterministic demo provider is
 * enough to run this in CI with no API keys.
 */

async function login(page: Page, email = "manager@demo.dev") {
  await page.goto("/");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("demo1234");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByRole("heading", { name: "Overview", level: 1 })).toBeVisible();
}

test("login renders the overview with live KPI metrics", async ({ page }) => {
  await login(page);
  const cards = page.locator(".metrics article");
  await expect(cards.first()).toBeVisible();
  expect(await cards.count()).toBeGreaterThan(0);
  // Each KPI card shows a numeric value, not a placeholder.
  await expect(cards.first().locator("strong")).toHaveText(/^\d+$/);
});

test("a manager can approve a pending action", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Approvals" }).click();
  const pending = page
    .locator("article.panel")
    .filter({ has: page.getByRole("button", { name: "Approve" }) })
    .first();

  const empty = page.getByText("No proposed actions yet.");
  // Wait for the async fetch to settle on either state before deciding --
  // checking `empty` immediately after the click races the initial (empty)
  // render against the API response and skips even when data exists.
  await expect(pending.or(empty)).toBeVisible({ timeout: 10_000 });
  if (await empty.isVisible().catch(() => false)) {
    test.skip(true, "No pending actions seeded -- run `make seed` before this suite.");
  }

  const approveButtons = page.getByRole("button", { name: "Approve" });
  const countBefore = await approveButtons.count();
  await expect(pending).toBeVisible();
  await pending.getByRole("button", { name: "Approve" }).click();
  // The approval resumes the paused LangGraph run; re-query rather than
  // reuse `pending` -- once approved it no longer matches the "has an
  // Approve button" filter, so the stale locator would resolve to a
  // different (still-pending) article instead of the one just approved.
  await expect(approveButtons).toHaveCount(countBefore - 1, { timeout: 10_000 });
  await expect(page.locator("article.panel").locator("pre").first()).toBeVisible();
});

test("the assistant answers a question with a response", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "AI assistant" }).click();
  await page.getByLabel("Assistant question").fill("What is overdue and who owns it?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.locator(".message-text")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".message-text")).not.toHaveText("");
});

test("an analyst cannot see the approve/reject controls", async ({ page }) => {
  await login(page, "analyst@demo.dev");
  await page.getByRole("button", { name: "Approvals" }).click();
  await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Settings" })).toHaveCount(0);
});
