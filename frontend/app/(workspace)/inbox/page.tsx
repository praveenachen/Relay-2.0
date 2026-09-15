"use client";

import Link from "next/link";
import { Inbox as InboxIcon, Sparkles } from "lucide-react";
import { useDefinitions, usePendingApprovals, useRuns } from "@/hooks/queries";
import { displayFor, runTitle } from "@/features/workflows/display";
import { ErrorMessage, Loading } from "@/components/ui";

export default function Inbox() {
  const approvals = usePendingApprovals(), runs = useRuns(), definitions = useDefinitions();
  if (approvals.isPending || runs.isPending || definitions.isPending) return <Loading />;
  const error = approvals.error || runs.error || definitions.error;
  if (error) return <ErrorMessage error={error} />;
  const runMap = Object.fromEntries((runs.data || []).map((run) => [run.id, run]));
  const definitionMap = Object.fromEntries((definitions.data || []).map((definition) => [definition.id, definition]));
  return (
    <>
      <header className="inbox-hero"><div><p className="eyebrow">Review before anything moves</p><h1>Inbox</h1><p>Suggestions from Relay, waiting for your decision.</p></div><span><InboxIcon /></span></header>
      {!approvals.data?.length ? <div className="inbox-empty"><Sparkles /><h2>All clear.</h2><p>New task and note proposals will wait here for you—never buried in raw system data.</p></div> : <ul className="inbox-list">{approvals.data.map((approval) => { const run = runMap[approval.workflow_run_id]; const definition = run && definitionMap[run.workflow_definition_id]; const display = displayFor(definition?.key); const title = run ? runTitle(run, display) : "Proposed update"; const href = display ? `/workflows/${display.slug}/${approval.workflow_run_id}` : `/runs/${approval.workflow_run_id}`; return <li key={approval.id}><div className={`inbox-kind ${display?.slug || ""}`}><Sparkles /></div><div><p>{display?.pillar || "Relay suggestion"}</p><h2>{title}</h2><span>Ready for your review · {new Date(approval.requested_at).toLocaleDateString()}</span></div><Link className="button secondary" href={href}>Review</Link></li>; })}</ul>}
    </>
  );
}
