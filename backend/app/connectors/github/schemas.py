from typing import Any

from pydantic import ConfigDict, Field

from app.workflows.lecture_notes.schemas import StrictModel


class GitHubOAuthToken(StrictModel):
    model_config = ConfigDict(extra="ignore")

    access_token: str
    token_type: str = "bearer"
    scope: str = ""


class GitHubUserInfo(StrictModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    login: str
    name: str | None = None


class GitHubRepository(StrictModel):
    owner: str
    name: str
    full_name: str
    private: bool = False
    html_url: str = ""


class GitHubCollaborator(StrictModel):
    login: str


class GitHubLabel(StrictModel):
    name: str


class GitHubPullRequest(StrictModel):
    number: int
    title: str
    html_url: str
    state: str = "open"


class CreateGitHubIssueAction(StrictModel):
    task_id: str
    repository_owner: str = Field(min_length=1, max_length=255)
    repository_name: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    body: str = ""
    assignees: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()
    connection_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GitHubIssueResult(StrictModel):
    external_id: str
    external_url: str
    number: int
    title: str
    simulated: bool = False


class RequestPullRequestReviewAction(StrictModel):
    task_id: str
    repository_owner: str = Field(min_length=1, max_length=255)
    repository_name: str = Field(min_length=1, max_length=255)
    pull_number: int = Field(gt=0)
    reviewer: str = Field(min_length=1, max_length=255)
    connection_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GitHubReviewRequestResult(StrictModel):
    external_id: str
    external_url: str
    pull_number: int
    reviewer: str
    simulated: bool = False
