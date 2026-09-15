import type { CSSProperties, ReactNode } from "react";
import { Check, Upload, ScanEye, Send, Clock3, X } from "lucide-react";
import type { Run } from "@/lib/schemas";
import {
  stagesFor,
  statusFor,
  type RelayStage,
} from "@/features/workflows/status";
export type RelayEndpoint = {
  label: string;
  icon?: ReactNode;
  description?: string;
};
export type RelayLineProps = {
  tone?: "learn" | "plan" | "collaborate";
  sources?: readonly RelayEndpoint[];
  destinations?: readonly RelayEndpoint[];
  stages?: readonly RelayStage[];
  status?: Run["status"];
  compact?: boolean;
  label?: string;
};
export function RelayLine({
  tone,
  sources = [{ label: "Your input" }],
  destinations = [{ label: "Your tools" }],
  stages,
  status = "DRAFT",
  compact = false,
  label = "Relay progress",
}: RelayLineProps) {
  const progress = stages || stagesFor(status);
  const icons = [Upload, ScanEye, Send];
  return (
    <figure
      className={`relay-line ${compact ? "compact" : ""}`}
      data-workflow={tone}
      aria-label={label}
    >
      <div className="relay-track">
        <ol
          style={{ "--stage-count": progress.length } as CSSProperties}
          className="relay-stages"
          aria-label="Workflow stages"
        >
          {progress.map((stage, index) => {
            const Icon = icons[index] || Send;
            return (
              <li
                key={stage.id}
                className={`relay-stage ${stage.state}`}
                aria-label={`${stage.label}: ${stage.state}`}
                aria-current={
                  stage.state === "active" || stage.state === "waiting"
                    ? "step"
                    : undefined
                }
              >
                <span className="relay-node" aria-hidden="true">
                  {stage.state === "complete" ? (
                    <Check />
                  ) : stage.state === "failed" ? (
                    <X />
                  ) : stage.state === "waiting" ? (
                    <Clock3 />
                  ) : (
                    <Icon />
                  )}
                </span>
                <span className="relay-stage-label">{stage.label}</span>
                <span className="stage-state" key={stage.state}>
                  {stage.state === "waiting"
                    ? "Your next step"
                    : stage.state === "active"
                      ? "In progress"
                      : stage.state === "complete"
                        ? "Done"
                        : stage.state === "failed"
                          ? "Needs attention"
                          : "Up next"}
                </span>
                {stage.description && <small>{stage.description}</small>}
              </li>
            );
          })}
        </ol>
      </div>
      {!compact && (
        <figcaption>
          <span>
            {sources.map((item) => item.label).join(", ")} &rarr;{" "}
            {destinations.map((item) => item.label).join(", ")}
          </span>
          <span>
            {statusFor(status).label} · {statusFor(status).description}
          </span>
        </figcaption>
      )}
    </figure>
  );
}
