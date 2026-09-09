from typing import Any

import httpx

from app.connectors.github.errors import (
    GitHubAuthorizationFailed,
    GitHubLabelNotFound,
    GitHubPullRequestNotFound,
    GitHubRateLimited,
    GitHubRepositoryAccessDenied,
    GitHubRepositoryNotFound,
    GitHubRequestTimeout,
    GitHubReviewerInvalid,
    GitHubUnavailable,
    GitHubUserNotAssignable,
    GitHubValidationFailed,
)
from app.connectors.github.mapper import (
    issue_result_from_response,
    pull_request_from_response,
    repository_from_response,
    review_request_result_from_response,
)
from app.connectors.github.schemas import (
    CreateGitHubIssueAction,
    GitHubCollaborator,
    GitHubIssueResult,
    GitHubLabel,
    GitHubPullRequest,
    GitHubRepository,
    GitHubReviewRequestResult,
    RequestPullRequestReviewAction,
)

GITHUB_API_VERSION = "2022-11-28"


def retry_after(headers: httpx.Headers) -> int | None:
    value = headers.get("retry-after")
    if value and value.isdigit():
        return int(value)
    return None


def github_error(response: httpx.Response) -> Exception:
    """Fallback mapping for statuses whose meaning doesn't depend on which
    endpoint was called. 404 and 422 mean different things at different
    call sites (repository vs. pull request; invalid assignee vs. label),
    so those are handled at each call site instead."""
    if response.status_code == 401:
        return GitHubAuthorizationFailed()
    if response.status_code == 403:
        if response.headers.get("x-ratelimit-remaining") == "0":
            return GitHubRateLimited(retry_after(response.headers))
        return GitHubRepositoryAccessDenied()
    if response.status_code == 404:
        return GitHubRepositoryNotFound()
    if response.status_code == 429:
        return GitHubRateLimited(retry_after(response.headers))
    if response.status_code == 422:
        return GitHubValidationFailed()
    return GitHubUnavailable()


def _issue_validation_error(response: httpx.Response) -> Exception:
    try:
        data = response.json()
    except ValueError:
        return GitHubValidationFailed()
    errors = data.get("errors") if isinstance(data, dict) else None
    if isinstance(errors, list):
        for item in errors:
            field = item.get("field") if isinstance(item, dict) else None
            if field == "assignees":
                return GitHubUserNotAssignable()
            if field == "labels":
                return GitHubLabelNotFound()
    return GitHubValidationFailed()


class GitHubApiClient:
    def __init__(
        self,
        access_token: str,
        *,
        base_url: str = "https://api.github.com",
        timeout: int = 20,
    ):
        self.access_token = access_token
        self.base_url = base_url
        self.timeout = timeout

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                return await client.request(
                    method,
                    path,
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": GITHUB_API_VERSION,
                    },
                    json=json,
                    params=params,
                )
        except httpx.TimeoutException as error:
            raise GitHubRequestTimeout() from error
        except httpx.HTTPError as error:
            raise GitHubUnavailable() from error

    async def get_repository(self, owner: str, name: str) -> GitHubRepository:
        response = await self.request("GET", f"/repos/{owner}/{name}")
        if response.status_code >= 400:
            raise github_error(response)
        return repository_from_response(response.json())

    async def list_repositories(self) -> list[GitHubRepository]:
        # Single page, most-recently-pushed first: enough for a project
        # setup picker without building full pagination for this phase.
        response = await self.request(
            "GET",
            "/user/repos",
            params={"per_page": 100, "sort": "pushed", "affiliation": "owner,collaborator"},
        )
        if response.status_code >= 400:
            raise github_error(response)
        data = response.json()
        return [repository_from_response(item) for item in data if isinstance(item, dict)]

    async def list_collaborators(self, owner: str, name: str) -> list[GitHubCollaborator]:
        response = await self.request(
            "GET", f"/repos/{owner}/{name}/collaborators", params={"per_page": 100}
        )
        if response.status_code >= 400:
            raise github_error(response)
        data = response.json()
        return [
            GitHubCollaborator(login=item["login"])
            for item in data
            if isinstance(item, dict) and isinstance(item.get("login"), str)
        ]

    async def list_labels(self, owner: str, name: str) -> list[GitHubLabel]:
        response = await self.request(
            "GET", f"/repos/{owner}/{name}/labels", params={"per_page": 100}
        )
        if response.status_code >= 400:
            raise github_error(response)
        data = response.json()
        return [
            GitHubLabel(name=item["name"])
            for item in data
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        ]

    async def get_pull_request(self, owner: str, name: str, number: int) -> GitHubPullRequest:
        response = await self.request("GET", f"/repos/{owner}/{name}/pulls/{number}")
        if response.status_code == 404:
            raise GitHubPullRequestNotFound()
        if response.status_code >= 400:
            raise github_error(response)
        return pull_request_from_response(response.json())

    async def create_issue(
        self, action: CreateGitHubIssueAction, idempotency_key: str
    ) -> GitHubIssueResult:
        marker = f"\n\n<!-- relay-action: {idempotency_key} -->"
        response = await self.request(
            "POST",
            f"/repos/{action.repository_owner}/{action.repository_name}/issues",
            json={
                "title": action.title,
                "body": (action.body or "") + marker,
                "assignees": list(action.assignees),
                "labels": list(action.labels),
            },
        )
        if response.status_code == 422:
            raise _issue_validation_error(response)
        if response.status_code >= 400:
            raise github_error(response)
        return issue_result_from_response(action, response.json())

    async def request_review(
        self, action: RequestPullRequestReviewAction, idempotency_key: str
    ) -> GitHubReviewRequestResult:
        response = await self.request(
            "POST",
            f"/repos/{action.repository_owner}/{action.repository_name}"
            f"/pulls/{action.pull_number}/requested_reviewers",
            json={"reviewers": [action.reviewer]},
        )
        if response.status_code == 404:
            raise GitHubPullRequestNotFound()
        if response.status_code == 422:
            raise GitHubReviewerInvalid()
        if response.status_code >= 400:
            raise github_error(response)
        return review_request_result_from_response(action, response.json())


class GitHubConnector:
    def __init__(self, client: GitHubApiClient):
        self.client = client

    async def repositories(self) -> list[GitHubRepository]:
        return await self.client.list_repositories()

    async def repository(self, owner: str, name: str) -> GitHubRepository:
        return await self.client.get_repository(owner, name)

    async def collaborators(self, owner: str, name: str) -> list[GitHubCollaborator]:
        return await self.client.list_collaborators(owner, name)

    async def labels(self, owner: str, name: str) -> list[GitHubLabel]:
        return await self.client.list_labels(owner, name)

    async def pull_request(self, owner: str, name: str, number: int) -> GitHubPullRequest:
        return await self.client.get_pull_request(owner, name, number)

    async def create_issue(
        self, action: CreateGitHubIssueAction, idempotency_key: str
    ) -> GitHubIssueResult:
        return await self.client.create_issue(action, idempotency_key)

    async def request_review(
        self, action: RequestPullRequestReviewAction, idempotency_key: str
    ) -> GitHubReviewRequestResult:
        return await self.client.request_review(action, idempotency_key)
