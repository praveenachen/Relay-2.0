"use client";

import Link from "next/link";
import { useState } from "react";
import { FileUp, Sparkles, X } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  sources,
  type ProjectSource,
  type SourceType,
} from "@/features/sources/api";
import { ErrorMessage, Spinner } from "@/components/ui";

const labels: Record<SourceType, string> = {
  ASSIGNMENT_BRIEF: "Assignment / brief",
  COURSE_OUTLINE: "Course outline",
  STUDY_GOAL: "Study goal",
  MEETING_TRANSCRIPT: "Meeting notes / transcript",
  DOCUMENT_BRIEF: "Document / brief",
  PERSONAL_GOAL: "Goal / project idea",
  NOTES_CHECKLIST: "Notes / checklist",
};

export function SourceCaptureModal({
  projectId,
  sourceType,
  close,
}: {
  projectId: string;
  sourceType: SourceType;
  close: () => void;
}) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [created, setCreated] = useState(false);
  const cache = useQueryClient();
  const create = useMutation({
    mutationFn: () =>
      sources.create(projectId, {
        sourceType,
        title: title.trim(),
        content,
        file,
      }),
    onSuccess: (source) => {
      cache.setQueryData<ProjectSource[]>(
        ["projects", projectId, "sources"],
        (items = []) => [source, ...items],
      );
      cache.invalidateQueries({ queryKey: ["task-proposals"] });
      setCreated(true);
    },
  });
  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(event) =>
        event.target === event.currentTarget && !create.isPending && close()
      }
    >
      <section
        className="project-modal source-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="source-modal-title"
      >
        <div className="modal-heading">
          <div>
            <p className="eyebrow">Add source</p>
            <h2 id="source-modal-title">{labels[sourceType]}</h2>
          </div>
          <button className="icon-button" onClick={close} aria-label="Close">
            <X />
          </button>
        </div>
        {created ? (
          <div className="source-success">
            <Sparkles />
            <h3>Proposals are ready.</h3>
            <p>
              Relay interpreted the source. Nothing has been created until you
              review and accept it.
            </p>
            <div>
              <button className="button secondary" onClick={close}>
                Stay here
              </button>
              <Link className="button" href="/inbox">
                Review in Inbox
              </Link>
            </div>
          </div>
        ) : (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              create.mutate();
            }}
          >
            <label className="field">
              Source title
              <input
                required
                maxLength={255}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="A name you’ll recognize later"
              />
            </label>
            <label className="field">
              Paste content
              <textarea
                rows={8}
                value={content}
                onChange={(event) => setContent(event.target.value)}
                placeholder="Paste the brief, transcript, outline, goal, or checklist…"
              />
            </label>
            <label className="source-file">
              <FileUp />
              <span>
                <strong>Or choose a document</strong>
                <small>PDF, DOCX, Markdown, or text</small>
              </span>
              <input
                type="file"
                accept=".pdf,.docx,.md,.markdown,.txt"
                onChange={(event) => setFile(event.target.files?.[0] || null)}
              />
            </label>
            {file && <p className="selected-file">{file.name}</p>}
            <ErrorMessage
              error={create.error}
              title="Couldn’t process source"
            />
            <div className="modal-actions">
              <button
                type="button"
                className="button secondary"
                onClick={close}
              >
                Cancel
              </button>
              <button
                className="button"
                disabled={
                  !title.trim() ||
                  (!content.trim() && !file) ||
                  create.isPending
                }
              >
                {create.isPending && (
                  <Spinner label="Generating task proposals" />
                )}
                {create.isPending
                  ? "Finding useful tasks…"
                  : "Create proposals"}
              </button>
            </div>
            <p className="source-safety">
              Relay will prepare proposals for review. It won’t create tasks
              yet.
            </p>
          </form>
        )}
      </section>
    </div>
  );
}
