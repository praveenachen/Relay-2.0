from typing import Any

from app.connectors.github.schemas import (
    CreateGitHubIssueAction,
    GitHubIssueResult,
    GitHubPullRequest,
    GitHubRepository,
    GitHubReviewRequestResult,
    RequestPullRequestReviewAction,
)


def _string_value(data: dict[str, Any], key: str, default: str = "") -> str:
    value = data.get(key)
    return value if isinstance(value, str) else default


def repository_from_response(data: dict[str, Any]) -> GitHubRepository:
    owner = data.get("owner")
    return GitHubRepository(
        owner=owner.get("login", "") if isinstance(owner, dict) else "",
        name=_string_value(data, "name"),
        full_name=_string_value(data, "full_name"),
        private=bool(data.get("private", False)),
        html_url=_string_value(data, "html_url"),
    )


def pull_request_from_response(data: dict[str, Any]) -> GitHubPullRequest:
    return GitHubPullRequest(
        number=data["number"],
        title=_string_value(data, "title"),
        html_url=_string_value(data, "html_url"),
        state=_string_value(data, "state", "open"),
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
        external_url=_string_value(data, "html_url"),
        number=number,
        title=_string_value(data, "title", action.title),
    )


def review_request_result_from_response(
    action: RequestPullRequestReviewAction, data: dict[str, Any]
) -> GitHubReviewRequestResult:
    return GitHubReviewRequestResult(
        external_id=(
            f"{action.repository_owner}/{action.repository_name}"
            f"#{action.pull_number}:{action.reviewer}"
        ),
        external_url=_string_value(data, "html_url"),
        pull_number=action.pull_number,
        reviewer=action.reviewer,
    )
