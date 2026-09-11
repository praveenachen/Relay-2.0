from uuid import UUID

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select

from app.connectors.notion import (
    CreateNotionStudyPageAction,
    MockNotionConnector,
    NotionApiClient,
    NotionAuthorizationFailed,
    NotionDestinationService,
    NotionOAuthClient,
    NotionOAuthService,
    NotionStudyPageMapper,
    NotionValidationFailed,
)
from app.connectors.notion.mapper import chunks
from app.domain.enums import Provider
from app.infrastructure.credentials import FernetCredentialStore
from app.models.entities import ConnectedAccount, NotionDestinationRecord
from app.repositories.relay import RelayRepository
from app.workflows.lecture_notes.schemas import (
    Definition,
    Formula,
    KeyConcept,
    LectureSummary,
    SummarySection,
    QuizQuestion,
)


def summary() -> LectureSummary:
    return LectureSummary(
        title="Week 7 - Eigenvalues",
        overview="Eigenvalues describe scaling behavior.",
        key_concepts=[KeyConcept(name="Eigenvalue", explanation="A scalar scaling factor.")],
        sections=[SummarySection(heading="Diagonalization", text="Use bases of eigenvectors.")],
        definitions=[Definition(term="Vector", definition="Magnitude and direction.")],
        formulas=[Formula(expression="Av = lambda v", description="Eigenvector equation.")],
        takeaways=["Eigenvectors keep their direction."],
        review_questions=["How do eigenvalues change under diagonalization?"],
        quiz_questions=[
            QuizQuestion(
                question="What does an eigenvalue describe?",
                answer="It describes the scalar scaling behavior of an eigenvector.",
            )
        ],
    )


def action() -> CreateNotionStudyPageAction:
    return CreateNotionStudyPageAction(
        title="Week 7 - Eigenvalues",
        connection_id=str(UUID(int=7)),
        parent_destination_id="page-1",
        parent_destination_title="University Notes",
        workspace_id="workspace-1",
        workspace_name="Student Workspace",
        content={"summary": summary()},
    )


def test_notion_oauth_token_accepts_response_metadata() -> None:
    from app.connectors.notion.schemas import NotionOAuthToken

    token = NotionOAuthToken.model_validate(
        {
            "access_token": "secret-access",
            "refresh_token": "secret-refresh",
            "bot_id": "bot-1",
            "workspace_id": "workspace-1",
            "workspace_name": "Student Workspace",
            "owner": {"type": "user", "user": {"id": "owner-1"}},
            "token_type": "bearer",
            "request_id": "636b4ac3-2ba8-40c7-9b04-c28e5e059aee",
        }
    )

    assert token.access_token == "secret-access"
    assert token.workspace_id == "workspace-1"


def test_mapper_orders_sections_and_splits_long_text():
    mapped = NotionStudyPageMapper().map(summary().model_copy(update={"overview": "word " * 900}))
    assert [block.kind for block in mapped][:4] == [
        "heading_1",
        "paragraph",
        "paragraph",
        "paragraph",
    ]
    assert all(len(block.text) <= 1900 for block in mapped)
    assert [block.text for block in mapped if block.kind == "heading_2"] == [
        "Notes",
        "Diagonalization",
        "Key Concepts",
        "Definitions",
        "Formulas / Equations",
        "Takeaways",
        "Mini Lecture Quiz",
    ]
    assert any(block.kind == "equation" and block.text == "Av = lambda v" for block in mapped)
    assert any(
        block.kind == "toggle" and block.text == "What does an eigenvalue describe?"
        for block in mapped
    )
    assert chunks("x" * 2001) == ["x" * 1900, "x" * 101]


async def test_mock_and_real_connector_contracts():
    mock_result = await MockNotionConnector().create_study_page(action(), "relay:1")
    assert mock_result.external_url.startswith("mock://")
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = request.read().decode()
        return httpx.Response(
            200,
            json={"id": "page-created", "url": "https://notion.so/page-created"},
        )

    transport = httpx.MockTransport(handler)

    class TestClient(NotionApiClient):
        async def request(self, method, path, json):
            async with httpx.AsyncClient(
                transport=transport, base_url="https://api.notion.com"
            ) as client:
                response = await client.request(method, path, json=json)
            return response.json()

    from app.connectors.notion import RealNotionConnector

    real_result = await RealNotionConnector(TestClient("token")).create_study_page(
        action(), "relay:1"
    )
    assert real_result.external_id == "page-created"
    assert "Relay action: relay:1" in captured["payload"]


