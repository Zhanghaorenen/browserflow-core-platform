import { test, expect } from "@playwright/test";
test("注册、采集、审批、页面路由、主题及移动端", async ({ page }) => {
  const username = "e2e_" + Date.now();
  await page.goto("/login");
  await page.getByRole("button", { name: "创建账号", exact: true }).click();
  await page.getByPlaceholder("输入用户名").fill(username);
  await page.locator('input[type="password"]').fill("StrongExample!123");
  await page.getByRole("button", { name: "注册账号", exact: true }).click();
  await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible();
  await page.getByRole("button", { name: "登录工作空间" }).click();
  await expect(page.getByRole("heading", { name: "工作台总览" })).toBeVisible();
  await expect(page.locator(".welcome-banner")).toBeVisible();
  await page.screenshot({
    path: "../docs/dashboard-desktop.png",
    fullPage: true,
  });
  await page.goto("/templates");
  await expect(
    page.getByRole("heading", { name: "任务模板", exact: true }),
  ).toBeVisible();
  await page
    .locator(".template-card")
    .filter({
      has: page.getByRole("heading", { name: "公开信息采集", exact: true }),
    })
    .getByRole("button", { name: "使用模板" })
    .click();
  await page.getByRole("button", { name: "创建并运行" }).click();
  await expect(page.locator(".page-heading .el-tag")).toContainText("已完成", {
    timeout: 30000,
  });
  const productUrl = page.url();
  await expect(page.locator(".execution-timeline")).toContainText(
    "extract_dom",
  );
  await page.getByRole("tab", { name: "结构化结果" }).click();
  await expect(
    page.locator("pre").filter({ hasText: "Cloud Console" }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 CSV" }).click();
  expect((await download).suggestedFilename()).toContain(".csv");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "../docs/task-execution.png", fullPage: true });
  await page.goto("/templates");
  await page
    .locator(".template-card")
    .filter({
      has: page.getByRole("heading", { name: "企业表单申请", exact: true }),
    })
    .getByRole("button", { name: "使用模板" })
    .click();
  await page.getByRole("button", { name: "创建并运行" }).click();
  await expect(page.locator(".page-heading .el-tag")).toContainText(
    "等待审批",
    { timeout: 30000 },
  );
  const formUrl = page.url();
  await page.getByRole("button", { name: "前往审批中心" }).click();
  await page.getByRole("button", { name: "查看详情" }).first().click();
  await page.getByRole("button", { name: "批准并继续" }).click();
  await page.getByRole("button", { name: "确定", exact: true }).click();
  await page.goto(formUrl);
  await expect(page.locator(".page-heading .el-tag")).toContainText("已完成", {
    timeout: 30000,
  });
  for (const [path, title] of [
    ["/tasks", "任务管理"],
    ["/results", "任务结果中心"],
    ["/monitoring", "系统运行监控"],
    ["/settings", "系统设置"],
  ]) {
    await page.goto(path);
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
  }
  await page.getByRole("tab", { name: "界面主题" }).click();
  await page.getByText("深色主题", { exact: true }).click();
  await page.getByRole("button", { name: "保存设置" }).click();
  await expect(page.locator("html")).toHaveClass("dark");
  await page.goto("/");
  await expect(page.locator(".welcome-banner")).toBeVisible();
  await page.screenshot({ path: "../docs/dashboard-dark.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".metrics")).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "../docs/dashboard-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("button", { name: "展开导航" }).click();
  await expect(page.locator("aside.mobile")).toBeVisible();
  await page.goto(productUrl);
});
