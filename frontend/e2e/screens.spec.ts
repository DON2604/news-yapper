import fs from "node:fs";
import path from "node:path";
import { type Page, test } from "@playwright/test";

// Visual QA: full-page screenshots of every designed screen at 375 / 768 / 1440 px.
const OUT = path.resolve(__dirname, "../../docs/screenshots");
const WIDTHS = (process.env.SCREEN_WIDTHS ?? "375,768,1440").split(",").map(Number);
const ROUTES: Record<string, string> = {
  home: "/",
  article: "/news/demo-chandrayaan-3-south-pole-landing",
  news: "/news",
  signin: "/signin",
  onboarding: "/onboarding",
  quiz: "/quiz/daily",
  "brain-dump": "/brain-dump",
  crunch: "/brain-dump/crunch",
  revision: "/revision",
  progress: "/progress",
  settings: "/settings",
  admin: "/admin",
};
const PUBLIC = new Set(["home", "article", "news", "signin"]);
// The BFF proxy rejects state-changing requests without a same-origin Origin header.
const SAME_ORIGIN = { origin: process.env.E2E_BASE_URL ?? "http://localhost:3000" };
const PAGES = (process.env.SCREEN_PAGES ?? Object.keys(ROUTES).join(",")).split(",");

async function login(page: Page, name: string) {
  await page.goto("/signin");
  await page.getByLabel("Tor naam").fill(name);
  await page.getByRole("button", { name: /start studying/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/signin"), { timeout: 30_000 });
}

test("capture live quiz and crunch result", async ({ page }) => {
  test.skip(!process.env.SCREEN_FLOWS, "Set SCREEN_FLOWS=1 to capture interactive states");
  test.setTimeout(5 * 60_000);
  fs.mkdirSync(OUT, { recursive: true });
  await login(page, `Screens ${Date.now().toString(36)}`);

  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/quiz/daily");
  await page.getByRole("button", { name: /start quiz/i }).click();
  const options = page.getByRole("group", { name: "Answer options" }).getByRole("button");
  await options.first().waitFor();
  await page.screenshot({ path: path.join(OUT, "quiz-question-1440.png"), animations: "disabled" });
  await options.nth(1).click();
  await page.getByRole("status").getByText(/Correct!|Oops|Not quite/).waitFor();
  await page.screenshot({ path: path.join(OUT, "quiz-feedback-1440.png"), fullPage: true, animations: "disabled" });
  await page.setViewportSize({ width: 375, height: 860 });
  await page.getByRole("button", { name: /next question/i }).click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(OUT, "quiz-question-375.png"), animations: "disabled" });
  await options.first().click();
  await page.getByRole("status").getByText(/Correct!|Oops|Not quite/).waitFor();
  await page.getByRole("status").scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(OUT, "quiz-feedback-375.png"), animations: "disabled" });

  const note = await (
    await page.request.post("/api/backend/notes", {
      headers: SAME_ORIGIN,
      data: { title: "Monetary policy", body: "Repo rate: rate at which RBI lends to banks\nCRR - cash banks keep with RBI\n- MPC has six members chaired by the Governor", color: "mint", tags: ["economy"] },
    })
  ).json();
  await page.request.post("/api/backend/snapshots", { headers: SAME_ORIGIN, data: { article_slug: "demo-gst-council-279a" } });
  const snaps = await (await page.request.get("/api/backend/snapshots")).json();
  const job = await (
    await page.request.post("/api/backend/crunch", {
      headers: SAME_ORIGIN,
      data: { note_ids: [note.id], snapshot_ids: snaps.map((s: { id: string }) => s.id), engine: "offline", settings: { flashcards: 6 } },
    })
  ).json();
  let outputId: string | null = null;
  for (let i = 0; i < 60 && !outputId; i++) {
    const status = await (await page.request.get(`/api/backend/crunch/jobs/${job.id}`)).json();
    outputId = status.output_id;
    if (!outputId) await page.waitForTimeout(1000);
  }
  for (const width of [1440, 375]) {
    await page.setViewportSize({ width, height: width < 800 ? 860 : 960 });
    await page.goto(`/brain-dump/crunch?output=${outputId}`);
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: path.join(OUT, `crunch-result-${width}.png`), fullPage: true, animations: "disabled" });
  }
});

test("capture designed screens", async ({ page }) => {
  test.setTimeout(10 * 60_000);
  fs.mkdirSync(OUT, { recursive: true });
  const ordered = [...PAGES.filter((p) => PUBLIC.has(p)), ...PAGES.filter((p) => !PUBLIC.has(p))];
  let loggedIn = false;
  for (const key of ordered) {
    if (!PUBLIC.has(key) && !loggedIn) {
      await login(page, process.env.SCREEN_USER ?? "admin");
      loggedIn = true;
    }
    for (const width of WIDTHS) {
      const height = width < 800 ? 860 : 960;
      await page.setViewportSize({ width, height });
      await page.goto(ROUTES[key]);
      await page.waitForLoadState("networkidle");
      await page.screenshot({ path: path.join(OUT, `${key}-${width}.png`), fullPage: true, animations: "disabled" });
      if (width < 800) {
        // Viewport-sized slices keep tall mobile pages legible for review.
        const total = await page.evaluate(() => document.documentElement.scrollHeight);
        const slices = Math.min(Math.ceil(total / height), 5);
        for (let i = 0; i < slices; i++) {
          await page.evaluate((y) => window.scrollTo(0, y), i * height);
          await page.waitForTimeout(150);
          await page.screenshot({ path: path.join(OUT, `${key}-${width}-part${i + 1}.png`), animations: "disabled" });
        }
      }
    }
  }
});
