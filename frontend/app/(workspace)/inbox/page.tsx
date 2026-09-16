"use client";

import { useState } from "react";
import { Check, Inbox as InboxIcon, Pencil, Sparkles, X } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTaskProposals } from "@/hooks/queries";
import {
  taskProposals,
  type ProposalPayload,
  type TaskProposal,
} from "@/features/sources/api";
import { ErrorMessage, Loading, Spinner } from "@/components/ui";
import { localInputValue } from "@/lib/datetime";

const confirmationLabels = {
  due_date: "Due date unclear",
  owner: "Owner unclear",
  details: "Needs confirmation",
};

function ProposalCard({
  item,
  draft,
  setDraft,
  selected,
  toggle,
}: {
  item: TaskProposal;
  draft: ProposalPayload;
  setDraft: (draft: ProposalPayload) => void;
  selected: boolean;
  toggle: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const cache = useQueryClient();
  const finish = () => {
    cache.invalidateQueries({ queryKey: ["task-proposals"] });
    cache.invalidateQueries({ queryKey: ["tasks"] });
    cache.invalidateQueries({ queryKey: ["approvals"] });
    cache.invalidateQueries({
      queryKey: ["projects", item.project_id, "tasks"],
    });
  };
  const edit = useMutation({
    mutationFn: () => taskProposals.edit(item.approval_id, draft),
    onSuccess: () => {
      setEditing(false);
      finish();
    },
  });
  const accept = useMutation({
    mutationFn: () => taskProposals.accept(item.approval_id, draft),
    onSuccess: finish,
  });
  const reject = useMutation({
    mutationFn: () => taskProposals.reject(item.approval_id),
    onSuccess: finish,
  });
  const error = edit.error || accept.error || reject.error;
  return (
    <li className="proposal-card">
      <label className="proposal-select">
        <input
          type="checkbox"
          checked={selected}
          onChange={toggle}
          aria-label={`Select ${draft.title}`}
        />
        <span>
          <Check />
        </span>
      </label>
      <div className="proposal-body">
        <div className="proposal-context">
          <span className={item.project_space.toLowerCase()}>
            {item.project_space.toLowerCase()}
          </span>
          <strong>{item.project_name}</strong>
          <span>From {item.source_title}</span>
        </div>
        {editing ? (
          <div className="proposal-form">
            <label className="field">
              Task title
              <input
                value={draft.title}
                onChange={(event) =>
                  setDraft({ ...draft, title: event.target.value })
                }
              />
            </label>
            <label className="field">
              Description
              <textarea
                rows={3}
                value={draft.description || ""}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    description: event.target.value || null,
                  })
                }
              />
            </label>
            <div className="form-split">
              <label className="field">
                Due date
                <input
                  type="datetime-local"
                  value={draft.due_date ? localInputValue(draft.due_date) : ""}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      due_date: event.target.value
                        ? new Date(event.target.value).toISOString()
                        : null,
                    })
                  }
                />
              </label>
              <label className="field">
                Estimate (minutes)
                <input
                  type="number"
                  min={5}
                  value={draft.estimate_minutes || ""}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      estimate_minutes: event.target.value
                        ? Number(event.target.value)
                        : null,
                    })
                  }
                />
              </label>
            </div>
            <label className="field">
              Priority
              <select
                value={draft.priority || ""}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    priority: (event.target.value ||
                      null) as ProposalPayload["priority"],
                  })
                }
              >
                <option value="">Not set</option>
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">High</option>
              </select>
            </label>
          </div>
        ) : (
          <>
            <h2>{draft.title}</h2>
            {draft.description && (
              <p className="proposal-description">{draft.description}</p>
            )}
            <div className="proposal-meta">
              {draft.due_date && (
                <span>Due {new Date(draft.due_date).toLocaleDateString()}</span>
              )}
              {draft.estimate_minutes && (
                <span>{draft.estimate_minutes} min</span>
              )}
              {draft.priority && (
                <span>{draft.priority.toLowerCase()} priority</span>
              )}
            </div>
          </>
        )}
        {draft.possible_duplicate && (
          <p className="proposal-duplicate-warning">
            Possible duplicate
            {draft.duplicate_of_title
              ? ` of "${draft.duplicate_of_title}"`
              : ""}
            . Review before creating it again.
          </p>
        )}
        {draft.needs_confirmation.length > 0 && (
          <div className="confirmation-list">
            {draft.needs_confirmation.map((field) => (
              <button
                key={field}
                onClick={() =>
                  setDraft({
                    ...draft,
                    needs_confirmation: draft.needs_confirmation.filter(
                      (value) => value !== field,
                    ),
                  })
                }
              >
                {confirmationLabels[field]} <span>Confirm</span>
              </button>
            ))}
          </div>
        )}
        {draft.source_reference && (
          <p className="proposal-source">Source: {draft.source_reference}</p>
        )}
        <ErrorMessage
          error={error}
          title={
            accept.error
              ? "Couldn’t create selected task"
              : "Couldn’t update proposal"
          }
        />
      </div>
      <div className="proposal-actions">
        {editing ? (
          <>
            <button
              className="button secondary"
              onClick={() => {
                setDraft(item.proposal);
                setEditing(false);
              }}
            >
              Cancel
            </button>
            <button
              className="button secondary"
              onClick={() => edit.mutate()}
              disabled={!draft.title.trim() || edit.isPending}
            >
              {edit.isPending && <Spinner label="Saving proposal edits" />}
              Save edits
            </button>
          </>
        ) : (
          <button
            className="icon-button"
            onClick={() => setEditing(true)}
            aria-label={`Edit ${draft.title}`}
          >
            <Pencil />
          </button>
        )}
        {!editing && (
          <>
            <button
              className="button reject-button"
              onClick={() => reject.mutate()}
              disabled={reject.isPending}
            >
              {reject.isPending ? (
                <Spinner label="Rejecting proposal" />
              ) : (
                <X />
              )}
              {draft.possible_duplicate ? "Skip" : "Reject"}
            </button>
            <button
              className="button"
              onClick={() => accept.mutate()}
              disabled={draft.needs_confirmation.length > 0 || accept.isPending}
            >
              {accept.isPending ? <Spinner label="Creating task" /> : <Check />}
              {draft.possible_duplicate ? "Create anyway" : "Accept"}
            </button>
          </>
        )}
      </div>
    </li>
  );
}

