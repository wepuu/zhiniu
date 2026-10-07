import { expect, test } from "@playwright/test";

test("redirects an unauthenticated visitor from the application home", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login\?next=%2F/);
});

test("searches by Chinese name, pinyin and code, then opens a deduplicated company timeline", async ({
  context,
  page,
}, testInfo) => {
  const applicationUrl = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3100";
  await context.addCookies([
    {
      name: "zhaoniu_session",
      value: "e2e-route-boundary",
      url: applicationUrl,
    },
  ]);
  await page.goto("/");
  const searchButton =
    testInfo.project.name === "mobile-chromium"
      ? page.getByRole("button", { name: "搜索股票", exact: true })
      : page.getByRole("button", { name: /搜索股票代码、中文名称或拼音/ });
  await searchButton.click();

  const search = page.getByRole("combobox", {
    name: "股票代码、中文名称或拼音",
  });
  await search.fill("贵州茅台");
  await expect(page.getByRole("option", { name: /贵州茅台/ })).toBeVisible();
  await search.fill("guizhoumaotai");
  await expect(page.getByRole("option", { name: /贵州茅台/ })).toBeVisible();
  await search.fill("gzmt");
  await expect(page.getByRole("option", { name: /贵州茅台/ })).toBeVisible();
  await search.fill("600519");
  await expect(page.getByRole("option", { name: /贵州茅台/ })).toBeVisible();
  await search.press("Enter");

  await expect(page).toHaveURL(/\/stock\/600519\.SH/);
  await expect(
    page.locator("h1:visible", { hasText: "贵州茅台" }),
  ).toBeVisible();
  await expect(
    page.locator("h2:visible", { hasText: "研究时间线" }),
  ).toBeVisible();

  const timelineItems = page.locator('[data-testid="timeline-item"]:visible');
  const texts = await timelineItems.allTextContents();
  expect(texts.length).toBeGreaterThan(0);
  expect(new Set(texts).size).toBe(texts.length);
});
