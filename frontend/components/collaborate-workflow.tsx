"use client";
import { ReactNode, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  ChevronDown,
  Play,
  Plus,
  Send,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { approvals } from "@/features/approvals/api";
import { connections } from "@/features/connections/api";
import { useConnections } from "@/hooks/queries";
import {
  CollaborateDetail,
  PlannedAction,
  collaborate,
} from "@/features/collaborate/api";
import { Project, ProjectMember, projects } from "@/features/projects/api";
import { WorkflowBadge } from "@/components/workflow-badge";
import { CompletionActions } from "@/components/completion-actions";
import { RelayLine } from "@/components/relay-line";
import {
  Empty,
  ErrorMessage,
  Loading,
  PageTitle,
  Spinner,
  Status,
} from "@/components/ui";
import { workflowDisplay } from "@/features/workflows/display";

function fileFromText(text: string) {
  return new File([text], "pasted-meeting-transcript.txt", {
    type: "text/plain",
  });
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function CollaborateEntry() {
  const router = useRouter();
  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: projects.list,
  });
  const [selected, setSelected] = useState("");
  const [creating, setCreating] = useState(false);
  const start = useMutation({
    mutationFn: (projectId: string) => collaborate.create(projectId),
    onSuccess: (run) => router.push(`/workflows/collaborate/${run.id}`),
  });

  return (
    <>
      <PageTitle
        eyebrow="Projects"
        title="Turn a meeting into accountable work."
        description="Turn a transcript into decisions and assigned tasks, then confirm what to save to Notion or create in GitHub."
        action={<WorkflowBadge workflow={workflowDisplay.project_meeting} />}
      />
      <RelayLine
        tone="collaborate"
        sources={[{ label: "Meeting transcript" }]}
        destinations={[{ label: "Notion" }, { label: "GitHub" }]}
        status="DRAFT"
      />
      <section className="panel project-picker my-6">
        <div className="project-picker-intro">
          <h2 className="section-title">Choose a project</h2>
          <p className="text-sm text-muted">
            A project remembers your team&apos;s members, Notion task database,
            and GitHub repository so Relay never has to guess them from a
            transcript.
          </p>
        </div>
        <div className="project-picker-controls">
          {projectsQuery.isPending ? (
            <Loading />
          ) : (
            <>
              <ErrorMessage error={projectsQuery.error} />
              {projectsQuery.data && projectsQuery.data.length > 0 && (
                <div className="mt-5 flex flex-wrap items-center gap-3">
                  <select
                    className="min-h-11 rounded-md border border-line bg-surface px-3 text-sm"
                    aria-label="Project"
                    value={selected}
                    onChange={(event) => setSelected(event.target.value)}
                  >
                    <option value="">Choose a project</option>
                    {projectsQuery.data.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                        {project.course ? ` (${project.course})` : ""}
                      </option>
                    ))}
                  </select>
                  <button
                    className="button"
                    disabled={!selected || start.isPending}
                    onClick={() => start.mutate(selected)}
                  >
                    <Play aria-hidden="true" />
                    Start a meeting
                  </button>
                </div>
              )}
              <ErrorMessage error={start.error} />
              <button
                className="button secondary mt-5"
                aria-expanded={creating}
                onClick={() => setCreating((value) => !value)}
              >
                <Plus aria-hidden="true" />
                {creating ? "Cancel" : "New project"}
              </button>
              {creating && (
                <ProjectSetupForm
                  onCreated={(project) => {
                    setCreating(false);
                    setSelected(project.id);
                  }}
                />
              )}
            </>
          )}
        </div>
      </section>
    </>
  );
}

