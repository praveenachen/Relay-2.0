from uuid import UUID

import httpx
import pytest
from cryptography.fernet import Fernet

from app.connectors.github.auth import GitHubOAuthClient, GitHubOAuthService
from app.connectors.github.client import GitHubApiClient, github_error
from app.connectors.github.errors import (
    GitHubAuthorizationFailed,
    GitHubLabelNotFound,
    GitHubNotConnected,
    GitHubPullRequestNotFound,
    GitHubRateLimited,
    GitHubRepositoryAccessDenied,
    GitHubRepositoryNotFound,
    GitHubRequestTimeout,
    GitHubReviewerInvalid,
    GitHubUserNotAssignable,
)
from app.connectors.github.schemas import (
    CreateGitHubIssueAction,
    GitHubOAuthToken,
    GitHubUserInfo,
    RequestPullRequestReviewAction,
)
from app.connectors.github.service import GitHubService
from app.domain.enums import Provider
from app.infrastructure.credentials import FernetCredentialStore
from app.models.entities import ConnectedAccount
from app.repositories.relay import RelayRepository


def test_github_oauth_url_uses_repo_scope_only() -> None:
    url = GitHubOAuthClient("client", "secret", "http://localhost/callback").authorization_url(
        "state-1"
    )
    assert "scope=repo" in url
    assert "delete_repo" not in url
    assert "admin" not in url
    assert "workflow" not in url


async def test_github_oauth_state_exchange_encrypts_tokens(account, session_factory) -> None:
    store = FernetCredentialStore([Fernet.generate_key().decode()])
    async with session_factory() as session:
        service = GitHubOAuthService(
            RelayRepository(session),
            GitHubOAuthClient("client", "secret", "https://relay.test/connections/GITHUB/callback"),
            store,
        )
        started = await service.start(UUID(account["id"]))
        state = started["authorization_url"].split("state=")[1].split("&")[0]

        async def exchange(code: str) -> GitHubOAuthToken:
            assert code == "code-1"
            return GitHubOAuthToken(access_token="github-access", scope="repo")

        async def userinfo(token: str) -> GitHubUserInfo:
            assert token == "github-access"
            return GitHubUserInfo(id=42, login="sarahc", name="Sarah Chen")

        service.oauth.exchange_code = exchange
        service.oauth.userinfo = userinfo
        connected = await service.callback(
            UUID(account["id"]), state=state, code="code-1", error=None
        )
        stored = await session.get(ConnectedAccount, connected.id)
        assert stored is not None
        assert stored.provider == Provider.GITHUB
        assert stored.access_token_encrypted != "github-access"
        assert store.decrypt(stored.access_token_encrypted) == "github-access"
        assert stored.refresh_token_encrypted is None
        # A used state cannot be replayed.
        with pytest.raises(GitHubAuthorizationFailed):
            await service.callback(UUID(account["id"]), state=state, code="code-1", error=None)


async def test_github_oauth_rejects_response_with_error_field() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "bad_verification_code"})

    transport = httpx.MockTransport(handler)

    class TestClient(GitHubOAuthClient):
        async def exchange_code(self, code: str) -> GitHubOAuthToken:
            async with httpx.AsyncClient(transport=transport) as client:
                response = await client.post(self.token_url)
            data = response.json()
            if "error" in data:
                raise GitHubAuthorizationFailed()
            return GitHubOAuthToken.model_validate(data)

    client = TestClient("client", "secret", "http://localhost/callback")
    with pytest.raises(GitHubAuthorizationFailed):
        await client.exchange_code("bad-code")


def _mock_client(handler) -> GitHubApiClient:
    transport = httpx.MockTransport(handler)

    class TestClient(GitHubApiClient):
        async def request(self, method, path, *, json=None, params=None):
            async with httpx.AsyncClient(
                transport=transport, base_url="https://api.github.com"
            ) as client:
                return await client.request(method, path, json=json, params=params)

    return TestClient("token")


async def test_repository_access_labels_and_collaborators() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/team/app":
            return httpx.Response(
                200,
                json={
                    "name": "app",
                    "full_name": "team/app",
                    "private": True,
                    "html_url": "https://github.com/team/app",
                    "owner": {"login": "team"},
                },
            )
        if request.url.path == "/repos/team/app/collaborators":
            return httpx.Response(200, json=[{"login": "sarahc"}, {"login": "alexk"}])
        if request.url.path == "/repos/team/app/labels":
            return httpx.Response(200, json=[{"name": "bug"}, {"name": "documentation"}])
        return httpx.Response(404, json={})

    client = _mock_client(handler)
    repo = await client.get_repository("team", "app")
    assert repo.full_name == "team/app" and repo.private is True
    collaborators = await client.list_collaborators("team", "app")
    assert {c.login for c in collaborators} == {"sarahc", "alexk"}
    labels = await client.list_labels("team", "app")
    assert {label.name for label in labels} == {"bug", "documentation"}


