# ADR-025: Resolve meeting owners against project members

## Context

Meeting transcripts use human shorthand: "Alex", "Sarah", "the designer", or no owner at all. Those names are not reliable Notion identities or GitHub usernames, and silently guessing would create work under the wrong person.

## Decision

COLLABORATE resolves extracted `owner_name` values only against `ProjectMember` records. Exact display-name matches win, first-name matches are accepted only when unique, ambiguous matches return all candidates, and unresolved or unspecified owners remain visible for human correction.

## Rationale

The language model is useful for extracting that a task exists and that a transcript said "Alex" owns it. It is not allowed to decide which GitHub or Notion identity that means. Keeping identity resolution deterministic makes review honest: the student sees where Relay is certain and where it needs help.

## Consequences

GitHub assignment only happens when the resolved member has a recorded `github_username`; otherwise the issue is created unassigned. Notion task owner fields are populated only when the project member has a configured Notion identity. Ambiguous owners block clean automation until the review step resolves them.

## When We Would Reconsider

If Relay later has organization directory sync or provider-native identity lookup with verified account links, the resolver could use those records as additional deterministic inputs. It should still never infer identities from transcript text alone.