function ProjectSetupForm({
  onCreated,
}: {
  onCreated: (project: Project) => void;
}) {
  const cache = useQueryClient();
  const connectionsQuery = useConnections();
  const hasNotion = (connectionsQuery.data || []).some(
    (item) => item.provider === "NOTION" && item.status === "CONNECTED",
  );
  const hasGithub = (connectionsQuery.data || []).some(
    (item) => item.provider === "GITHUB" && item.status === "CONNECTED",
  );
  const notionDatabases = useQuery({
    queryKey: ["connections", "notion-task-databases"],
    queryFn: connections.notionTaskDatabases,
    enabled: hasNotion,
  });
  const githubRepos = useQuery({
    queryKey: ["connections", "github-repositories"],
    queryFn: connections.githubRepositories,
    enabled: hasGithub,
  });
  const refreshGithubRepos = useMutation({
    mutationFn: connections.githubRepositories,
    onSuccess: (items) => {
      cache.setQueryData(["connections", "github-repositories"], items);
    },
  });
  const [name, setName] = useState("");
  const [course, setCourse] = useState("");
  const [notionDatabaseId, setNotionDatabaseId] = useState("");
  const [mappingTitle, setMappingTitle] = useState("Name");
  const [mappingOwner, setMappingOwner] = useState("Owner");
  const [mappingDeadline, setMappingDeadline] = useState("Due");
  const [mappingStatus, setMappingStatus] = useState("Status");
  const [statusType, setStatusType] = useState<"select" | "status">("status");
  const [repoFullName, setRepoFullName] = useState("");
  const [manualRepoFullName, setManualRepoFullName] = useState("");

  const manualRepoMatch = manualRepoFullName
    .trim()
    .match(/^([^/\s]+)\/([^/\s]+)$/);
  const listedRepo = (githubRepos.data || []).find(
    (item) => item.full_name === repoFullName,
  );
  const selectedRepo =
    repoFullName === "__manual__" && manualRepoMatch
      ? { owner: manualRepoMatch[1], name: manualRepoMatch[2] }
      : listedRepo;

  const create = useMutation({
    mutationFn: () =>
      projects.create({
        name,
        course: course || null,
        notion_database_id: notionDatabaseId || null,
        notion_property_mapping: notionDatabaseId
          ? {
              title: mappingTitle,
              owner: mappingOwner || null,
              deadline: mappingDeadline || null,
              status: mappingStatus || null,
              status_property_type: statusType,
              default_status: "To Do",
            }
          : null,
        github_repository_owner: selectedRepo?.owner || null,
        github_repository_name: selectedRepo?.name || null,
      }),
    onSuccess: async (project) => {
      await cache.invalidateQueries({ queryKey: ["projects"] });
      onCreated(project);
    },
  });

  return (
    <div className="mt-6 border-t border-line pt-6">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="field">
          Project name
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label className="field">
          Course
          <input
            value={course}
            onChange={(event) => setCourse(event.target.value)}
          />
        </label>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <label className="field">
          Notion task database
          {hasNotion ? (
            <>
              <select
                value={notionDatabaseId}
                onChange={(event) => setNotionDatabaseId(event.target.value)}
                disabled={notionDatabases.isPending}
              >
                <option value="">
                  {notionDatabases.isPending ? "Loading databases..." : "None"}
                </option>
                {(notionDatabases.data || []).map((database) => (
                  <option key={database.id} value={database.id}>
                    {database.title}
                  </option>
                ))}
              </select>
              <span className="text-sm text-muted">
                Choose where confirmed meeting tasks should be added.
              </span>
              {notionDatabases.error && (
                <span className="text-sm text-danger">
                  Relay could not load Notion databases. Refresh Connections
                  after sharing a database with Relay.
                </span>
              )}
              {!notionDatabases.isPending &&
                !notionDatabases.error &&
                (notionDatabases.data || []).length === 0 && (
                  <span className="text-sm text-muted">
                    No task databases found. In Notion, share the database
                    itself with Relay, then refresh.
                  </span>
                )}
            </>
          ) : (
            <span className="text-sm text-muted">
              <Link className="text-link" href="/connections">
                Connect Notion
              </Link>{" "}
              to create tasks there.
            </span>
          )}
        </label>
        <label className="field">
          GitHub repository
          {hasGithub ? (
            <>
              <select
                value={repoFullName}
                onChange={(event) => setRepoFullName(event.target.value)}
                disabled={githubRepos.isPending || refreshGithubRepos.isPending}
              >
                <option value="">
                  {githubRepos.isPending ? "Loading repositories..." : "None"}
                </option>
                {(githubRepos.data || []).map((item) => (
                  <option key={item.full_name} value={item.full_name}>
                    {item.full_name}
                  </option>
                ))}
                <option value="__manual__">Enter repository manually</option>
              </select>
              <button
                type="button"
                className="button secondary"
                disabled={refreshGithubRepos.isPending}
                onClick={() => refreshGithubRepos.mutate()}
              >
                {refreshGithubRepos.isPending && (
                  <Spinner label="Refreshing repositories" />
                )}
                Refresh repositories
              </button>
              {repoFullName === "__manual__" && (
                <input
                  value={manualRepoFullName}
                  onChange={(event) =>
                    setManualRepoFullName(event.target.value)
                  }
                  placeholder="owner/repository, e.g. praveenachen/Relay-2.0"
                  aria-label="GitHub repository full name"
                />
              )}
              {(githubRepos.error || refreshGithubRepos.error) && (
                <span className="text-sm text-danger">
                  Relay could not load GitHub repositories. Refresh to try the
                  current connection again.
                </span>
              )}
              {!githubRepos.isPending &&
                !githubRepos.error &&
                (githubRepos.data || []).length === 0 && (
                  <span className="text-sm text-muted">
                    No repositories found for this GitHub connection. You can
                    enter owner/repository manually, or reconnect GitHub if the
                    repository should appear here.
                  </span>
                )}
            </>
          ) : (
            <span className="text-sm text-muted">
              <Link className="text-link" href="/connections">
                Connect GitHub
              </Link>{" "}
              to create issues there.
            </span>
          )}
        </label>
      </div>
      {notionDatabaseId && (
        <details className="project-advanced">
          <summary>Advanced Notion field settings</summary>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="field">
              Title property
              <input
                value={mappingTitle}
                onChange={(e) => setMappingTitle(e.target.value)}
              />
            </label>
            <label className="field">
              Owner property
              <input
                value={mappingOwner}
                onChange={(e) => setMappingOwner(e.target.value)}
              />
            </label>
            <label className="field">
              Deadline property
              <input
                value={mappingDeadline}
                onChange={(e) => setMappingDeadline(e.target.value)}
              />
            </label>
            <label className="field">
              Status property
              <input
                value={mappingStatus}
                onChange={(e) => setMappingStatus(e.target.value)}
              />
            </label>
            <label className="field">
              Status property type
              <select
                value={statusType}
                onChange={(e) =>
                  setStatusType(e.target.value as "select" | "status")
                }
              >
                <option value="status">Status</option>
                <option value="select">Select</option>
              </select>
            </label>
          </div>
        </details>
      )}
      <ErrorMessage error={create.error} />
      <button
        className="button mt-5"
        disabled={!name.trim() || create.isPending}
        onClick={() => create.mutate()}
      >
        Create project
      </button>
    </div>
  );
}

