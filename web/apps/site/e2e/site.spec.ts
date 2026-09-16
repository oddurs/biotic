import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const pages = [
  "/",
  "/docs/",
  "/docs/start/getting-started/",
  "/design/",
  "/design/components/",
  "/library/",
  "/library/tide-2026-09-08/",
  "/research/",
  "/about/",
  "/notes/",
];

async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(
    results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`),
  ).toEqual([]);
}

for (const path of pages) {
  test(`${path} renders without errors and passes axe`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    const res = await page.goto(path);
    expect(res?.status()).toBe(200);
    await expect(page.locator("main")).toBeVisible();
    await expect(page).toHaveTitle(/biotic/);
    expect(errors).toEqual([]);
    await expectAccessible(page);
  });
}

test("every link in the header and footer resolves", async ({ page, request }) => {
  await page.goto("/");
  const hrefs = await page
    .locator("header a, footer a")
    .evaluateAll((as) => as.map((a) => (a as HTMLAnchorElement).href));
  for (const url of hrefs.filter((u) => u.startsWith("http://localhost:6969"))) {
    const res = await request.get(url);
    expect(res.status(), url).toBe(200);
  }
});

test("theme toggle forces a face and persists", async ({ page }) => {
  await page.goto("/");
  const toggle = page.getByRole("button", { name: /theme/i });
  await toggle.click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await toggle.click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("search finds a docs page", async ({ page }) => {
  await page.goto("/docs/");
  // The search island hydrates on idle; Astro drops the ssr attribute once it has.
  await page.locator('astro-island[component-export="Search"]:not([ssr])').waitFor();
  await page.keyboard.press("/");
  const input = page.getByRole("searchbox", { name: /search query/i });
  await expect(input).toBeVisible();
  await input.fill("membrane");
  await expect(page.getByRole("link", { name: /membrane/i }).first()).toBeVisible();
});

test("feeds, sitemap, robots, and an OG image exist", async ({ request }) => {
  for (const [path, type] of [
    ["/notes/rss.xml", /xml/],
    ["/sitemap-index.xml", /xml/],
    ["/robots.txt", /text\/plain/],
    ["/og/default.png", /image\/png/],
    ["/og/docs/start/getting-started.png", /image\/png/],
  ] as const) {
    const res = await request.get(path);
    expect(res.status(), path).toBe(200);
    expect(res.headers()["content-type"], path).toMatch(type);
  }
});
