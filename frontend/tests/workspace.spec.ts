import { expect, test } from "@playwright/test";

test("protected pages require a real session", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByRole("heading", { name: "Pick up where you left off." }),
  ).toBeVisible();
});

test("Inbox bulk accept uses the confirmed card drafts", async ({ page }) => {
  const email = `inbox-${Date.now()}@example.com`;
  const origin = `http://localhost:${process.env.RELAY_BROWSER_FRONTEND_PORT || "3010"}`;
  const registered = await page.request.post("/api/auth/register", {
    headers: { Origin: origin },
    data: {
      email,
      password: "browser test password 123",
      name: "Inbox Student",
    },
  });
  expect(registered.ok()).toBeTruthy();
  const loggedIn = await page.request.post("/api/auth/login", {
    headers: { Origin: origin },
    form: { username: email, password: "browser test password 123" },
  });
  expect(loggedIn.ok()).toBeTruthy();
  const created = await page.request.post("/api/projects", {
    headers: { Origin: origin },
    data: { name: "10K plan", space: "PERSONAL" },
  });
  expect(created.ok()).toBeTruthy();
  const project = await created.json();
  const captured = await page.request.post(
    `/api/projects/${project.id}/sources`,
    {
      headers: { Origin: origin },
      multipart: {
        source_type: "PERSONAL_GOAL",
        title: "Race goal",
        content: "Prepare for my first 10K",
      },
    },
  );
  expect(captured.ok()).toBeTruthy();

  await page.goto("/inbox");
  const cards = page.locator(".proposal-card");
  const card = cards.first();
  await expect(card).toBeVisible();
  const initialCount = await cards.count();
  const taskTitle = (await card.getByRole("heading").textContent())!;
  await card.locator('input[type="checkbox"]').check();
  const confirmations = card.locator(".confirmation-list button");
  while ((await confirmations.count()) > 0) await confirmations.first().click();
  const acceptSelected = page.getByRole("button", {
    name: "Accept selected (1)",
  });
  await expect(acceptSelected).toBeEnabled();
  await acceptSelected.click();
  await expect(cards).toHaveCount(initialCount - 1);

  await page.goto(`/projects/${project.id}?tab=plan`);
  const taskRow = page.locator(".plan-tasks li").filter({ hasText: taskTitle });
  await expect(taskRow.getByLabel(`Select ${taskTitle}`)).toBeDisabled();
  await taskRow.getByRole("button", { name: "Add details" }).click();
  await page.getByLabel("Due date").fill("2026-10-10");
  await page.getByLabel("Estimate").fill("60");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(taskRow.getByLabel(`Select ${taskTitle}`)).toBeEnabled();
  await taskRow.getByLabel(`Select ${taskTitle}`).check();
  await expect(
    page.getByRole("button", { name: "Plan my week" }),
  ).toBeDisabled();
  await expect(page.getByText("Google Calendar isn’t connected")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Connect Google Calendar" }),
  ).toHaveAttribute("href", "/connections");
  await page.getByRole("link", { name: "Adjust preferences" }).click();
  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByLabel("Preferred session (minutes)")).toBeVisible();
});