export default function Inbox() {
  const query = useTaskProposals();
  const [selected, setSelected] = useState<string[]>([]);
  const [drafts, setDrafts] = useState<Record<string, ProposalPayload>>({});
  const cache = useQueryClient();
  const pending = (query.data || []).filter(
    (item) => item.status === "PENDING",
  );
  const proposalFor = (item: TaskProposal) =>
    drafts[item.approval_id] || item.proposal;
  const selectableItems = pending.filter((item) => {
    const proposal = proposalFor(item);
    return (
      proposal.needs_confirmation.length === 0 && !proposal.possible_duplicate
    );
  });
  const selectedItems = selectableItems
    .filter((item) => selected.includes(item.approval_id))
    .map((item) => ({ item, proposal: proposalFor(item) }));
  const acceptSelected = useMutation({
    mutationFn: async () => {
      const results = await Promise.allSettled(
        selectedItems.map(({ item, proposal }) =>
          taskProposals.accept(item.approval_id, proposal),
        ),
      );
      const failures = results.filter(
        (result) => result.status === "rejected",
      ).length;
      if (failures)
        throw new Error(
          `Couldn’t create ${failures} selected ${failures === 1 ? "task" : "tasks"}. Please retry.`,
        );
      return results;
    },
    onSuccess: () => {
      setSelected([]);
    },
    onSettled: () => {
      cache.invalidateQueries({ queryKey: ["task-proposals"] });
      cache.invalidateQueries({ queryKey: ["tasks"] });
      cache.invalidateQueries({ queryKey: ["approvals"] });
      for (const { item } of selectedItems)
        cache.invalidateQueries({
          queryKey: ["projects", item.project_id, "tasks"],
        });
    },
  });
  if (query.isPending) return <Loading />;
  if (query.error)
    return <ErrorMessage error={query.error} retry={() => query.refetch()} />;
  return (
    <>
      <header className="inbox-hero">
        <div>
          <p className="eyebrow">Review before anything moves</p>
          <h1>Inbox</h1>
          <p>Task proposals from your sources, waiting for your decision.</p>
        </div>
        <span>
          <InboxIcon />
        </span>
      </header>
      {pending.length > 0 && (
        <div className="inbox-toolbar">
          <label>
            <input
              type="checkbox"
              checked={
                selectableItems.length > 0 &&
                selectableItems.every((item) =>
                  selected.includes(item.approval_id),
                )
              }
              onChange={(event) =>
                setSelected(
                  event.target.checked
                    ? selectableItems.map((item) => item.approval_id)
                    : [],
                )
              }
            />{" "}
            Select all
          </label>
          <button
            className="button"
            disabled={!selectedItems.length || acceptSelected.isPending}
            onClick={() => acceptSelected.mutate()}
          >
            {acceptSelected.isPending ? (
              <Spinner label="Creating selected tasks" />
            ) : (
              <Check />
            )}
            Accept selected ({selectedItems.length})
          </button>
        </div>
      )}
      <ErrorMessage
        error={acceptSelected.error}
        title="Couldn’t create selected tasks"
      />
      {!pending.length ? (
        <div className="inbox-empty">
          <Sparkles />
          <h2>All clear.</h2>
          <p>
            New task proposals will wait here for you. Relay never creates them
            before your approval.
          </p>
        </div>
      ) : (
        <ul className="inbox-list proposal-list">
          {pending.map((item) => (
            <ProposalCard
              key={item.approval_id}
              item={item}
              draft={proposalFor(item)}
              setDraft={(draft) =>
                setDrafts((current) => ({
                  ...current,
                  [item.approval_id]: draft,
                }))
              }
              selected={selected.includes(item.approval_id)}
              toggle={() =>
                setSelected((current) =>
                  current.includes(item.approval_id)
                    ? current.filter((id) => id !== item.approval_id)
                    : [...current, item.approval_id],
                )
              }
            />
          ))}
        </ul>
      )}
    </>
  );
}