export function CollaborateRun({ id }: { id: string }) {
  const cache = useQueryClient();
  const detail = useQuery({
    queryKey: ["collaborate", id],
    queryFn: () => collaborate.detail(id),
    refetchInterval: (query) =>
      query.state.data?.run.status === "ANALYZING" ? 1500 : false,
  });
  const invalidate = async () => {
    await Promise.all([
      cache.invalidateQueries({ queryKey: ["collaborate", id] }),
      cache.invalidateQueries({ queryKey: ["runs"] }),
      cache.invalidateQueries({ queryKey: ["events", id] }),
      cache.invalidateQueries({ queryKey: ["approvals"] }),
    ]);
  };
  if (detail.isPending) return <Loading />;
  if (detail.error) return <ErrorMessage error={detail.error} />;
  const data = detail.data;

  const needsTranscriptWork =
    data.run.status === "DRAFT" ||
    data.stage === "transcript_ready" ||
    data.stage === "analyzing";

  return (
    <>
      <PageTitle
        eyebrow="Projects"
        title={data.project?.name || "Meeting"}
        description="Review decisions, owners, and where each task should be saved before anything is created."
        action={<Status value={data.run.status} />}
      />
      <RelayLine
        tone="collaborate"
        sources={[{ label: "Meeting transcript" }]}
        destinations={[{ label: "Notion" }, { label: "GitHub" }]}
        status={data.run.status}
      />
      {data.run.error_message && (
        <div className="notice error my-6">
          <X aria-hidden="true" />
          <p>{data.run.error_message}</p>
        </div>
      )}
      {needsTranscriptWork ? (
        <TranscriptStage id={id} data={data} invalidate={invalidate} />
      ) : (
        <ReviewAndApprove id={id} data={data} invalidate={invalidate} />
      )}
    </>
  );
}