test("signup, project workspace, legacy planner, preferences, and logout", async ({
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
    page.getByRole("heading", { name: "Recent projects" }),
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

  // The current product shell is organized around spaces and projects.
  await page.getByRole("link", { name: "School", exact: true }).click();
  await expect(page).toHaveURL(/\/spaces\/school$/);
  await expect(
    page.getByRole("heading", { name: "School", exact: true }),
  ).toBeVisible();
  await page
    .locator(".space-hero")
    .getByRole("button", { name: "New project" })
    .click();
  await page.getByLabel("Project name").fill("Assignment 3");
  await page.getByRole("button", { name: "Create project" }).click();
  await page.getByRole("link").filter({ hasText: "Assignment 3" }).click();
  await expect(page).toHaveURL(/\/projects\/[a-f0-9-]+$/);
  await expect(
    page.getByRole("heading", { name: "Assignment 3" }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Project sections" }),
  ).toBeVisible();

  // Legacy workflow routes remain intentionally reachable while their engines
  // are repurposed behind the project surfaces.
  await page.goto("/workflows/plan");
  await page.getByRole("button", { name: "Build a study plan" }).click();
  await expect(page).toHaveURL(/\/workflows\/plan\/[a-f0-9-]+$/);
  await page.getByRole("button", { name: "Add task" }).click();
  await page.getByLabel("Task name").fill("Assignment 3");
  await expect(page.getByLabel("Estimated effort (minutes)")).toHaveValue("60");
  await expect(
    page.getByRole("button", { name: "Build my plan" }),
  ).toBeDisabled();
  // Google Calendar was never connected during onboarding (skipped above),
  // and Plan now requires an explicit calendar before setup can be saved.
  await expect(page.getByText("Next: connect Google Calendar.")).toBeVisible();
  await page.reload();
  await expect(page.getByText("Next: connect Google Calendar.")).toBeVisible();
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
  await page.locator(".sidebar-account summary").click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("browser test password 123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Recent projects" }),
  ).toBeVisible();
});

test("meeting workspace keeps action items compact and editable", async ({
  page,
}) => {
  const email = `meeting-${Date.now()}@example.com`;
  await page.goto("/signup");
  await page.getByLabel("Name", { exact: true }).fill("Relay Student");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("browser test password 123");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.getByRole("button", { name: "Get started" }).click();
  await page.getByRole("button", { name: "Skip for now" }).click();
  await page.getByRole("button", { name: "Save and continue" }).click();
  await page.getByRole("button", { name: "Go to dashboard" }).click();

  await page.goto("/workflows/collaborate");
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByLabel("Project name").fill("StudySync");
  await page.getByRole("button", { name: "Create project" }).click();
  await page.getByRole("button", { name: "Start a meeting" }).click();
  await page
    .getByLabel("Paste transcript text")
    .fill(
      "Sarah: We decided to use the new API.\nAlex: I'll implement the API tests by Friday.",
    );
  await page.getByRole("button", { name: "Save transcript" }).click();
  await page.getByRole("button", { name: "Prepare meeting" }).click();
  await page.getByRole("button", { name: "Process meeting" }).click();

  await expect(page.getByRole("heading", { name: "Summary" })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.locator(".action-item-row")).toHaveCount(1);
  await expect(page.getByText(/confidence/i)).toHaveCount(0);

  await page.locator(".action-item-row summary").click();
  await page.getByLabel("Task").fill("Write API tests");
  await page.getByRole("button", { name: "Save edits" }).click();
  await expect(page.locator(".action-item-row summary")).toContainText(
    "Write API tests",
  );

  await page
    .locator(".learn-disclosure")
    .filter({ hasText: "Action items" })
    .locator("summary")
    .first()
    .click();
  await expect(
    page.getByRole("button", { name: "Proceed to Approval" }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
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
  await page.getByRole("button", { name: "Create study notes" }).click();
  await expect(page).toHaveURL(/\/workflows\/learn\/[a-f0-9-]+$/);
  await page.getByRole("button", { name: "Parse", exact: true }).click();
  await expect(page.getByText("2 sections parsed")).toBeVisible();
  await expect(page.locator(".relay-stage")).toHaveCount(3);
  await expect(
    page.getByRole("heading", { name: "Destination", exact: true }),
  ).toHaveCount(0);
  await expect(page.locator(".relay-stage").first()).toHaveCSS(
    "border-top-style",
    "solid",
  );
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
    page.getByRole("link", { name: "Return to Dashboard", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "View Completed Actions", exact: true }),
  ).toHaveCount(0);
  await page.getByText("View study notes", { exact: true }).click();
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
