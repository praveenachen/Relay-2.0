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
    description: "Saved and ready for your next step.",
  },
  ANALYZING: {
    label: "Understanding",
    tone: "active",
    symbol: "activity",
    description: "The input is being interpreted.",
  },
  PLAN_READY: {
    label: "Plan ready",
    tone: "warning",
    symbol: "clock",
    description: "A plan is ready to move into review.",
  },
  AWAITING_APPROVAL: {
    label: "Needs review",
    tone: "warning",
    symbol: "clock",
    description: "Your decision is needed before work moves forward.",
  },
  APPROVED: {
    label: "Approved",
    tone: "success",
    symbol: "check",
    description: "Your decision is saved. Execution has not started.",
  },
  QUEUED: {
    label: "Queued",
    tone: "neutral",
    symbol: "clock",
    description: "Waiting to begin execution.",
  },
  EXECUTING: {
    label: "Running",
    tone: "active",
    symbol: "activity",
    description: "Approved work is being carried out.",
  },
  COMPLETED: {
    label: "Completed",
    tone: "success",
    symbol: "check",
    description: "This run is complete.",
  },
  PARTIALLY_COMPLETED: {
    label: "Partially completed",
    tone: "warning",
    symbol: "warning",
    description: "Some actions completed. Review the recorded outcome.",
  },
  FAILED: {
    label: "Failed",
    tone: "danger",
    symbol: "warning",
    description: "This run stopped with an error. Review its activity.",
  },
  REJECTED: {
    label: "Rejected",
    tone: "neutral",
    symbol: "stop",
    description: "The proposal was rejected. No further action is authorized.",
  },
  CANCELLED: {
    label: "Cancelled",
    tone: "neutral",
    symbol: "stop",
    description: "This run was cancelled.",
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
    description: "An account connection is recorded.",
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
    ANALYZING: 1,
    PLAN_READY: 1,
    AWAITING_APPROVAL: 2,
    APPROVED: 2,
    QUEUED: 3,
    EXECUTING: 3,
    COMPLETED: 4,
    PARTIALLY_COMPLETED: 3,
    REJECTED: 2,
  };
  const position =
    status === "FAILED" || status === "CANCELLED"
      ? index[failedFrom as Run["status"]]
      : index[status];
  return ["Source", "Understand", "Review", "Destination"].map((label, i) => {
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
            ].includes(status)
          ? "waiting"
          : status === "APPROVED"
            ? "complete"
            : "active";
    }
    return { id: label.toLowerCase(), label, state };
  });
}