function transcriptNextStep(
  data: CollaborateDetail,
  busy: boolean,
  hasDraftTranscript: boolean,
) {
  if (busy) {
    return {
      title: "Processing your meeting…",
      description: "Finding the summary, decisions, and action items.",
    };
  }
  if (!data.source) {
    return {
      title: "Next: save a transcript.",
      description: hasDraftTranscript
        ? "Save the selected file or pasted transcript to continue."
        : "Choose a transcript file or paste meeting notes below.",
    };
  }
  if (data.stage !== "transcript_ready" && data.stage !== "plan_ready") {
    return {
      title: "Ready to process your meeting.",
      description:
        "Relay will prepare the transcript, then find the important outcomes.",
    };
  }
  return {
    title: "Find decisions and action items.",
    description: "Relay will organize the meeting into a clear project update.",
  };
}

function collaborateReviewNextStep(
  data: CollaborateDetail,
  busy: boolean,
  actionCount: number,
  hasUnsavedEdits: boolean,
) {
  if (busy) {
    return {
      title: "Saving your changes…",
      description: "Your meeting workspace will refresh when it is ready.",
    };
  }
  if (data.run.status === "PLAN_READY") {
    return {
      title: hasUnsavedEdits
        ? "Next: save your action-item edits."
        : "Your action items are ready.",
      description: hasUnsavedEdits
        ? "Save your owner, due date, or destination changes before continuing."
        : actionCount
          ? "Review the tasks, then continue when they look right."
          : "Relay did not find action items in this transcript.",
    };
  }
  if (data.approvals.some((approval) => approval.status === "PENDING")) {
    return {
      title: "Confirm what Relay should create.",
      description: "Review the Notion tasks and GitHub issues below.",
    };
  }
  if (data.run.status === "APPROVED") {
    return {
      title: "Ready to create your project tasks.",
      description:
        "Relay will create the confirmed Notion tasks and GitHub issues.",
    };
  }
  return {
    title: "Your meeting workspace was updated.",
    description: "Review the latest details below.",
  };
}