async def test_repository_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    client = _mock_client(handler)
    with pytest.raises(GitHubRepositoryNotFound):
        await client.get_repository("team", "missing")


async def test_create_issue_embeds_idempotency_marker_and_composes_external_id() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read().decode()
        return httpx.Response(
            201,
            json={
                "number": 42,
                "title": "Implement auth",
                "html_url": "https://github.com/team/app/issues/42",
            },
        )

    client = _mock_client(handler)
    action = CreateGitHubIssueAction(
        task_id="action-1",
        repository_owner="team",
        repository_name="app",
        title="Implement auth",
        body="Do the thing",
        assignees=("sarahc",),
        labels=("bug",),
    )
    result = await client.create_issue(action, "collaborate:run-1:action-1")
    assert result.number == 42
    assert result.external_id == "team/app#42"
    assert "relay-action: collaborate:run-1:action-1" in captured["body"]


async def test_create_issue_invalid_assignee_and_label_mapped_distinctly() -> None:
    def assignee_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"errors": [{"field": "assignees"}]})

    def label_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"errors": [{"field": "labels"}]})

    action = CreateGitHubIssueAction(
        task_id="a", repository_owner="team", repository_name="app", title="X"
    )
    with pytest.raises(GitHubUserNotAssignable):
        await _mock_client(assignee_handler).create_issue(action, "key-1")
    with pytest.raises(GitHubLabelNotFound):
        await _mock_client(label_handler).create_issue(action, "key-2")


async def test_pull_request_lookup_and_review_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/repos/team/app/pulls/7":
            return httpx.Response(
                200,
                json={"number": 7, "title": "Add auth", "html_url": "https://x/7", "state": "open"},
            )
        if request.url.path == "/repos/team/app/pulls/7/requested_reviewers":
            return httpx.Response(201, json={"html_url": "https://x/7"})
        return httpx.Response(404, json={})

    client = _mock_client(handler)
    pr = await client.get_pull_request("team", "app", 7)
    assert pr.number == 7 and pr.state == "open"
    action = RequestPullRequestReviewAction(
        task_id="a", repository_owner="team", repository_name="app", pull_number=7, reviewer="alexk"
    )
    result = await client.request_review(action, "collaborate:run-1:action-2")
    assert result.external_id == "team/app#7:alexk"


async def test_pull_request_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={})

    client = _mock_client(handler)
    with pytest.raises(GitHubPullRequestNotFound):
        await client.get_pull_request("team", "app", 999)


async def test_review_request_invalid_reviewer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={})

    client = _mock_client(handler)
    action = RequestPullRequestReviewAction(
        task_id="a",
        repository_owner="team",
        repository_name="app",
        pull_number=7,
        reviewer="nobody",
    )
    with pytest.raises(GitHubReviewerInvalid):
        await client.request_review(action, "key-3")


def test_error_mapping_permission_rate_limit_and_generic() -> None:
    denied = httpx.Response(403, headers={}, json={})
    assert isinstance(github_error(denied), GitHubRepositoryAccessDenied)
    limited = httpx.Response(403, headers={"x-ratelimit-remaining": "0"}, json={})
    assert isinstance(github_error(limited), GitHubRateLimited)
    rate_limited = httpx.Response(429, headers={"retry-after": "30"}, json={})
    mapped = github_error(rate_limited)
    assert isinstance(mapped, GitHubRateLimited)
    assert mapped.retry_after == 30


async def test_request_timeout_is_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    transport = httpx.MockTransport(handler)

    class TestClient(GitHubApiClient):
        async def request(self, method, path, *, json=None, params=None):
            try:
                async with httpx.AsyncClient(
                    transport=transport, base_url="https://api.github.com"
                ) as client:
                    return await client.request(method, path, json=json, params=params)
            except httpx.TimeoutException as error:
                raise GitHubRequestTimeout() from error

    client = TestClient("token")
    with pytest.raises(GitHubRequestTimeout):
        await client.get_repository("team", "app")


async def test_github_service_requires_connection(account, session_factory) -> None:
    store = FernetCredentialStore([Fernet.generate_key().decode()])
    async with session_factory() as session:
        service = GitHubService(RelayRepository(session), store)
        with pytest.raises(GitHubNotConnected):
            await service.repository(UUID(account["id"]), "team", "app")
