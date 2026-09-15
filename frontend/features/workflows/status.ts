import type { Run } from "@/lib/schemas";

export type Tone = "neutral" | "active" | "success" | "warning" | "danger";
export type StageState =
  "upcoming" | "active" | "complete" | "failed" | "waiting";
export type RelayStage = {
  id: string;
  label: string;
  state: StageState;
  description?: string;
};
type StatusPresentation = {
  label: string;
  tone: Tone;
  symbol: "clock" | "activity" | "check" | "warning" | "stop";
  description: string;
};
export const workflowStatuses: Record<Run["status"], StatusPresentation> = {
  DRAFT: {
    label: "Draft",
    tone: "neutral",
    symbol: "clock",
    description: "Ready when you are.",
  },
  ANALYZING: {
    label: "Understanding",
    tone: "active",
    symbol: "activity",
    description: "Relay is organizing your material.",
  },
  PLAN_READY: {
    label: "Plan ready",
    tone: "warning",
    symbol: "clock",
    description: "Ready for you to review.",
  },
  AWAITING_APPROVAL: {
    label: "Needs review",
    tone: "warning",
    symbol: "clock",
    description: "Review this before Relay saves it.",
  },
  APPROVED: {
    label: "Approved",
    tone: "success",
    symbol: "check",
    description: "Ready to save.",
  },
  QUEUED: {
    label: "Queued",
    tone: "neutral",
    symbol: "clock",
    description: "Waiting to save your changes.",
  },
  EXECUTING: {
    label: "Saving",
    tone: "active",
    symbol: "activity",
    description: "Your changes are being saved.",
  },
  COMPLETED: {
    label: "Completed",
    tone: "success",
    symbol: "check",
    description: "Your work is saved.",
  },
  PARTIALLY_COMPLETED: {
    label: "Partially completed",
    tone: "warning",
    symbol: "warning",
    description: "Some items were saved. Check what still needs attention.",
  },
  FAILED: {
    label: "Failed",
    tone: "danger",
    symbol: "warning",
    description: "Relay could not finish saving this work.",
  },
  REJECTED: {
    label: "Rejected",
    tone: "neutral",
    symbol: "stop",
    description: "These changes were not saved.",
  },
  CANCELLED: {
    label: "Cancelled",
    tone: "neutral",
    symbol: "stop",
    description: "This work was cancelled.",
  },
};
const otherStatuses: Record<string, StatusPresentation> = {
  PENDING: {
    label: "Needs review",
    tone: "warning",
    symbol: "clock",
    description: "Waiting for your decision.",
  },
  EXPIRED: {
    label: "Expired",
    tone: "warning",
    symbol: "warning",
    description: "Reconnect to renew access.",
  },
  REVOKED: {
    label: "Disconnected",
    tone: "neutral",
    symbol: "stop",
    description: "Access has been removed from Relay.",
  },
  CONNECTED: {
    label: "Connected",
    tone: "success",
    symbol: "check",
    description: "This tool is ready to use.",
  },
  ERROR: {
    label: "Connection error",
    tone: "danger",
    symbol: "warning",
    description: "This connection needs attention.",
  },
};
export function statusFor(value: string): StatusPresentation {
  return (
    workflowStatuses[value as Run["status"]] ||
    otherStatuses[value] || {
      label: "Unknown state",
      tone: "neutral",
      symbol: "clock",
      description: "Refresh to check the current state.",
    }
  );
}
export function stagesFor(
  status: Run["status"],
  failedFrom?: string,
): RelayStage[] {
  const index: Partial<Record<Run["status"], number>> = {
    DRAFT: 0,
    ANALYZING: 0,
    PLAN_READY: 1,
    AWAITING_APPROVAL: 1,
    APPROVED: 2,
    QUEUED: 2,
    EXECUTING: 2,
    COMPLETED: 3,
    PARTIALLY_COMPLETED: 2,
    REJECTED: 1,
  };
  const position =
    status === "FAILED" || status === "CANCELLED"
      ? index[failedFrom as Run["status"]]
      : index[status];
  return ["Upload", "Review", "Save"].map((label, i) => {
    let state: StageState = "upcoming";
    if (position !== undefined && i < position) state = "complete";
    if (i === position) {
      state = ["FAILED", "PARTIALLY_COMPLETED", "REJECTED"].includes(status)
        ? "failed"
        : [
              "DRAFT",
              "PLAN_READY",
              "AWAITING_APPROVAL",
              "QUEUED",
              "CANCELLED",
              "APPROVED",
            ].includes(status)
          ? "waiting"
          : "active";
    }
    return { id: label.toLowerCase(), label, state };
  });
}
