import { expect, test } from "@playwright/test";

test("protected pages require a real session", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
});

test("signup, optional connections, preferences, persisted draft, and logout", async ({
  page,
}, testInfo) => {
  const email = `browser-${Date.now()}@example.com`;
  await page.goto("/signup");
  await page.getByLabel("Name", { exact: true }).fill("Relay Student");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("browser test password 123");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page).toHaveURL(/\/onboarding$/);
  await page.getByRole("button", { name: "Get started" }).click();
  await page
    .getByRole("button", { name: "Connect", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "not implemented yet" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Skip for now" }).click();
  await page.getByLabel("Timezone").fill("America/Toronto");
  await page.getByLabel("Preferred session (minutes)").fill("45");
  await page.getByRole("button", { name: "Save and continue" }).click();
  await page.getByRole("button", { name: "Go to dashboard" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByText("There are no actions waiting for your approval."),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("dashboard-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("dashboard-mobile.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 720 });
  await page
    .getByRole("button", { name: "Create draft", exact: true })
    .first()
    .click();
  await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+$/);
  await expect(page.getByText("Your draft is saved.")).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("workflow created", { exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await expect(page.getByLabel("Preferred session (minutes)")).toHaveValue(
    "45",
  );
  await page.getByLabel("Preferred session (minutes)").fill("100");
  await page.getByLabel("Maximum session (minutes)").fill("50");
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "must not exceed" }),
  ).toBeVisible();
  await page.getByLabel("Preferred session (minutes)").fill("40");
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(page.getByRole("status")).toContainText("Preferences saved");
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("browser test password 123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Continue where you left off" }),
  ).toBeVisible();
});
