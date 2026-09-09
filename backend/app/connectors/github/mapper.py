from typing import Any

from app.connectors.github.schemas import (
    CreateGitHubIssueAction,
    GitHubIssueResult,
    GitHubPullRequest,
    GitHubRepository,
    GitHubReviewRequestResult,
    RequestPullRequestReviewAction,
)


def repository_from_response(data: dict[str, Any]) -> GitHubRepository:
    owner = data.get("owner")
    return GitHubRepository(
        owner=owner.get("login", "") if isinstance(owner, dict) else "",
        name=data.get("name", ""),
        full_name=data.get("full_name", ""),
        private=bool(data.get("private", False)),
        html_url=data.get("html_url") if isinstance(data.get("html_url"), str) else "",
    )


def pull_request_from_response(data: dict[str, Any]) -> GitHubPullRequest:
    return GitHubPullRequest(
        number=data["number"],
        title=data.get("title") or "",
        html_url=data.get("html_url") or "",
        state=data.get("state") or "open",
    )


def issue_result_from_response(
    action: CreateGitHubIssueAction, data: dict[str, Any]
) -> GitHubIssueResult:
    number = data["number"]
    return GitHubIssueResult(
        # Issue numbers repeat across repositories, so the artifact identity
        # composes the repository the same way GitHub's own UI addresses an
        # issue ("owner/name#number"), keeping it unique per connected account.
        external_id=f"{action.repository_owner}/{action.repository_name}#{number}",
        external_url=data.get("html_url") or "",
        number=number,
        title=data.get("title") or action.title,
    )


def review_request_result_from_response(
    action: RequestPullRequestReviewAction, data: dict[str, Any]
) -> GitHubReviewRequestResult:
    return GitHubReviewRequestResult(
        external_id=(
            f"{action.repository_owner}/{action.repository_name}"
            f"#{action.pull_number}:{action.reviewer}"
        ),
        external_url=data.get("html_url") if isinstance(data.get("html_url"), str) else "",
        pull_number=action.pull_number,
        reviewer=action.reviewer,
    )
