from uuid import NAMESPACE_URL, uuid5

from app.connectors.github.errors import GitHubUnavailable
from app.connectors.github.schemas import (
    CreateGitHubIssueAction,
    GitHubIssueResult,
    GitHubReviewRequestResult,
    RequestPullRequestReviewAction,
)


class MockGitHubConnector:
    def __init__(self, *, fail: bool = False):
        self.fail = fail

    async def create_issue(
        self, action: CreateGitHubIssueAction, idempotency_key: str
    ) -> GitHubIssueResult:
        if self.fail:
            raise GitHubUnavailable()
        identifier = uuid5(NAMESPACE_URL, idempotency_key).hex
        number = int(identifier[:6], 16) % 9000 + 100
        return GitHubIssueResult(
            external_id=f"{action.repository_owner}/{action.repository_name}#{number}",
            external_url=f"mock://github/issue/{identifier}",
            number=number,
            title=action.title,
            simulated=True,
        )

    async def request_review(
        self, action: RequestPullRequestReviewAction, idempotency_key: str
    ) -> GitHubReviewRequestResult:
        if self.fail:
            raise GitHubUnavailable()
        identifier = uuid5(NAMESPACE_URL, idempotency_key).hex
        return GitHubReviewRequestResult(
            external_id=(
                f"{action.repository_owner}/{action.repository_name}"
                f"#{action.pull_number}:{action.reviewer}"
            ),
            external_url=f"mock://github/review/{identifier}",
            pull_number=action.pull_number,
            reviewer=action.reviewer,
            simulated=True,
        )
