"use client";
import { ChangeEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  ChevronDown,
  FileText,
  Pencil,
  Play,
  Plus,
  RotateCcw,
  Save,
  Send,
  Upload,
  X,
} from "lucide-react";
import { approvals } from "@/features/approvals/api";
import { connections } from "@/features/connections/api";
import { learn, LectureSummary } from "@/features/learn/api";
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

function refsLabel(
  refs: { section_id: string; page: number | null }[] | undefined,
): string {
  if (!refs?.length) return "No source reference";
  return refs
    .map((ref) => `${ref.section_id}${ref.page ? `, p. ${ref.page}` : ""}`)
    .join(" | ");
}

function fileFromText(text: string) {
  return new File([text], "pasted-lecture-notes.txt", { type: "text/plain" });
}

export function LearnEntry() {
  const router = useRouter();
  const cache = useQueryClient();
  const config = useQuery({
    queryKey: ["learn", "config"],
    queryFn: learn.config,
  });
  const [file, setFile] = useState<File | null>(null);
  const [pasted, setPasted] = useState("");
  const create = useMutation({
    mutationFn: learn.create,
    onSuccess: async (run) => {
      const selected = file || fileFromText(pasted);
      await learn.upload(run.id, selected);
      await cache.invalidateQueries({ queryKey: ["runs"] });
      router.push(`/workflows/learn/${run.id}`);
    },
  });
  const maxSize = config.data?.max_upload_bytes;
  const chosenSize = file?.size || new Blob([pasted]).size;
  const tooLarge = Boolean(maxSize && chosenSize > maxSize);
  const canStart =
    Boolean(file || pasted.trim()) && !tooLarge && !create.isPending;

  return (
    <>
      <PageTitle
        eyebrow="LEARN"
        title="Turn lecture material into reviewed study notes."
        description="Upload PDF, DOCX, Markdown, or plain text. Relay parses it locally, generates a sourced summary, and waits for your approval before publishing to Notion."
        action={<WorkflowBadge workflow={workflowDisplay.lecture_to_notion} />}
      />
      <RelayLine
        sources={[{ label: "Lecture notes" }]}
        destinations={[{ label: "Notion" }]}
        status="DRAFT"
      />
      <section className="my-10 grid gap-6 lg:grid-cols-[1fr_0.8fr]">
        <div className="panel">
          <h2 className="section-title">Source document</h2>
          <label className="learn-drop">
            <Upload aria-hidden="true" />
            <span>
              {file ? file.name : "Choose a PDF, DOCX, Markdown, or text file"}
            </span>
            <input
              type="file"
              accept=".pdf,.docx,.md,.markdown,.txt,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(event: ChangeEvent<HTMLInputElement>) =>
                setFile(event.target.files?.[0] || null)
              }
            />
          </label>
          <label className="field mt-5">
            Paste lecture text
            <textarea
              rows={9}
              value={pasted}
              onChange={(event) => setPasted(event.target.value)}
              placeholder="Paste notes here when you do not have a file."
            />
          </label>
          <ErrorMessage error={create.error} />
          {tooLarge && (
            <div role="alert" className="notice error mt-4">
              <X aria-hidden="true" />
              <p>
                The selected source is larger than the configured upload limit.
              </p>
            </div>
          )}
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button
              className="button"
              disabled={!canStart}
              onClick={() => create.mutate()}
            >
              <Play aria-hidden="true" />
              {create.isPending ? "Creating..." : "Create LEARN run"}
            </button>
            <p className="text-sm text-muted">
              Provider: {config.data?.provider || "loading"}.
            </p>
          </div>
        </div>
        <div className="panel">
          <h2 className="section-title">What Relay will prepare</h2>
          <ol className="learn-steps">
            <li>Store the original file privately on this machine.</li>
            <li>Parse a structured document with pages and sections.</li>
            <li>Generate sourced notes with a typed model response.</li>
            <li>Save your approved payload before publishing.</li>
          </ol>
        </div>
      </section>
    </>
  );
}

