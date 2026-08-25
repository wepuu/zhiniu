import { expect, test } from "@playwright/test";

const inviteCode = process.env.E2E_INVITE_CODE;
const accountEmail = process.env.E2E_ACCOUNT_EMAIL;
const accountPassword = process.env.E2E_ACCOUNT_PASSWORD;

test("registers an invited account and submits real verification and recovery email", async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== "desktop-chromium" ||
      !inviteCode ||
      !accountEmail ||
      !accountPassword,
    "Provide one-time E2E account variables; this test consumes an invitation.",
  );

  await page.goto("/register");
  await page.getByLabel("邀请码").fill(inviteCode!);
  await page.getByLabel("邮箱", { exact: true }).fill(accountEmail!);
  await page.getByLabel("密码", { exact: true }).fill(accountPassword!);
  await page.getByLabel("确认密码").fill(accountPassword!);
  await page
    .getByLabel(/我已阅读并同意/)
    .nth(0)
    .check();
  await page
    .getByLabel(/我已阅读并同意/)
    .nth(1)
    .check();
  await page.getByRole("button", { name: "创建账户" }).click();

  await expect(page).toHaveURL(/\/verify-email/);
  await page.getByRole("button", { name: "重新发送验证邮件" }).click();
  await expect(page.getByRole("status")).toContainText("新的验证邮件已发送");

  await page.goto("/forgot-password");
  await page.getByLabel("注册邮箱").fill(accountEmail!);
  await page.getByRole("button", { name: "发送重置邮件" }).click();
  await expect(page.getByRole("status")).toContainText(
    "如果该邮箱对应账户存在，我们将发送密码重置邮件",
  );
});

test("consumes real verification and password-reset links", async ({
  page,
}, testInfo) => {
  const verificationUrl = process.env.E2E_VERIFICATION_URL;
  const resetUrl = process.env.E2E_RESET_URL;
  const replacementPassword = process.env.E2E_REPLACEMENT_PASSWORD;
  test.skip(
    testInfo.project.name !== "desktop-chromium" ||
      !verificationUrl ||
      !resetUrl ||
      !replacementPassword,
    "Provide the one-time links received in the test mailbox.",
  );

  await page.goto(verificationUrl!);
  await expect(page.getByRole("status")).toContainText("邮箱验证完成");

  await page.goto(resetUrl!);
  await page.getByLabel("新密码").fill(replacementPassword!);
  await page.getByLabel("确认新密码").fill(replacementPassword!);
  await page.getByRole("button", { name: "确认重置密码" }).click();
  await expect(page.getByRole("status")).toContainText(
    "所有旧登录会话均已退出",
  );
});