async def test_real_connector_maps_provider_errors():
    class FailingClient(NotionApiClient):
        async def create_page(self, parent_page_id, title, blocks):
            raise NotionValidationFailed()

    from app.connectors.notion import RealNotionConnector

    with pytest.raises(NotionValidationFailed):
        await RealNotionConnector(FailingClient("token")).create_study_page(action(), "relay:1")


async def test_oauth_state_exchange_encrypts_tokens(client, account, session_factory):
    store = FernetCredentialStore([Fernet.generate_key().decode()])
    token = {
        "access_token": "secret-access",
        "refresh_token": "secret-refresh",
        "bot_id": "bot-1",
        "workspace_id": "workspace-1",
        "workspace_name": "Student Workspace",
        "workspace_icon": None,
        "owner": {"type": "user", "user": {"id": "owner-1"}},
        "duplicated_template_id": None,
    }
    async with session_factory() as session:
        service = NotionOAuthService(
            RelayRepository(session),
            NotionOAuthClient(
                "client",
                "secret",
                "https://relay.test/connections/NOTION/callback",
                token_url="https://api.notion.test/v1/oauth/token",
            ),
            store,
        )
        started = await service.start(UUID(account["id"]))
        state = started["authorization_url"].split("state=")[1]

        async def exchange(code):
            assert code == "code-1"
            from app.connectors.notion.schemas import NotionOAuthToken

            return NotionOAuthToken.model_validate(token)

        service.oauth.exchange_code = exchange
        connected = await service.callback(
            UUID(account["id"]), state=state, code="code-1", error=None
        )
        assert connected.display_name == "Student Workspace"
        stored = await session.get(ConnectedAccount, connected.id)
        assert stored.access_token_encrypted != "secret-access"
        assert store.decrypt(stored.access_token_encrypted) == "secret-access"
        assert stored.provider_metadata["bot_id"] == "bot-1"
        with pytest.raises(NotionAuthorizationFailed):
            await service.callback(UUID(account["id"]), state=state, code="code-1", error=None)


async def test_destination_discovery_paginates_and_selects(account, session_factory):
    store = FernetCredentialStore([Fernet.generate_key().decode()])
    async with session_factory() as session:
        connection = ConnectedAccount(
            user_id=UUID(account["id"]),
            provider=Provider.NOTION,
            external_account_id="workspace-1",
            display_name="Student Workspace",
            access_token_encrypted=store.encrypt("notion-token"),
            scopes=["read_content", "insert_content"],
            provider_metadata={"workspace_id": "workspace-1"},
            status="CONNECTED",
        )
        session.add(connection)
        await session.commit()

        calls = 0

        class PagedClient(NotionApiClient):
            async def search_pages(self):
                nonlocal calls
                calls += 1
                from app.connectors.notion import NotionDestination

                return [
                    NotionDestination(id="page-1", title="University Notes"),
                    NotionDestination(id="page-2", title="Archive"),
                ]

        class Service(NotionDestinationService):
            async def client(self, connection):
                return PagedClient("token")

        service = Service(RelayRepository(session), store)
        refreshed = await service.refresh(UUID(account["id"]))
        assert [item.title for item in refreshed] == ["Archive", "University Notes"]
        assert calls == 1
        selected = await service.select(UUID(account["id"]), "page-1")
        assert selected.title == "University Notes"
        assert (
            await session.scalar(select(func.count()).select_from(NotionDestinationRecord))
        ) == 2


async def test_notion_http_search_paginates():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.read().decode())
        if len(calls) == 1:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"object": "page", "id": "page-1", "properties": {}},
                    ],
                    "has_more": True,
                    "next_cursor": "cursor-2",
                },
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {"object": "page", "id": "page-2", "properties": {}},
                ],
                "has_more": False,
            },
        )

    transport = httpx.MockTransport(handler)

    class TestClient(NotionApiClient):
        async def request(self, method, path, json):
            async with httpx.AsyncClient(
                transport=transport, base_url="https://api.notion.com"
            ) as client:
                response = await client.request(method, path, json=json)
            return response.json()

    assert [item.id for item in await TestClient("token").search_pages()] == ["page-1", "page-2"]
    assert '"start_cursor":"cursor-2"' in calls[1].replace(" ", "")
