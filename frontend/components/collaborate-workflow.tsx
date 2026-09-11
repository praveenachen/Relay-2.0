"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Play, Plus, Send, Trash2, Upload, X } from "lucide-react";
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
import { RelayLine } from "@/components/relay-line";
import {
  Empty,
  ErrorMessage,
  Loading,
  PageTitle,
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
        eyebrow="COLLABORATE"
        title="Turn a meeting into accountable work."
        description="Relay extracts decisions and action items from a transcript, resolves owners against your project's real members, and proposes typed Notion and GitHub actions you approve before anything is created."
        action={<WorkflowBadge workflow={workflowDisplay.project_meeting} />}
      />
      <RelayLine
        sources={[{ label: "Meeting transcript" }]}
        destinations={[{ label: "Notion" }, { label: "GitHub" }]}
        status="DRAFT"
      />
      <section className="panel my-8">
        <h2 className="section-title">Choose a project</h2>
        <p className="text-sm text-muted">
          A project remembers your team&apos;s members, Notion task database,
          and GitHub repository so Relay never has to guess them from a
          transcript.
        </p>
        {projectsQuery.isPending ? (
          <Loading />
        ) : (
          <>
            <ErrorMessage error={projectsQuery.error} />
            {projectsQuery.data && projectsQuery.data.length > 0 && (
              <div className="mt-5 flex flex-wrap items-center gap-3">
                <select
                  className="min-h-11 rounded-md border border-line bg-surface px-3 text-sm"
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
  const notionDatabases = useQuery({
    queryKey: ["connections", "notion-task-databases"],
    queryFn: connections.notionTaskDatabases,
  });
  const githubRepos = useQuery({
    queryKey: ["connections", "github-repositories"],
    queryFn: connections.githubRepositories,
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

  const hasNotion = (connectionsQuery.data || []).some(
    (item) => item.provider === "NOTION" && item.status === "CONNECTED",
  );
  const hasGithub = (connectionsQuery.data || []).some(
    (item) => item.provider === "GITHUB" && item.status === "CONNECTED",
  );
  const repo = (githubRepos.data || []).find(
    (item) => item.full_name === repoFullName,
  );

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
        github_repository_owner: repo?.owner || null,
        github_repository_name: repo?.name || null,
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
            <select
              value={notionDatabaseId}
              onChange={(event) => setNotionDatabaseId(event.target.value)}
            >
              <option value="">None</option>
              {(notionDatabases.data || []).map((database) => (
                <option key={database.id} value={database.id}>
                  {database.title}
                </option>
              ))}
            </select>
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
            <select
              value={repoFullName}
              onChange={(event) => setRepoFullName(event.target.value)}
            >
              <option value="">None</option>
              {(githubRepos.data || []).map((item) => (
                <option key={item.full_name} value={item.full_name}>
                  {item.full_name}
                </option>
              ))}
            </select>
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

  return (
    <>
      <PageTitle
        eyebrow="COLLABORATE run"
        title={data.project?.name || "Meeting"}
        description="Review the transcript analysis, resolve owners and destinations, and approve before Relay touches Notion or GitHub."
        action={<Status value={data.run.status} />}
      />
      <RelayLine
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
      {data.run.status === "DRAFT" ? (
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
      title: "Relay is working on this step.",
      description: "Wait for the current action to finish before moving on.",
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
      title: "Next: extract transcript segments.",
      description:
        "Relay will split the transcript into structured segments before analysis.",
    };
  }
  return {
    title: "Next: analyze the meeting.",
    description:
      "Relay will identify decisions, owners, deadlines, and proposed Notion or GitHub work.",
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
      title: "Relay is working on this step.",
      description: "Wait for the current action to finish before moving on.",
    };
  }
  if (data.run.status === "PLAN_READY") {
    return {
      title: hasUnsavedEdits
        ? "Next: save your action-item edits."
        : "Next: request approval for project actions.",
      description: hasUnsavedEdits
        ? "Save the edited owners, deadlines, or destinations before asking for approval."
        : actionCount
          ? "Review the extracted action items, then request approval when they look right."
          : "Relay did not find action items to approve in this transcript.",
    };
  }
  if (data.approvals.some((approval) => approval.status === "PENDING")) {
    return {
      title: "Next: approve or reject each action.",
      description:
        "Approval is the final checkpoint before Relay writes to Notion or GitHub.",
    };
  }
  if (data.run.status === "APPROVED") {
    return {
      title: "Next: create approved project work.",
      description:
        "Send the approved action items to their selected destinations.",
    };
  }
  return {
    title: "Workflow status updated.",
    description:
      "Relay will show the next available action as the collaboration workflow progresses.",
  };
}

function NextStepNotice({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="notice next-step my-6">
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
            Extract segments
          </button>
        )}
        {(data.stage === "transcript_ready" ||
          data.run.status === "ANALYZING") && (
          <button
            className="button"
            disabled={busy || data.run.status === "ANALYZING"}
            onClick={() => analyze.mutate()}
          >
            <Play aria-hidden="true" />
            {data.run.status === "ANALYZING"
              ? "Analyzing..."
              : "Analyze meeting"}
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
  const execute = useMutation({
    mutationFn: () => collaborate.execute(id),
    onSuccess: invalidate,
  });

  const busy =
    save.isPending ||
    requestApproval.isPending ||
    resolve.isPending ||
    reject.isPending ||
    execute.isPending;
  const canEdit = data.run.status === "PLAN_READY";
  const members = membersQuery.data || [];

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
          execute.error
        }
      />
      {data.summary && (
        <div className="panel">
          <h2 className="section-title">Summary</h2>
          <p className="text-sm">{data.summary}</p>
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
        </div>
      )}

      {data.decisions.length > 0 && (
        <div className="panel">
          <h2 className="section-title">Decisions</h2>
          <div className="mt-4 space-y-3">
            {data.decisions.map((decision, index) => (
              <article key={index} className="learn-card">
                <p className="font-medium">{decision.title}</p>
                <p className="mt-2 text-sm text-muted">
                  {decision.description}
                </p>
              </article>
            ))}
          </div>
        </div>
      )}

      <div className="panel">
        <h2 className="section-title">Action items</h2>
        {actionItems.length === 0 ? (
          <Empty title="No action items were extracted.">
            Relay found decisions but no clear owner commitments in this
            transcript.
          </Empty>
        ) : (
          <div className="mt-4 space-y-4">
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
              Request approval
            </button>
          </div>
        )}
      </div>

      {data.approvals.length > 0 && (
        <div className="panel">
          <h2 className="section-title">Approvals</h2>
          <div className="mt-4 space-y-3">
            {data.approvals.map((approval) => (
              <div
                key={approval.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-line px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium">
                    {String(
                      approval.original_payload.title ||
                        approval.original_payload.reviewer ||
                        "Action",
                    )}
                  </p>
                  <Status value={approval.status} />
                </div>
                {approval.status === "PENDING" && (
                  <div className="flex gap-2">
                    <button
                      className="button"
                      disabled={busy}
                      onClick={() => resolve.mutate(approval)}
                    >
                      <Check aria-hidden="true" />
                      Approve
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
          {data.run.status === "APPROVED" && (
            <button
              className="button mt-5"
              disabled={busy}
              onClick={() => execute.mutate()}
            >
              <Send aria-hidden="true" />
              Create approved Notion and GitHub work
            </button>
          )}
        </div>
      )}

      {(data.run.status === "COMPLETED" ||
        data.run.status === "PARTIALLY_COMPLETED") && (
        <ExecutionSummary data={data} />
      )}
    </section>
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
  return (
    <article className="learn-card">
      <div className="section-heading">
        <label className="field grow">
          Title
          <input
            disabled={!editable}
            value={item.title}
            onChange={(event) => onChange({ title: event.target.value })}
          />
        </label>
        {editable && (
          <button
            className="button secondary"
            aria-label={`Remove ${item.title}`}
            onClick={onRemove}
          >
            <Trash2 aria-hidden="true" />
          </button>
        )}
      </div>
      <p className="mt-2 text-xs text-muted">
        {item.category.replaceAll("_", " ")} - confidence {item.confidence}
      </p>
      <label className="field mt-3">
        Description
        <textarea
          disabled={!editable}
          rows={2}
          value={item.description}
          onChange={(event) => onChange({ description: event.target.value })}
        />
      </label>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
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
      <div className="mt-3 flex flex-wrap gap-4 text-sm">
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
              (item.category === "REVIEW_REQUEST" && !item.pull_request_number)
            }
            checked={item.destinations.includes("github")}
            onChange={() => toggleDestination("github")}
          />
          GitHub
        </label>
      </div>
    </article>
  );
}

function ExecutionSummary({ data }: { data: CollaborateDetail }) {
  const payload = data.run.result_payload as {
    succeeded_count?: number;
    failed_count?: number;
    total_count?: number;
  } | null;
  return (
    <div className="panel">
      <h2 className="section-title">Result</h2>
      <p className="text-sm">
        {payload?.succeeded_count ?? 0} of {payload?.total_count ?? 0} approved
        actions completed
        {payload?.failed_count ? `, ${payload.failed_count} failed` : ""}.
      </p>
      <div className="mt-5 flex flex-wrap gap-3">
        <Link className="button secondary" href="/dashboard">
          Dashboard
        </Link>
        <Link className="button secondary" href="/workflows/collaborate">
          Start another
        </Link>
      </div>
    </div>
  );
}