export function LearnRun({ id }: { id: string }) {
  const cache = useQueryClient();
  const detail = useQuery({
    queryKey: ["learn", id],
    queryFn: () => learn.detail(id),
    refetchInterval: (query) =>
      query.state.data?.run.status === "ANALYZING" ||
      query.state.data?.run.status === "QUEUED" ||
      query.state.data?.run.status === "EXECUTING"
        ? 1500
        : false,
  });
  const artifact = useQuery({
    queryKey: ["learn", id, "artifact"],
    queryFn: () => learn.artifact(id),
    enabled: detail.data?.run.status === "COMPLETED",
  });
  const invalidate = async () => {
    await Promise.all([
      cache.invalidateQueries({ queryKey: ["learn", id] }),
      cache.invalidateQueries({ queryKey: ["runs"] }),
      cache.invalidateQueries({ queryKey: ["events", id] }),
      cache.invalidateQueries({ queryKey: ["approvals"] }),
      cache.invalidateQueries({ queryKey: ["connections"] }),
    ]);
  };
  const config = useQuery({
    queryKey: ["learn", "config"],
    queryFn: learn.config,
  });
  const notionConnections = useQuery({
    queryKey: ["connections"],
    queryFn: connections.list,
  });
  const refreshDestinations = useMutation({
    mutationFn: connections.refreshNotionDestinations,
    onSuccess: invalidate,
  });
  const syncDestination = useMutation({
    mutationFn: () => learn.destination(id),
    onSuccess: invalidate,
  });
  const parse = useMutation({
    mutationFn: () => learn.parse(id),
    onSuccess: invalidate,
  });
  const summarize = useMutation({
    mutationFn: () => learn.summarize(id),
    onSuccess: invalidate,
  });
  const save = useMutation({
    mutationFn: ({
      summary,
      expectedPayload,
    }: {
      summary: LectureSummary;
      expectedPayload: unknown;
    }) => learn.edit(id, summary, expectedPayload),
    onSuccess: invalidate,
  });
  const resolve = useMutation({
    mutationFn: ({ approve }: { approve: boolean }) => {
      const approval = detail.data?.approval;
      if (!approval) throw new Error("No approval is available.");
      return approvals.resolve(approval, approve);
    },
    onSuccess: invalidate,
  });
  const [file, setFile] = useState<File | null>(null);
  const [pasted, setPasted] = useState("");
  const upload = useMutation({
    mutationFn: async () => {
      const selected = file || fileFromText(pasted);
      return learn.upload(id, selected);
    },
    onSuccess: async () => {
      setFile(null);
      setPasted("");
      await invalidate();
    },
  });
  const execute = useMutation({
    mutationFn: () => learn.execute(id),
    onSuccess: invalidate,
  });
  if (detail.isPending) return <Loading />;
  if (detail.error) return <ErrorMessage error={detail.error} />;
  const data = detail.data;
  const pending = data.approval?.status === "PENDING";
  const backendWorking = data.stage === "summarizing";
  const busy =
    parse.isPending ||
    summarize.isPending ||
    save.isPending ||
    resolve.isPending ||
    upload.isPending ||
    execute.isPending ||
    refreshDestinations.isPending ||
    syncDestination.isPending;
  const notionConnection = notionConnections.data?.find(
    (item) => item.provider === "NOTION" && item.status === "CONNECTED",
  );
  const realPublish = config.data?.notion_publish_mode === "real";
  const hasDestination = Boolean(
    data.approval?.original_payload.parent_destination_id,
  );
  const maxSize = config.data?.max_upload_bytes;
  const chosenSize = file?.size || new Blob([pasted]).size;
  const tooLarge = Boolean(maxSize && chosenSize > maxSize);
  const canUpload =
    data.run.status === "DRAFT" &&
    !data.source &&
    Boolean(file || pasted.trim()) &&
    !tooLarge &&
    !busy;
  const nextStep = learnNextStep(data, busy || backendWorking, canUpload);

  return (
    <>
      <PageTitle
        eyebrow="LEARN run"
        title={data.summary?.title || data.source?.filename || "Lecture notes"}
        description="Review the source, generated notes, approval payload, and Notion publish result for this LEARN workflow."
        action={<Status value={data.run.status} />}
      />
      <RelayLine
        sources={[{ label: data.source?.filename || "Lecture notes" }]}
        destinations={[{ label: "Notion" }]}
        status={data.run.status}
      />
      <NextStepNotice {...nextStep} />
      <ErrorMessage
        error={
          (backendWorking ? null : parse.error) ||
          (backendWorking ? null : summarize.error) ||
          save.error ||
          resolve.error ||
          upload.error ||
          execute.error ||
          refreshDestinations.error ||
          syncDestination.error ||
          notionConnections.error
        }
      />
      {data.run.error_message && (
        <div className="notice error my-6">
          <X aria-hidden="true" />
          <p>{data.run.error_message}</p>
        </div>
      )}
      <section className="my-8 grid gap-5 lg:grid-cols-3">
        <SourcePanel
          detail={data}
          file={file}
          pasted={pasted}
          tooLarge={tooLarge}
          canUpload={canUpload}
          uploading={upload.isPending}
          setFile={setFile}
          setPasted={setPasted}
          upload={() => upload.mutate()}
        />
        <ProcessingPanel
          detail={data}
          busy={busy}
          parse={() => parse.mutate()}
          summarize={() => summarize.mutate()}
        />
        <ApprovalPanel
          detail={data}
          busy={busy}
          realPublish={realPublish}
          hasDestination={hasDestination}
          connectionName={notionConnection?.display_name}
          refreshDestinations={() => refreshDestinations.mutate()}
          syncDestination={() => syncDestination.mutate()}
          reject={() => resolve.mutate({ approve: false })}
          execute={() => execute.mutate()}
        />
      </section>
      {data.summary ? (
        <SummaryReview
          key={JSON.stringify(data.summary)}
          summary={data.summary}
          pending={pending}
          busy={busy}
          approvalPayload={data.approval?.original_payload}
          realPublish={realPublish}
          hasDestination={hasDestination}
          approve={() => resolve.mutate({ approve: true })}
          onSave={(summary, expectedPayload) =>
            save.mutate({ summary, expectedPayload })
          }
        />
      ) : (
        <Empty title="No generated notes yet.">
          Parse and summarize the uploaded source to review the proposed study
          page.
        </Empty>
      )}
      {data.run.status === "COMPLETED" && (
        <section className="panel mt-8">
          <h2 className="section-title">
            {artifact.data?.external_url.startsWith("mock://")
              ? "Mock Notion artifact"
              : "Relayed to Notion"}
          </h2>
          {artifact.isPending ? (
            <Loading label="Loading published artifact" />
          ) : artifact.error ? (
            <ErrorMessage error={artifact.error} />
          ) : (
            <div className="learn-result">
              <p className="font-medium">{artifact.data?.external_id}</p>
              <p className="text-sm text-muted">
                {artifact.data?.external_url}
              </p>
              <p className="mt-3 text-sm">
                Created{" "}
                {new Date(artifact.data?.created_at || "").toLocaleString()}
              </p>
              {artifact.data?.external_url.startsWith("https://") && (
                <a
                  className="button mt-5"
                  href={artifact.data.external_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open in Notion
                </a>
              )}
            </div>
          )}
          <div className="mt-5 flex flex-wrap gap-3">
            <Link className="button secondary" href="/dashboard">
              Dashboard
            </Link>
            <Link className="button secondary" href="/workflows/learn">
              Start another
            </Link>
          </div>
        </section>
      )}
    </>
  );
}

function learnNextStep(
  detail: Awaited<ReturnType<typeof learn.detail>>,
  busy: boolean,
  canUpload: boolean,
) {
  if (busy || detail.stage === "summarizing") {
    return {
      title: "Relay is working on this step.",
      description:
        detail.stage === "summarizing"
          ? "OpenAI is generating your study-page draft. This can take a minute for longer PDFs."
          : "Wait for the current action to finish before moving on.",
    };
  }
  if (canUpload || (detail.run.status === "DRAFT" && !detail.source)) {
    return {
      title: "Next: upload lecture notes.",
      description:
        "Use the Source card below to upload a file or paste text into this draft.",
    };
  }
  if (detail.run.status === "DRAFT" && detail.source) {
    return {
      title: "Next: parse the source.",
      description:
        "Relay will read the uploaded document and break it into page-aware sections.",
    };
  }
  if (detail.run.status === "ANALYZING" && detail.source?.status === "PARSED") {
    return {
      title: "Next: summarize the parsed source.",
      description:
        detail.provider === "fake"
          ? "Local fake mode creates a demo draft from parsed text, so it may repeat headings instead of writing polished notes."
          : "Relay will generate a sourced study-page draft for review.",
    };
  }
  if (detail.approval?.status === "PENDING") {
    return {
      title: "Next: review and approve the study page.",
      description:
        "Edit anything that looks wrong, save changes if needed, then approve the exact payload before publishing.",
    };
  }
  if (detail.run.status === "APPROVED") {
    return {
      title: "Next: publish to Notion.",
      description:
        "The payload is approved and ready to send to your selected Notion destination.",
    };
  }
  return {
    title: "Workflow status updated.",
    description:
      "Relay will show the next available action as the run progresses.",
  };
}

function NextStepNotice({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  const working = title.startsWith("Relay is working");
  return (
    <div className={`notice next-step my-6 ${working ? "working" : ""}`}>
      <div>
        <p className="font-medium">{title}</p>
        <p className="mt-1">{description}</p>
      </div>
    </div>
  );
}

function SummaryReview({
  summary,
  pending,
  busy,
  approvalPayload,
  realPublish,
  hasDestination,
  approve,
  onSave,
}: {
  summary: LectureSummary;
  pending: boolean;
  busy: boolean;
  approvalPayload: unknown;
  realPublish: boolean;
  hasDestination: boolean;
  approve: () => void;
  onSave: (summary: LectureSummary, expectedPayload: unknown) => void;
}) {
  const [draft, setDraft] = useState(summary);
  const [editing, setEditing] = useState(false);
  const dirty = JSON.stringify(draft) !== JSON.stringify(summary);
  return (
    <SummaryEditor
      value={draft}
      onChange={setDraft}
      disabled={!pending || busy}
      editing={editing}
      setEditing={setEditing}
      onSave={() => {
        if (!approvalPayload) return;
        onSave(draft, approvalPayload);
        setEditing(false);
      }}
      onReset={() => {
        setDraft(summary);
        setEditing(false);
      }}
      canSave={Boolean(pending && dirty && approvalPayload) && !busy}
      canApprove={
        pending && !dirty && (!realPublish || hasDestination) && !busy
      }
      onApprove={approve}
    />
  );
}

function SourcePanel({
  detail,
  file,
  pasted,
  tooLarge,
  canUpload,
  uploading,
  setFile,
  setPasted,
  upload,
}: {
  detail: Awaited<ReturnType<typeof learn.detail>>;
  file: File | null;
  pasted: string;
  tooLarge: boolean;
  canUpload: boolean;
  uploading: boolean;
  setFile: (file: File | null) => void;
  setPasted: (text: string) => void;
  upload: () => void;
}) {
  return (
    <article className="panel">
      <h2 className="section-title">Source</h2>
      {detail.source ? (
        <div className="space-y-3 text-sm">
          <p className="font-medium">{detail.source.filename}</p>
          <p className="text-muted">
            {(detail.source.size_bytes / 1024).toFixed(1)} KB |{" "}
            {detail.source.content_type}
          </p>
          <Status value={detail.source.status} />
          <p className="text-muted">
            {detail.source.sections.length} sections parsed
            {detail.source.metadata?.page_count
              ? ` across ${detail.source.metadata.page_count} pages`
              : ""}
            .
          </p>
        </div>
      ) : detail.run.status === "DRAFT" ? (
        <div className="space-y-4">
          <p className="text-sm text-muted">
            Upload a lecture document or paste notes to continue this draft.
          </p>
          <label className="learn-drop compact">
            <Upload aria-hidden="true" />
            <span>
              {file ? file.name : "Choose PDF, DOCX, Markdown, or text"}
            </span>
            <input
              type="file"
              accept=".pdf,.docx,.md,.markdown,.txt,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(event: ChangeEvent<HTMLInputElement>) =>
                setFile(event.target.files?.[0] || null)
              }
            />
          </label>
          <label className="field">
            Paste lecture text
            <textarea
              rows={5}
              value={pasted}
              onChange={(event) => setPasted(event.target.value)}
              placeholder="Paste notes here when you do not have a file."
            />
          </label>
          {tooLarge && (
            <p className="text-sm text-danger">
              This source is larger than the configured upload limit.
            </p>
          )}
          <button className="button" disabled={!canUpload} onClick={upload}>
            <Upload aria-hidden="true" />
            {uploading ? "Uploading..." : "Upload source"}
          </button>
        </div>
      ) : (
        <p className="text-sm text-muted">No source has been uploaded.</p>
      )}
    </article>
  );
}

function ProcessingPanel({
  detail,
  busy,
  parse,
  summarize,
}: {
  detail: Awaited<ReturnType<typeof learn.detail>>;
  busy: boolean;
  parse: () => void;
  summarize: () => void;
}) {
  const canParse = detail.run.status === "DRAFT" && detail.source;
  const summarizing = detail.stage === "summarizing";
  const canSummarize =
    detail.run.status === "ANALYZING" &&
    detail.source?.status === "PARSED" &&
    !summarizing;
  return (
    <article className="panel">
      <h2 className="section-title">Processing</h2>
      <p className="text-sm text-muted">
        Provider: {detail.provider}
        {detail.stage ? ` | ${detail.stage}` : ""}
      </p>
      <div className="mt-5 flex flex-wrap gap-3">
        <button
          className={canParse && !busy ? "button" : "button secondary"}
          disabled={!canParse || busy}
          onClick={parse}
        >
          <FileText aria-hidden="true" />
          Parse
        </button>
        <button
          className={canSummarize && !busy ? "button" : "button secondary"}
          disabled={!canSummarize || busy}
          onClick={summarize}
        >
          <RotateCcw aria-hidden="true" />
          Summarize
        </button>
      </div>
    </article>
  );
}

function ApprovalPanel({
  detail,
  busy,
  realPublish,
  hasDestination,
  connectionName,
  refreshDestinations,
  syncDestination,
  reject,
  execute,
}: {
  detail: Awaited<ReturnType<typeof learn.detail>>;
  busy: boolean;
  realPublish: boolean;
  hasDestination: boolean;
  connectionName?: string;
  refreshDestinations: () => void;
  syncDestination: () => void;
  reject: () => void;
  execute: () => void;
}) {
  const pending = detail.approval?.status === "PENDING";
  const payload = detail.approval?.original_payload;
  return (
    <article className="panel">
      <h2 className="section-title">Destination</h2>
      <p className="text-sm font-medium">
        {String(payload?.workspace_name || connectionName || "Notion")}
      </p>
      <p className="mt-2 text-sm text-muted">
        {String(payload?.parent_destination_title || "No destination selected")}
      </p>
      {realPublish && pending && !hasDestination && (
        <div className="notice mt-4">
          <p>
            Connect Notion and choose a default destination before approval.
          </p>
        </div>
      )}
      {pending && (
        <div className="mt-5 flex flex-wrap gap-3">
          <Link className="button secondary" href="/connections">
            Connections
          </Link>
          <button
            className="button secondary"
            disabled={busy}
            onClick={refreshDestinations}
          >
            Refresh pages
          </button>
          <button
            className="button secondary"
            disabled={busy}
            onClick={syncDestination}
          >
            Use default
          </button>
        </div>
      )}
      <h2 className="section-title mt-8">Approval</h2>
      {detail.approval ? <Status value={detail.approval.status} /> : null}
      {pending && (
        <div className="mt-5 flex flex-wrap gap-3">
          <button className="button secondary" disabled={busy} onClick={reject}>
            <X aria-hidden="true" />
            Reject
          </button>
        </div>
      )}
      {detail.run.status === "APPROVED" && (
        <button className="button mt-5" disabled={busy} onClick={execute}>
          <Send aria-hidden="true" />
          Publish to Notion
        </button>
      )}
    </article>
  );
}

function SummaryEditor({
  value,
  onChange,
  disabled,
  editing,
  setEditing,
  onSave,
  onReset,
  canSave,
  canApprove,
  onApprove,
}: {
  value: LectureSummary;
  onChange: (value: LectureSummary) => void;
  disabled: boolean;
  editing: boolean;
  setEditing: (editing: boolean) => void;
  onSave: () => void;
  onReset: () => void;
  canSave: boolean;
  canApprove: boolean;
  onApprove: () => void;
}) {
  const set = <K extends keyof LectureSummary>(
    key: K,
    next: LectureSummary[K],
  ) => onChange({ ...value, [key]: next });
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <h2 className="section-title">Study page draft</h2>
          <p className="text-sm text-muted">
            Review this as one study document. Switch to edit mode only if you
            need to adjust the generated notes before approval.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          {editing ? (
            <>
              <button
                className="button secondary"
                disabled={disabled}
                onClick={onReset}
              >
                <RotateCcw aria-hidden="true" />
                Reset
              </button>
              <button
                className={canSave ? "button" : "button secondary"}
                disabled={!canSave}
                onClick={onSave}
              >
                <Save aria-hidden="true" />
                Save notes
              </button>
            </>
          ) : (
            <button
              className="button secondary"
              disabled={disabled}
              onClick={() => setEditing(true)}
            >
              <Pencil aria-hidden="true" />
              Edit notes
            </button>
          )}
          <button
            className={canApprove ? "button" : "button secondary"}
            disabled={!canApprove}
            onClick={onApprove}
          >
            <Check aria-hidden="true" />
            Approve
          </button>
        </div>
      </div>
      {editing ? (
        <div className="grid gap-5">
          <label className="field">
            Title
            <input
              disabled={disabled}
              value={value.title}
              onChange={(event) => set("title", event.target.value)}
            />
          </label>
          <label className="field">
            Overview
            <textarea
              disabled={disabled}
              rows={5}
              value={value.overview}
              onChange={(event) => set("overview", event.target.value)}
            />
          </label>
          <TextList
            title="Takeaways"
            values={value.takeaways}
            disabled={disabled}
            collapsible
            onChange={(items) => set("takeaways", items)}
          />
          <TextList
            title="Review questions"
            values={value.review_questions}
            disabled={disabled}
            collapsible
            onChange={(items) => set("review_questions", items)}
          />
          <PairList
            title="Key concepts"
            values={value.key_concepts}
            first="name"
            second="explanation"
            disabled={disabled}
            collapsible
            onChange={(items) => set("key_concepts", items)}
          />
          <PairList
            title="Study notes"
            values={value.sections}
            first="heading"
            second="text"
            disabled={disabled}
            collapsible
            onChange={(items) => set("sections", items)}
          />
          <PairList
            title="Definitions"
            values={value.definitions}
            first="term"
            second="definition"
            disabled={disabled}
            collapsible
            onChange={(items) => set("definitions", items)}
          />
          <PairList
            title="Examples"
            values={value.examples}
            first="title"
            second="explanation"
            disabled={disabled}
            collapsible
            onChange={(items) => set("examples", items)}
          />
        </div>
      ) : (
        <StudyPagePreview summary={value} />
      )}
    </section>
  );
}

