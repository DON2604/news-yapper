import { expect, test } from "@playwright/test";

// Full user journey against the real stack (Postgres + API + worker + web):
// read -> save snapshot -> daily quiz (Mistake Vault) -> sticky -> offline Crunch -> review a card -> progress.
const NAME = process.env.E2E_USER ?? `E2E ${Date.now().toString(36)}`;

test("core study loop works end to end", async ({ page }) => {
  test.setTimeout(240_000);

  await page.goto("/");
  await expect(page.getByRole("link", { name: /Aajke Ki Scene\? - home/ })).toBeVisible();
  await expect(page.getByText(/DEMO edition/)).toBeVisible();

  await page.goto("/signin");
  await page.getByLabel("Tor naam").fill(NAME);
  await page.getByRole("button", { name: /start studying/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/signin"));

  await page.goto("/news/demo-chandrayaan-3-south-pole-landing");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Chandrayaan-3");
  await expect(page.getByRole("heading", { name: "Exam facts" })).toBeVisible();
  await page.getByRole("button", { name: "Pin to Brain Dump" }).click();
  await expect(page.getByRole("button", { name: "Pinned to Brain Dump" })).toBeVisible();

  await page.goto("/quiz/daily");
  await page.getByRole("button", { name: /start quiz/i }).click();
  const options = page.getByRole("group", { name: "Answer options" }).getByRole("button");
  for (let i = 0; i < 15; i++) {
    await options.first().click();
    await expect(page.getByRole("status")).toContainText(/Correct!|Oops|Not quite/);
    const results = page.getByRole("button", { name: /see results/i });
    if (await results.isVisible()) {
      await results.click();
      break;
    }
    await page.getByRole("button", { name: /next question/i }).click();
  }
  await expect(page.getByText("Daily quiz done")).toBeVisible();

  await page.goto("/brain-dump");
  await page.getByRole("button", { name: /new sticky/i }).click();
  await page.getByLabel(/Title/).fill("Repo vs reverse repo");
  await page.getByRole("textbox", { name: "Note", exact: true }).fill("Repo rate: rate at which RBI lends to banks\n- MPC has six members");
  await page.getByRole("button", { name: "Stick it!" }).click();
  await expect(page.getByText("Sticky saved ✓")).toBeVisible();

  await page.goto("/brain-dump/crunch");
  await page.getByRole("checkbox", { name: /Repo vs reverse repo/ }).check();
  await page.getByLabel("Engine").selectOption("offline");
  await expect(page.getByText("Offline engine", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /crunch it/i }).click();
  await expect(page.getByRole("heading", { name: "Revision points" })).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText(/cards saved to Revision/)).toBeVisible();

  await page.goto("/revision");
  await page.getByRole("button", { name: "Show answer" }).click();
  await page.getByRole("button", { name: /^Good/ }).click();
  await expect(page.getByText(/1 reviewed/)).toBeVisible();

  await page.goto("/progress");
  await expect(page.getByText(/XP total/)).toBeVisible();
  await expect(page.getByText(/Current streak/)).toBeVisible();
});

test("private pages require sign-in and other users' data stays private", async ({ page, browser }) => {
  await page.goto("/brain-dump");
  await expect(page).toHaveURL(/\/signin\?callbackUrl=/);

  const res = await page.request.get("/api/backend/notes");
  expect(res.status()).toBe(401);
  const internal = await page.request.post("/api/backend/auth/sync", { data: {} });
  expect(internal.status()).toBe(404);

  const ctx = await browser.newContext();
  const other = await ctx.newPage();
  await other.goto("/signin");
  await other.getByLabel("Tor naam").fill(`Other ${Date.now().toString(36)}`);
  await other.getByRole("button", { name: /start studying/i }).click();
  await other.waitForURL((url) => !url.pathname.startsWith("/signin"));
  const notes = await other.request.get("/api/backend/notes");
  expect(await notes.json()).toEqual([]);
  await ctx.close();
});
