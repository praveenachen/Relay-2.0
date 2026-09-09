"use client";
import { ChangeEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  FileText,
  Play,
  Plus,
  RotateCcw,
  Save,
  Send,
  Upload,
  X,
} from "lucide-react";
import { approvals } from "@/features/approvals/api";
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
        description="Upload PDF, DOCX, Markdown, or plain text. Relay parses it locally, generates a sourced summary, and waits for your approval before the mock Notion publish."
        action={<WorkflowBadge workflow={workflowDisplay.lecture_to_notion} />}
      />
      <RelayLine
        sources={[{ label: "Lecture notes" }]}
        destinations={[{ label: "Mock Notion" }]}
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
            <li>Save your approved payload before mock publishing.</li>
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
    ]);
  };
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
  const execute = useMutation({
    mutationFn: () => learn.execute(id),
    onSuccess: invalidate,
  });
  if (detail.isPending) return <Loading />;
  if (detail.error) return <ErrorMessage error={detail.error} />;
  const data = detail.data;
  const pending = data.approval?.status === "PENDING";
  const busy =
    parse.isPending ||
    summarize.isPending ||
    save.isPending ||
    resolve.isPending ||
    execute.isPending;

  return (
    <>
      <PageTitle
        eyebrow="LEARN run"
        title={data.summary?.title || data.source?.filename || "Lecture notes"}
        description="Review the source, generated notes, approval payload, and mock publish result for this LEARN workflow."
        action={<Status value={data.run.status} />}
      />
      <RelayLine
        sources={[{ label: data.source?.filename || "Lecture notes" }]}
        destinations={[{ label: "Mock Notion" }]}
        status={data.run.status}
      />
      <ErrorMessage
        error={
          parse.error ||
          summarize.error ||
          save.error ||
          resolve.error ||
          execute.error
        }
      />
      {data.run.error_message && (
        <div className="notice error my-6">
          <X aria-hidden="true" />
          <p>{data.run.error_message}</p>
        </div>
      )}
      <section className="my-8 grid gap-5 lg:grid-cols-3">
        <SourcePanel detail={data} />
        <ProcessingPanel
          detail={data}
          busy={busy}
          parse={() => parse.mutate()}
          summarize={() => summarize.mutate()}
        />
        <ApprovalPanel
          detail={data}
          dirty={false}
          busy={busy}
          approve={() => resolve.mutate({ approve: true })}
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
          <h2 className="section-title">Mock Notion artifact</h2>
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

function SummaryReview({
  summary,
  pending,
  busy,
  approvalPayload,
  onSave,
}: {
  summary: LectureSummary;
  pending: boolean;
  busy: boolean;
  approvalPayload: unknown;
  onSave: (summary: LectureSummary, expectedPayload: unknown) => void;
}) {
  const [draft, setDraft] = useState(summary);
  const dirty = JSON.stringify(draft) !== JSON.stringify(summary);
  return (
    <SummaryEditor
      value={draft}
      onChange={setDraft}
      disabled={!pending || busy}
      onSave={() => approvalPayload && onSave(draft, approvalPayload)}
      onReset={() => setDraft(summary)}
      canSave={Boolean(pending && dirty && approvalPayload) && !busy}
    />
  );
}

function SourcePanel({
  detail,
}: {
  detail: Awaited<ReturnType<typeof learn.detail>>;
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
  const canSummarize =
    detail.run.status === "ANALYZING" && detail.source?.status === "PARSED";
  return (
    <article className="panel">
      <h2 className="section-title">Processing</h2>
      <p className="text-sm text-muted">
        Provider: {detail.provider}
        {detail.stage ? ` | ${detail.stage}` : ""}
      </p>
      <div className="mt-5 flex flex-wrap gap-3">
        <button
          className="button secondary"
          disabled={!canParse || busy}
          onClick={parse}
        >
          <FileText aria-hidden="true" />
          Parse
        </button>
        <button
          className="button secondary"
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
  dirty,
  busy,
  approve,
  reject,
  execute,
}: {
  detail: Awaited<ReturnType<typeof learn.detail>>;
  dirty: boolean;
  busy: boolean;
  approve: () => void;
  reject: () => void;
  execute: () => void;
}) {
  const pending = detail.approval?.status === "PENDING";
  return (
    <article className="panel">
      <h2 className="section-title">Approval</h2>
      {detail.approval ? <Status value={detail.approval.status} /> : null}
      {pending && (
        <div className="mt-5 flex flex-wrap gap-3">
          <button
            className="button"
            disabled={busy || dirty}
            onClick={approve}
            title={dirty ? "Save the edited notes before approval" : "Approve"}
          >
            <Check aria-hidden="true" />
            Approve
          </button>
          <button className="button secondary" disabled={busy} onClick={reject}>
            <X aria-hidden="true" />
            Reject
          </button>
        </div>
      )}
      {detail.run.status === "APPROVED" && (
        <button className="button mt-5" disabled={busy} onClick={execute}>
          <Send aria-hidden="true" />
          Publish mock page
        </button>
      )}
    </article>
  );
}

function SummaryEditor({
  value,
  onChange,
  disabled,
  onSave,
  onReset,
  canSave,
}: {
  value: LectureSummary;
  onChange: (value: LectureSummary) => void;
  disabled: boolean;
  onSave: () => void;
  onReset: () => void;
  canSave: boolean;
}) {
  const set = <K extends keyof LectureSummary>(
    key: K,
    next: LectureSummary[K],
  ) => onChange({ ...value, [key]: next });
  return (
    <section className="panel">
      <div className="section-heading">
        <h2 className="section-title">Study page draft</h2>
        <div className="flex flex-wrap gap-3">
          <button
            className="button secondary"
            disabled={disabled}
            onClick={onReset}
          >
            <RotateCcw aria-hidden="true" />
            Reset
          </button>
          <button className="button" disabled={!canSave} onClick={onSave}>
            <Save aria-hidden="true" />
            Save notes
          </button>
        </div>
      </div>
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
          onChange={(items) => set("takeaways", items)}
        />
        <TextList
          title="Review questions"
          values={value.review_questions}
          disabled={disabled}
          onChange={(items) => set("review_questions", items)}
        />
        <PairList
          title="Key concepts"
          values={value.key_concepts}
          first="name"
          second="explanation"
          disabled={disabled}
          onChange={(items) => set("key_concepts", items)}
        />
        <PairList
          title="Study notes"
          values={value.sections}
          first="heading"
          second="text"
          disabled={disabled}
          onChange={(items) => set("sections", items)}
        />
        <PairList
          title="Definitions"
          values={value.definitions}
          first="term"
          second="definition"
          disabled={disabled}
          onChange={(items) => set("definitions", items)}
        />
        <PairList
          title="Examples"
          values={value.examples}
          first="title"
          second="explanation"
          disabled={disabled}
          onChange={(items) => set("examples", items)}
        />
      </div>
    </section>
  );
}

function TextList({
  title,
  values,
  disabled,
  onChange,
}: {
  title: string;
  values: string[];
  disabled: boolean;
  onChange: (values: string[]) => void;
}) {
  return (
    <div>
      <div className="section-heading">
        <h3 className="section-title">{title}</h3>
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
    </div>
  );
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
  onChange,
}: {
  title: string;
  values: T[];
  first: keyof T & string;
  second: keyof T & string;
  disabled: boolean;
  onChange: (values: T[]) => void;
}) {
  return (
    <div>
      <h3 className="section-title">{title}</h3>
      <div className="grid gap-4">
        {values.map((item, index) => (
          <article className="learn-card" key={index}>
            <label className="field">
              {first.replaceAll("_", " ")}
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
              {second.replaceAll("_", " ")}
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
    </div>
  );
}
