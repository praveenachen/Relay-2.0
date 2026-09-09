import { test, expect } from "@playwright/test";
import {
  workflowStatuses,
  stagesFor,
  statusFor,
} from "../features/workflows/status";
import { workflowStatus } from "../lib/schemas";
import {
  workflows,
  displayFor,
  displayForSlug,
} from "../features/workflows/display";

test("every workflow state has an explicit readable presentation", () => {
  for (const state of workflowStatus.options) {
    expect(workflowStatuses[state].label).toBeTruthy();
    expect(workflowStatuses[state].description).toBeTruthy();
    expect(stagesFor(state)).toHaveLength(4);
  }
  expect(statusFor("AWAITING_APPROVAL").label).toBe("Needs review");
  expect(statusFor("EXECUTING").label).toBe("Running");
  expect(statusFor("PARTIALLY_COMPLETED").tone).toBe("warning");
  expect(statusFor("FUTURE_UNKNOWN").label).toBe("Unknown state");
  expect(
    stagesFor("COMPLETED").every((stage) => stage.state === "complete"),
  ).toBe(true);
  expect(stagesFor("FAILED", "ANALYZING")[1].state).toBe("failed");
  expect(stagesFor("FAILED").every((stage) => stage.state === "upcoming")).toBe(
    true,
  );
  expect(stagesFor("AWAITING_APPROVAL")[2].state).toBe("waiting");
});

test("every workflow pillar has a unique slug, key, and a full entry-page script", () => {
  expect(workflows).toHaveLength(3);
  expect(new Set(workflows.map((workflow) => workflow.slug)).size).toBe(3);
  expect(new Set(workflows.map((workflow) => workflow.key)).size).toBe(3);
  for (const workflow of workflows) {
    expect(workflow.steps.length).toBeGreaterThan(0);
    expect(workflow.sources.length).toBeGreaterThan(0);
    expect(workflow.destinations.length).toBeGreaterThan(0);
    expect(displayForSlug(workflow.slug)?.key).toBe(workflow.key);
    expect(displayFor(workflow.key)?.slug).toBe(workflow.slug);
  }
  expect(displayForSlug("not-a-real-slug")).toBeUndefined();
});