function NextStepNotice({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  const working = title.includes("…");
  return (
    <div className={`notice next-step my-6 ${working ? "working" : ""}`}>
      <div>
        <p className="font-medium">{title}</p>
        <p className="mt-1">{description}</p>
      </div>
    </div>
  );
}

function TranscriptStage({
  id,
  data,
  invalidate,
}: {
  id: string;
  data: CollaborateDetail;
  invalidate: () => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [pasted, setPasted] = useState("");
  const [meetingDate, setMeetingDate] = useState(todayIso());
  const upload = useMutation({
    mutationFn: () => collaborate.upload(id, file || fileFromText(pasted)),
    onSuccess: invalidate,
  });
  const parse = useMutation({
    mutationFn: () => collaborate.parse(id, meetingDate),
    onSuccess: invalidate,
  });
  const analyze = useMutation({
    mutationFn: () => collaborate.analyze(id),
    onSuccess: invalidate,
  });
  const busy = upload.isPending || parse.isPending || analyze.isPending;
  const nextStep = transcriptNextStep(
    data,
    busy,
    Boolean(file || pasted.trim()),
  );

  if (!data.source) {
    return (
      <section className="panel my-8">
        <NextStepNotice {...nextStep} />
        <h2 className="section-title">Meeting transcript</h2>
        <label className="learn-drop">
          <Upload aria-hidden="true" />
          <span>
            {file ? file.name : "Choose a TXT, Markdown, or DOCX transcript"}
          </span>
          <input
            type="file"
            accept=".txt,.md,.markdown,.docx,text/plain,text/markdown"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
        </label>
        <label className="field mt-5">
          Paste transcript text
          <textarea
            rows={8}
            value={pasted}
            onChange={(event) => setPasted(event.target.value)}
            placeholder={
              "Sarah: I'll handle authentication.\n\n[10:42] Alex:\nI'll review Sarah's PR."
            }
          />
        </label>
        <label className="field mt-5 max-w-xs">
          Meeting date
          <input
            type="date"
            value={meetingDate}
            onChange={(event) => setMeetingDate(event.target.value)}
          />
        </label>
        <ErrorMessage error={upload.error} />
        <button
          className="button mt-5"
          disabled={busy || !(file || pasted.trim())}
          onClick={() => upload.mutate()}
        >
          Save transcript
        </button>
      </section>
    );
  }

  return (
    <section className="panel my-8">
      <NextStepNotice {...nextStep} />
      <h2 className="section-title">Transcript saved</h2>
      <p className="text-sm text-muted">
        {data.source.filename} ({(data.source.size_bytes / 1024).toFixed(1)} KB)
      </p>
      <ErrorMessage error={parse.error || analyze.error} />
      <div className="mt-5 flex flex-wrap gap-3">
        {data.stage !== "transcript_ready" && data.stage !== "plan_ready" && (
          <button
            className="button"
            disabled={busy}
            onClick={() => parse.mutate()}
          >
            Prepare meeting
          </button>
        )}
        {(data.stage === "transcript_ready" ||
          data.run.status === "ANALYZING") && (
          <button
            className="button"
            disabled={busy || data.stage === "analyzing"}
            onClick={() => analyze.mutate()}
          >
            {analyze.isPending || data.stage === "analyzing" ? (
              <Spinner label="Generating meeting actions" />
            ) : (
              <Play aria-hidden="true" />
            )}
            {analyze.isPending || data.stage === "analyzing"
              ? "Processing your meeting…"
              : "Process meeting"}
          </button>
        )}
      </div>
    </section>
  );
}

function ReviewAndApprove({
  id,
  data,
  invalidate,
}: {
  id: string;
  data: CollaborateDetail;
  invalidate: () => Promise<void>;
}) {
  const membersQuery = useQuery({
    queryKey: ["projects", data.project?.id, "members"],
    queryFn: () => projects.members(data.project!.id),
    enabled: !!data.project,
  });
  const [items, setItems] = useState<PlannedAction[] | null>(null);
  const actionItems = items ?? data.action_items;
  const pendingApprovals = data.approvals.filter(
    (approval) => approval.status === "PENDING",
  );

  const save = useMutation({
    mutationFn: (next: PlannedAction[]) =>
      collaborate.updateActionItems(id, next),
    onSuccess: async (updated) => {
      setItems(null);
      await invalidate();
      return updated;
    },
  });
  const requestApproval = useMutation({
    mutationFn: () => collaborate.requestApproval(id),
    onSuccess: invalidate,
  });
  const resolve = useMutation({
    mutationFn: (approval: CollaborateDetail["approvals"][number]) =>
      approvals.resolve(approval, true),
    onSuccess: invalidate,
  });
  const reject = useMutation({
    mutationFn: (approval: CollaborateDetail["approvals"][number]) =>
      approvals.resolve(approval, false),
    onSuccess: invalidate,
  });
  const approveAll = useMutation({
    mutationFn: async () => {
      for (const approval of pendingApprovals) {
        await approvals.resolve(approval, true);
      }
    },
    onSuccess: invalidate,
  });
  const execute = useMutation({
    mutationFn: () => collaborate.execute(id),
    onSuccess: invalidate,
  });

  const busy =
    save.isPending ||
    requestApproval.isPending ||
    resolve.isPending ||
    reject.isPending ||
    approveAll.isPending ||
    execute.isPending;
  const canEdit = data.run.status === "PLAN_READY";
  const members = membersQuery.data || [];
  const isReviewPhase = data.run.status === "PLAN_READY";
  const isApprovalPhase = pendingApprovals.length > 0;
  const isExecutionPhase = data.run.status === "APPROVED";
  const isCompletePhase =
    data.run.status === "COMPLETED" ||
    data.run.status === "PARTIALLY_COMPLETED";
  const notionCount = pendingApprovals.filter(
    (approval) => typeof approval.original_payload.database_id === "string",
  ).length;
  const githubCount = pendingApprovals.filter(
    (approval) =>
      typeof approval.original_payload.repository_owner === "string",
  ).length;

  const updateItem = (index: number, patch: Partial<PlannedAction>) => {
    const next = actionItems.map((item, i) =>
      i === index ? { ...item, ...patch } : item,
    );
    setItems(next);
  };
  const removeItem = (index: number) => {
    const next = actionItems.filter((_, i) => i !== index);
    setItems(next);
    save.mutate(next);
  };

  return (
    <section className="my-8 space-y-8">
      <NextStepNotice
        {...collaborateReviewNextStep(
          data,
          busy,
          actionItems.length,
          Boolean(items),
        )}
      />
      <ErrorMessage
        error={
          save.error ||
          requestApproval.error ||
          resolve.error ||
          reject.error ||
          approveAll.error ||
          execute.error
        }
      />

      {isReviewPhase && (
        <>
          <div className="meeting-meta">
            <span>Meeting workspace</span>
            {data.source?.filename && <span>{data.source.filename}</span>}
          </div>
          {data.summary && <CollaborateSummary data={data} />}
          <DisclosurePanel
            title={`Decisions (${data.decisions.length})`}
            defaultOpen
          >
            {data.decisions.length > 0 ? (
              <div className="decision-list">
                {data.decisions.map((decision, index) => (
                  <article key={index} className="decision-item">
                    <p className="font-medium">{decision.title}</p>
                    <p className="mt-2 text-sm text-muted">
                      {decision.description}
                    </p>
                  </article>
                ))}
              </div>
            ) : (
              <Empty title="No decisions found.">
                Relay did not find explicit meeting decisions in this
                transcript.
              </Empty>
            )}
          </DisclosurePanel>

          <DisclosurePanel
            title={`Action items (${actionItems.length})`}
            defaultOpen
          >
            {actionItems.length === 0 ? (
              <Empty title="No action items found.">
                Relay found decisions but no clear owner commitments in this
                transcript.
              </Empty>
            ) : (
              <div className="action-item-list">
                {actionItems.map((item, index) => (
                  <ActionItemCard
                    key={item.id}
                    item={item}
                    members={members}
                    editable={canEdit}
                    onChange={(patch) => updateItem(index, patch)}
                    onRemove={() => removeItem(index)}
                  />
                ))}
              </div>
            )}
          </DisclosurePanel>
          {canEdit && (
            <div className="mt-5 flex flex-wrap gap-3">
              {items && (
                <button
                  className="button"
                  disabled={busy}
                  onClick={() => save.mutate(actionItems)}
                >
                  Save edits
                </button>
              )}
              <button
                className={
                  !items && actionItems.length > 0 && !busy
                    ? "button"
                    : "button secondary"
                }
                disabled={busy || actionItems.length === 0}
                onClick={() => requestApproval.mutate()}
              >
                <Send aria-hidden="true" />
                Proceed to Approval
              </button>
            </div>
          )}
        </>
      )}

      {isApprovalPhase && (
        <div className="confirmation-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Ready to create</p>
              <h2 className="section-title">Confirm these changes</h2>
              <p className="mt-2 text-sm text-muted">
                {notionCount === 0 &&
                  githubCount === 0 &&
                  `${pendingApprovals.length} ${pendingApprovals.length === 1 ? "change" : "changes"} will be created`}
                {notionCount > 0 &&
                  `${notionCount} ${notionCount === 1 ? "task" : "tasks"} will be added to Notion`}
                {notionCount > 0 && githubCount > 0 && ". "}
                {githubCount > 0 &&
                  `${githubCount} GitHub ${githubCount === 1 ? "issue or review" : "issues or reviews"} will be created`}
                .
              </p>
            </div>
            <button
              className="button"
              disabled={busy || pendingApprovals.length === 0}
              onClick={() => approveAll.mutate()}
            >
              <Check aria-hidden="true" />
              Confirm all
            </button>
          </div>
          <div className="mt-4 space-y-3">
            {data.approvals.map((approval) => (
              <div key={approval.id} className="confirmation-row">
                <div>
                  <p className="text-sm font-medium">
                    {String(
                      approval.original_payload.title ||
                        approval.original_payload.reviewer ||
                        "Action",
                    )}
                  </p>
                  <Status value={approval.status} />
                  <p className="mt-1 text-xs text-muted">
                    {typeof approval.original_payload.database_id === "string"
                      ? "Notion task"
                      : "GitHub issue or review"}
                  </p>
                </div>
                {approval.status === "PENDING" && (
                  <div className="flex gap-2">
                    <button
                      className="button secondary"
                      disabled={busy}
                      onClick={() => resolve.mutate(approval)}
                    >
                      <Check aria-hidden="true" />
                      Confirm
                    </button>
                    <button
                      className="button secondary"
                      disabled={busy}
                      onClick={() => reject.mutate(approval)}
                    >
                      <X aria-hidden="true" />
                      Reject
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {isExecutionPhase && (
        <div className="panel">
          <h2 className="section-title">Ready to create</h2>
          <p className="mt-2 text-sm text-muted">
            Your action items are confirmed. Relay will now create them in the
            selected tools.
          </p>
          <button
            className="button mt-5"
            disabled={busy}
            onClick={() => execute.mutate()}
          >
            <Send aria-hidden="true" />
            Confirm &amp; create
          </button>
        </div>
      )}

      {isCompletePhase && <ExecutionSummary data={data} />}
    </section>
  );
}

function CollaborateSummary({ data }: { data: CollaborateDetail }) {
  return (
    <section className="meeting-summary">
      <h2 className="section-title">Summary</h2>
      <p>{data.summary}</p>
      {data.unresolved_questions.length > 0 && (
        <div className="notice mt-4">
          <p className="font-medium">Unresolved questions</p>
          <ul className="mt-2 list-disc pl-5 text-sm">
            {data.unresolved_questions.map((question, index) => (
              <li key={index}>{question}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function DisclosurePanel({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details className="learn-disclosure" open={defaultOpen}>
      <summary>
        <span>{title}</span>
        <ChevronDown className="learn-disclosure-icon" aria-hidden="true" />
      </summary>
      <div className="mt-4">{children}</div>
    </details>
  );
}

function ActionItemCard({
  item,
  members,
  editable,
  onChange,
  onRemove,
}: {
  item: PlannedAction;
  members: ProjectMember[];
  editable: boolean;
  onChange: (patch: Partial<PlannedAction>) => void;
  onRemove: () => void;
}) {
  const toggleDestination = (destination: "notion" | "github") => {
    const has = item.destinations.includes(destination);
    onChange({
      destinations: has
        ? item.destinations.filter((d) => d !== destination)
        : [...item.destinations, destination],
    });
  };
  const memberName = members.find(
    (member) => member.id === item.member_id,
  )?.display_name;
  const owner = memberName || item.owner_name || "Unassigned";
  const needsOwner = ["ambiguous", "unresolved"].includes(item.identity_status);
  return (
    <details className="action-item-row">
      <summary>
        <span className="action-item-title">
          <strong>{item.title}</strong>
          {needsOwner && (
            <small className="needs-confirmation">Owner unclear</small>
          )}
        </span>
        <span>
          <small>Owner</small>
          {owner}
        </span>
        <span>
          <small>Due</small>
          {item.deadline_date
            ? new Date(`${item.deadline_date}T12:00:00`).toLocaleDateString(
                undefined,
                { month: "short", day: "numeric" },
              )
            : "No due date"}
        </span>
        <span>
          <small>Send to</small>
          {item.destinations.length
            ? item.destinations
                .map((value) => (value === "notion" ? "Notion" : "GitHub"))
                .join(" + ")
            : "Nowhere yet"}
        </span>
        <ChevronDown className="action-item-chevron" aria-hidden="true" />
      </summary>
      <div className="action-item-editor">
        <label className="field grow">
          Task
          <input
            disabled={!editable}
            value={item.title}
            onChange={(event) => onChange({ title: event.target.value })}
          />
        </label>
        <label className="field">
          Description
          <textarea
            disabled={!editable}
            rows={2}
            value={item.description}
            onChange={(event) => onChange({ description: event.target.value })}
          />
        </label>
        <div className="action-item-edit-grid">
          <label className="field">
            Owner
            {item.identity_status === "ambiguous" ? (
              <select
                disabled={!editable}
                value={item.member_id || ""}
                onChange={(event) =>
                  onChange({
                    member_id: event.target.value || null,
                    identity_status: "resolved",
                  })
                }
              >
                <option value="">Choose who this is</option>
                {item.identity_candidates.map((candidate) => (
                  <option key={candidate.id} value={candidate.id}>
                    {candidate.display_name}
                  </option>
                ))}
              </select>
            ) : (
              <select
                disabled={!editable}
                value={item.member_id || ""}
                onChange={(event) =>
                  onChange({
                    member_id: event.target.value || null,
                    identity_status: event.target.value
                      ? "resolved"
                      : "unresolved",
                  })
                }
              >
                <option value="">{item.owner_name || "Unassigned"}</option>
                {members.map((member) => (
                  <option key={member.id} value={member.id}>
                    {member.display_name}
                  </option>
                ))}
              </select>
            )}
          </label>
          <label className="field">
            Deadline
            <input
              type="date"
              disabled={!editable}
              value={item.deadline_date || ""}
              onChange={(event) =>
                onChange({ deadline_date: event.target.value || null })
              }
            />
          </label>
        </div>
        {item.category === "REVIEW_REQUEST" && (
          <p className="context-tag mt-3">
            {item.pull_request_number
              ? `Pull request #${item.pull_request_number}`
              : "No pull request identified -- this review request stays unresolved."}
          </p>
        )}
        <fieldset className="action-destinations">
          <legend>Send to</legend>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              disabled={!editable}
              checked={item.destinations.includes("notion")}
              onChange={() => toggleDestination("notion")}
            />
            Notion
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              disabled={
                !editable ||
                (item.category === "REVIEW_REQUEST" &&
                  !item.pull_request_number)
              }
              checked={item.destinations.includes("github")}
              onChange={() => toggleDestination("github")}
            />
            GitHub
          </label>
        </fieldset>
        {editable && (
          <button
            className="text-link danger-link"
            aria-label={`Remove ${item.title}`}
            onClick={onRemove}
          >
            <Trash2 aria-hidden="true" /> Remove task
          </button>
        )}
      </div>
    </details>
  );
}

function ExecutionSummary({ data }: { data: CollaborateDetail }) {
  const payload = data.run.result_payload as {
    results?: {
      status?: string;
      external_url?: string;
      action_type?: string;
    }[];
    succeeded_count?: number;
    failed_count?: number;
    total_count?: number;
  } | null;
  const succeeded = (payload?.results || []).filter(
    (item) => item.status === "succeeded",
  );
  const notionCreated = succeeded.filter((item) =>
    item.action_type?.toUpperCase().includes("NOTION"),
  ).length;
  const githubCreated = succeeded.filter((item) =>
    item.action_type?.toUpperCase().includes("GITHUB"),
  ).length;
  return (
    <div className="created-summary">
      <p className="eyebrow">Created</p>
      <h2 className="section-title">Your project tools are up to date</h2>
      <ul>
        {notionCreated > 0 && (
          <li>
            <Check aria-hidden="true" /> {notionCreated} Notion{" "}
            {notionCreated === 1 ? "task" : "tasks"}
          </li>
        )}
        {githubCreated > 0 && (
          <li>
            <Check aria-hidden="true" /> {githubCreated} GitHub{" "}
            {githubCreated === 1 ? "issue or review" : "issues or reviews"}
          </li>
        )}
        {notionCreated === 0 && githubCreated === 0 && (
          <li>
            <Check aria-hidden="true" /> {payload?.succeeded_count ?? 0} project{" "}
            {(payload?.succeeded_count ?? 0) === 1 ? "item" : "items"}
          </li>
        )}
      </ul>
      {(payload?.failed_count || 0) > 0 && (
        <p className="notice error mt-4">
          {payload?.succeeded_count ?? 0}{" "}
          {(payload?.succeeded_count ?? 0) === 1 ? "item was" : "items were"}{" "}
          created. {payload?.failed_count} could not be created.
        </p>
      )}
      <CompletionActions
        workflow="collaborate"
        actionLabel="Open created items"
        destinations={(payload?.results || [])
          .filter((item) => item.status === "succeeded")
          .map((item) => item.external_url)}
      />
    </div>
  );
}