function StudyPagePreview({ summary }: { summary: LectureSummary }) {
  return (
    <article className="study-document">
      <header>
        <h1>{summary.title}</h1>
        <p>{summary.overview}</p>
      </header>
      {summary.sections.length > 0 && (
        <section>
          <h2>Study notes</h2>
          {summary.sections.map((section, index) => (
            <div className="study-document-section" key={index}>
              <h3>{section.heading}</h3>
              <p>{section.text}</p>
              <p className="context-tag">{refsLabel(section.source_refs)}</p>
            </div>
          ))}
        </section>
      )}
      {summary.key_concepts.length > 0 && (
        <section>
          <h2>Key concepts</h2>
          <dl className="study-document-list">
            {summary.key_concepts.map((concept, index) => (
              <div key={index}>
                <dt>{concept.name}</dt>
                <dd>{concept.explanation}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}
      {summary.definitions.length > 0 && (
        <section>
          <h2>Definitions</h2>
          <dl className="study-document-list">
            {summary.definitions.map((definition, index) => (
              <div key={index}>
                <dt>{definition.term}</dt>
                <dd>{definition.definition}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}
      {summary.examples.length > 0 && (
        <section>
          <h2>Examples</h2>
          {summary.examples.map((example, index) => (
            <div className="study-document-section" key={index}>
              <h3>{example.title}</h3>
              <p>{example.explanation}</p>
              <p className="context-tag">{refsLabel(example.source_refs)}</p>
            </div>
          ))}
        </section>
      )}
      {summary.takeaways.length > 0 && (
        <section>
          <h2>Takeaways</h2>
          <ul>
            {summary.takeaways.map((takeaway, index) => (
              <li key={index}>{takeaway}</li>
            ))}
          </ul>
        </section>
      )}
      {summary.review_questions.length > 0 && (
        <section>
          <h2>Review questions</h2>
          <ol>
            {summary.review_questions.map((question, index) => (
              <li key={index}>{question}</li>
            ))}
          </ol>
        </section>
      )}
    </article>
  );
}

function TextList({
  title,
  values,
  disabled,
  collapsible = false,
  onChange,
}: {
  title: string;
  values: string[];
  disabled: boolean;
  collapsible?: boolean;
  onChange: (values: string[]) => void;
}) {
  const content = (
    <>
      <div className="section-heading">
        {!collapsible && <h3 className="section-title">{title}</h3>}
        <button
          className="button secondary"
          disabled={disabled}
          onClick={() => onChange([...values, ""])}
        >
          <Plus aria-hidden="true" />
          Add
        </button>
      </div>
      <div className="grid gap-3">
        {values.map((item, index) => (
          <div className="learn-row" key={index}>
            <textarea
              disabled={disabled}
              rows={2}
              value={item}
              onChange={(event) =>
                onChange(
                  values.map((value, i) =>
                    i === index ? event.target.value : value,
                  ),
                )
              }
            />
            <button
              aria-label={`Remove ${title} ${index + 1}`}
              className="button secondary"
              disabled={disabled}
              onClick={() => onChange(values.filter((_, i) => i !== index))}
            >
              <X aria-hidden="true" />
            </button>
          </div>
        ))}
      </div>
    </>
  );

  if (collapsible) {
    return (
      <details className="learn-disclosure">
        <summary>
          <span>{title}</span>
          <ChevronDown className="learn-disclosure-icon" aria-hidden="true" />
        </summary>
        <div className="mt-4">{content}</div>
      </details>
    );
  }

  return <div>{content}</div>;
}

function labelFor(field: string) {
  return field
    .replaceAll("_", " ")
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function PairList<
  T extends Record<string, unknown> & {
    source_refs?: LectureSummary["sections"][number]["source_refs"];
  },
>({
  title,
  values,
  first,
  second,
  disabled,
  collapsible = false,
  onChange,
}: {
  title: string;
  values: T[];
  first: keyof T & string;
  second: keyof T & string;
  disabled: boolean;
  collapsible?: boolean;
  onChange: (values: T[]) => void;
}) {
  const content = (
    <div className="grid gap-4">
      {values.map((item, index) => (
        <article className="learn-card" key={index}>
          <label className="field">
            {labelFor(first)}
            <input
              disabled={disabled}
              value={String(item[first] || "")}
              onChange={(event) =>
                onChange(
                  values.map((value, i) =>
                    i === index
                      ? ({ ...value, [first]: event.target.value } as T)
                      : value,
                  ),
                )
              }
            />
          </label>
          <label className="field">
            {labelFor(second)}
            <textarea
              disabled={disabled}
              rows={3}
              value={String(item[second] || "")}
              onChange={(event) =>
                onChange(
                  values.map((value, i) =>
                    i === index
                      ? ({ ...value, [second]: event.target.value } as T)
                      : value,
                  ),
                )
              }
            />
          </label>
          <p className="context-tag">{refsLabel(item.source_refs)}</p>
        </article>
      ))}
    </div>
  );

  if (collapsible) {
    return (
      <details className="learn-disclosure">
        <summary>
          <span>{title}</span>
          <ChevronDown className="learn-disclosure-icon" aria-hidden="true" />
        </summary>
        <div className="mt-4">{content}</div>
      </details>
    );
  }

  return (
    <div>
      <h3 className="section-title">{title}</h3>
      {content}
    </div>
  );
}
