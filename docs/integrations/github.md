# GitHub integration

Relay supports GitHub as the technical-work destination for COLLABORATE: issues for technical tasks, review requests on existing pull requests. Like Notion and Google Calendar, this is per-user OAuth with encrypted credential storage; Relay never uses a shared developer token.

## GitHub App vs. OAuth

This phase uses a classic GitHub **OAuth App**, not a GitHub App. See `docs/decisions/ADR-026-github-app-vs-oauth.md` for the full reasoning; in short: a GitHub App's installation-scoped, fine-grained permissions (e.g. "Issues: write, Metadata: read" with no code/admin access at all) are the *more* correct least-privilege choice, but they require a materially bigger integration (JWT-signed app authentication, installation access tokens, an app manifest, installation management UI) that isn't justified yet at this phase's scope. OAuth's `repo` scope is coarser than that -- it grants read/write on code, issues, and pull requests for repositories the user can access -- but it is still the *narrowest classic OAuth scope* that supports issue and PR work on private repositories (the only alternative, `public_repo`, would silently fail for a private class project repo). Relay never requests `delete_repo`, `admin:*`, or `workflow`.

## Local configuration

Create an OAuth App at github.com/settings/developers and configure the local callback:

```text
http://localhost:8000/connections/GITHUB/callback
```

Set these server-side values in `.env`:

```text
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GITHUB_REDIRECT_URI=http://localhost:8000/connections/GITHUB/callback
TOKEN_ENCRYPTION_KEY=
GITHUB_PUBLISH_MODE=mock
```

`GITHUB_PUBLISH_MODE=real` switches `LocalRuntimeClient` from `MockGitHubConnector` to the real, database-backed connector -- the same `mock`/`real` toggle Notion already uses for LEARN, so tests and local development never need a live GitHub account by default.

## OAuth flow and token lifecycle

`GET /connections/GITHUB/authorize` creates a random state, stores only its SHA-256 hash with an expiry, and returns a GitHub authorization URL requesting `scope=repo` only. The callback validates state, exchanges the code, fetches the authenticated user's login via `GET /user`, and persists the encrypted access token. Classic GitHub OAuth App tokens do not expire and carry no refresh token (`GoogleOAuthClient`'s refresh dance and ADR-018's "provider-specific token lifecycle" both anticipated this: GitHub simply needs none of it). A 401 from any GitHub call marks the connection `REVOKED` and clears the stored token, the same pattern Notion and Google already use.

One real quirk `GitHubOAuthClient.exchange_code` accounts for: GitHub answers a bad or reused authorization code with **HTTP 200** and an `{"error": "..."}` body, not a 4xx status -- the client checks for that field explicitly rather than trusting the status code alone.

## Repository context

A COLLABORATE run never lets the model infer a repository. `ProjectWorkspace.github_repository_owner` / `github_repository_name` are set once when the project is created (from a picker backed by `GET /connections/GITHUB/repositories`, listing the user's accessible repositories) and reused by every meeting for that project. Before proposing GitHub actions, `GitHubService.repository()` / `.collaborators()` / `.labels()` read live data through `GitHubApiClient` and normalize it into Relay's own `GitHubRepository` / `GitHubCollaborator` / `GitHubLabel` types -- the scheduling/planning code never sees a raw GitHub API response.

## Issues, assignment, and labels

`CreateGitHubIssueAction` is the typed, frozen payload: repository, title, body, `assignees`, `labels`. Labels are never populated from the model -- `MeetingActionItem` has no labels field at all, so any label on an issue came from a student typing it into the review UI. Before an approval round is requested, `ProjectMeetingWorkflowService._github_repository_facts` fetches the repository's real collaborators and labels once and drops any assignee or label that doesn't actually exist, rather than letting GitHub reject the whole issue at execution time over one bad entry; a resolved member with no `github_username` recorded is simply left unassigned (never guessed).

## Pull request review requests

Relay only requests a review on a **pull request that already exists**. `RequestPullRequestReviewAction` requires a repository, a pull number, and a reviewer login. The pull number comes from a deterministic regex over the transcript's own text (`#12`) -- never invented -- run against whatever raw phrase the model captured in `pull_request_reference`; if no number can be extracted, the action item's GitHub destination stays empty and the review request is visibly unresolved in the review UI rather than silently skipped. Relay never creates a pull request and never generates code.

## Idempotency and artifacts

The idempotency-key marker convention matches Google's and Notion's: an issue body gets a trailing `<!-- relay-action: {key} -->` HTML comment (invisible in GitHub's rendered view), and a review-request artifact's identity composes `owner/name#pull_number:reviewer` since a single PR can have multiple review requests. The actual duplicate-prevention guarantee, as with every provider, is Relay's own `ExternalArtifact.idempotency_key` uniqueness constraint plus the `LocalExecution` idempotency check before any call is made at all.

## Errors

Raw HTTP responses are translated to Relay domain errors at the connector boundary (`app/connectors/github/client.py::github_error` plus per-call-site overrides, since 404 and 422 mean different things depending on which endpoint was called):

- `GITHUB_NOT_CONNECTED`
- `GITHUB_AUTHORIZATION_FAILED` (401)
- `GITHUB_REPOSITORY_ACCESS_DENIED` (403, not rate-limited)
- `GITHUB_REPOSITORY_NOT_FOUND` (404 on a repository)
- `GITHUB_PULL_REQUEST_NOT_FOUND` (404 on a pull request)
- `GITHUB_USER_NOT_ASSIGNABLE` / `GITHUB_LABEL_NOT_FOUND` (422 on issue creation, distinguished by GitHub's `errors[].field`)
- `GITHUB_REVIEWER_INVALID` (422 on a review request)
- `GITHUB_RATE_LIMITED` (429, or 403 with `X-RateLimit-Remaining: 0`)
- `GITHUB_REQUEST_TIMEOUT`
- `GITHUB_UNAVAILABLE` (other 4xx/5xx or a network error)

## Testing

`backend/tests/test_github_connector.py` covers OAuth scope/state/replay, the "200 with an error field" quirk, repository/collaborator/label reads, issue creation (including the idempotency marker and the composed external id), 404/422/429/timeout mapping, and pull request lookup plus review requests -- all against `httpx.MockTransport`, no live GitHub API calls in CI.
