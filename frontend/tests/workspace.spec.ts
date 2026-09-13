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
  // Notion, Google Calendar, and GitHub all have real OAuth now, so
  // connecting during onboarding would navigate away to a live provider.
  // This step only verifies connections are optional -- skipping moves on
  // without connecting anything.
  await expect(
    page.getByRole("article").filter({ hasText: "GitHub" }),
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
  page.on("console", (msg) => console.log(`DIAG console: ${msg.text()}`));
  page.on("pageerror", (err) => console.log(`DIAG pageerror: ${err}`));
  page.on("requestfailed", (req) =>
    console.log(`DIAG requestfailed: ${req.url()} ${req.failure()?.errorText}`),
  );
  page.on("response", (res) => {
    if (res.url().includes("workflows/plan")) {
      console.log(`DIAG response: ${res.status()} ${res.url()}`);
    }
  });
  await page.getByRole("link", { name: "Start plan", exact: true }).click();
  await expect(page).toHaveURL(/\/workflows\/plan$/);
  console.log("DIAG about to click Start a study plan");
  await page.getByRole("button", { name: "Start a study plan" }).click();
  console.log("DIAG clicked Start a study plan");
  await expect(page).toHaveURL(/\/workflows\/plan\/[a-f0-9-]+$/, {
    timeout: 15000,
  });
  await expect(page.getByText("Next: save your planning setup.")).toBeVisible();
  await page.reload();
  await expect(page.getByText("Next: save your planning setup.")).toBeVisible();
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

test("LEARN upload review approval and mock publish", async ({
  page,
}, testInfo) => {
  const email = `learn-${Date.now()}@example.com`;
  await page.goto("/signup");
  await page.getByLabel("Name", { exact: true }).fill("Relay Student");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("browser test password 123");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await page.getByRole("button", { name: "Get started" }).click();
  await page.getByRole("button", { name: "Skip for now" }).click();
  await page.getByRole("button", { name: "Save and continue" }).click();
  await page.getByRole("button", { name: "Go to dashboard" }).click();

  await page.goto("/workflows/learn");
  await expect(
    page.getByRole("heading", {
      name: "Turn lecture material into reviewed study notes.",
    }),
  ).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles({
    name: "linear-algebra.md",
    mimeType: "text/markdown",
    buffer: Buffer.from(
      "# Linear Algebra\nA vector has magnitude and direction.\n## Eigenvalues\nEigenvalues describe scaling.",
    ),
  });
  await page.getByRole("button", { name: "Create LEARN run" }).click();
  await expect(page).toHaveURL(/\/workflows\/learn\/[a-f0-9-]+$/);
  await page.getByRole("button", { name: "Parse", exact: true }).click();
  await expect(page.getByText("2 sections parsed")).toBeVisible();
  await page.getByRole("button", { name: "Summarize", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Study page draft" }),
  ).toBeVisible({
    timeout: 15000,
  });
  await page.getByRole("button", { name: "Edit notes" }).click();
  await page.getByLabel("Title").fill("Week 7 - Eigenvalues");
  await page.getByRole("button", { name: "Save notes" }).click();
  await expect(page.getByRole("button", { name: "Approve" })).toBeEnabled({
    timeout: 15000,
  });
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(
    page.getByRole("button", { name: "Publish to Notion" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Publish to Notion" }).click();
  await expect(page.getByText("mock://notion/page/")).toBeVisible({
    timeout: 15000,
  });
  await expect(
    page
      .getByRole("heading", { name: "Week 7 - Eigenvalues", level: 1 })
      .first(),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("learn-desktop.png"),
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
    path: testInfo.outputPath("learn-mobile.png"),
    fullPage: true,
  });
});
