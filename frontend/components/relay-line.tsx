const defaultStages = ["Source", "Understand", "Review", "Destination"];
const stageByStatus: Record<string, number> = {
  DRAFT: 0,
  ANALYZING: 1,
  PLAN_READY: 1,
  AWAITING_APPROVAL: 2,
  APPROVED: 2,
  QUEUED: 3,
  EXECUTING: 3,
  COMPLETED: 4,
  PARTIALLY_COMPLETED: 3,
};
export function RelayLine({
  status,
  stages = defaultStages,
}: {
  status: string;
  stages?: readonly string[];
}) {
  const active = stageByStatus[status];
  return (
    <div className="panel">
      <ol
        aria-label="Workflow progress"
        className="grid grid-cols-2 gap-5 sm:grid-cols-4"
      >
        {stages.map((stage, index) => (
          <li
            key={stage}
            aria-current={active === index ? "step" : undefined}
            className={`border-t-2 pt-4 ${active !== undefined && index <= active ? "border-accent" : "border-line"}`}
          >
            <span className="mb-2 block text-xs text-muted">0{index + 1}</span>
            <span className="font-medium">{stage}</span>
          </li>
        ))}
      </ol>
      <p className="mt-5 text-sm text-muted">
        {status.toLowerCase().replaceAll("_", " ")} · External actions require
        your approval.
      </p>
    </div>
  );
}
