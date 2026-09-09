# ADR-026: Use GitHub OAuth now, revisit GitHub Apps later

## Context

COLLABORATE needs repository lookup, collaborator lookup, label lookup, issue creation, and review requests on existing pull requests. GitHub supports both classic OAuth Apps and GitHub Apps, but their setup and permission models differ materially.

## Decision

Phase 7 uses a classic GitHub OAuth App with the `repo` scope. Relay stores the token encrypted on the user's `ConnectedAccount` and never requests repository deletion, admin, workflow, Gmail, or unrelated permissions.

## Rationale

A GitHub App would provide better least-privilege permissions and installation-scoped access, but it requires app registration, installation handling, JWT app authentication, installation access tokens, and extra UI states. OAuth is smaller and matches the existing per-user connection architecture. `public_repo` is insufficient for private class repositories, so `repo` is the narrowest classic OAuth scope that supports this phase's private-repository issue and PR-review work.

## Consequences

OAuth tokens are coarser than ideal and inherit the connecting user's repository access. Relay mitigates this by keeping provider calls behind typed connector methods, storing tokens encrypted, and never exposing credentials to the frontend. GitHub App migration remains a future hardening item.

## When We Would Reconsider

Before production use across many repositories or organizations, Relay should move to a GitHub App with explicit Issues, Pull Requests, and Metadata permissions and installation-level repository selection.
