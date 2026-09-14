from typing import Any

import httpx

from app.connectors.notion.errors import (
    NotionAuthorizationFailed,
    NotionDestinationNotFound,
    NotionPermissionDenied,
    NotionPublishFailed,
    NotionRateLimited,
    NotionRequestTimeout,
    NotionUnavailable,
    NotionValidationFailed,
)
from app.connectors.notion.mapper import NotionStudyPageMapper
from app.connectors.notion.schemas import (
    CreateNotionStudyPageAction,
    CreateNotionTaskAction,
    CreateNotionTaskDatabaseAction,
    ExternalArtifactResult,
    NotionBlock,
    NotionDestination,
    NotionTaskDatabaseResult,
    NotionTaskResult,
)

# Newer Notion API versions split databases into data sources; keep this
# version pinned until the connector migrates to /v1/data_sources endpoints.
NOTION_VERSION = "2022-06-28"
NOTION_MAX_PAGE_CHILDREN = 100


def retry_after(headers: httpx.Headers) -> int | None:
    value = headers.get("retry-after")
    if value and value.isdigit():
        return int(value)
    return None


def provider_error(response: httpx.Response) -> Exception:
    if response.status_code == 401:
        return NotionAuthorizationFailed()
    if response.status_code == 403:
        return NotionPermissionDenied()
    if response.status_code == 404:
        return NotionDestinationNotFound()
    if response.status_code == 429:
        return NotionRateLimited(retry_after(response.headers))
    if response.status_code in {400, 409}:
        return NotionValidationFailed()
    if response.status_code in {500, 502, 503, 504}:
        return NotionUnavailable()
    return NotionPublishFailed()


def title_from_result(result: dict[str, Any]) -> str:
    properties = result.get("properties", {})
    for value in properties.values():
        if isinstance(value, dict) and value.get("type") == "title":
            text = value.get("title", [])
            if text:
                plain = text[0].get("plain_text")
                if isinstance(plain, str) and plain.strip():
                    return plain
    return "Untitled"


def notion_rich_text(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": text}}]


def notion_block(block: NotionBlock) -> dict[str, Any]:
    if block.kind == "equation":
        return {"object": "block", "type": "equation", "equation": {"expression": block.text}}
    payload: dict[str, Any] = {
        "object": "block",
        "type": block.kind,
        block.kind: {"rich_text": notion_rich_text(block.text)},
    }
    if block.children:
        payload[block.kind]["children"] = [notion_block(child) for child in block.children]
    return payload


class NotionApiClient:
    def __init__(
        self,
        access_token: str,
        *,
        base_url: str = "https://api.notion.com",
        timeout: int = 20,
    ):
        self.access_token, self.base_url, self.timeout = access_token, base_url, timeout

    async def request(
        self, method: str, path: str, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.request(
                    method,
                    path,
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Notion-Version": NOTION_VERSION,
                        "Content-Type": "application/json",
                    },
                    json=json,
                )
        except httpx.TimeoutException as error:
            raise NotionRequestTimeout() from error
        except httpx.HTTPError as error:
            raise NotionUnavailable() from error
        if response.status_code >= 400:
            raise provider_error(response)
        data = response.json()
        return data if isinstance(data, dict) else {}

    async def search_pages(self) -> list[NotionDestination]:
        results: list[NotionDestination] = []
        cursor: str | None = None
        while True:
            payload: dict[str, Any] = {
                "page_size": 100,
                "filter": {"property": "object", "value": "page"},
            }
            if cursor:
                payload["start_cursor"] = cursor
            data = await self.request("POST", "/v1/search", payload)
            for item in data.get("results", []):
                if (
                    item.get("object") == "page"
                    and isinstance(item.get("id"), str)
                    and item.get("parent", {}).get("type") not in {"database_id", "data_source_id"}
                    and not item.get("archived")
                    and not item.get("in_trash")
                ):
                    results.append(
                        NotionDestination(
                            id=item["id"],
                            title=title_from_result(item),
                            object_type="page",
                        )
                    )
            cursor = data.get("next_cursor") if data.get("has_more") else None
            if not cursor:
                return results

    async def search_databases(self) -> list[NotionDestination]:
        """Existing databases the connection can see -- used only by
        Collaborate's project setup to pick a database to sync action items
        into. A database's title is a top-level rich_text array, unlike a
        page's title *property*, so this can't reuse title_from_result()."""
        results: list[NotionDestination] = []
        cursor: str | None = None
        while True:
            payload: dict[str, Any] = {
                "page_size": 100,
                "filter": {"property": "object", "value": "database"},
            }
            if cursor:
                payload["start_cursor"] = cursor
            data = await self.request("POST", "/v1/search", payload)
            for item in data.get("results", []):
                if item.get("object") == "database" and isinstance(item.get("id"), str):
                    title_parts = item.get("title", [])
                    title = "".join(
                        part.get("plain_text", "") for part in title_parts if isinstance(part, dict)
                    ).strip()
                    results.append(
                        NotionDestination(
                            id=item["id"],
                            title=title or "Untitled database",
                            object_type="database",
                        )
                    )
            cursor = data.get("next_cursor") if data.get("has_more") else None
            if not cursor:
                return results

    async def create_page(
        self, parent_page_id: str, title: str, blocks: list[NotionBlock]
    ) -> dict[str, Any]:
        return await self.request(
            "POST",
            "/v1/pages",
            {
                "parent": {"page_id": parent_page_id},
                "properties": {"title": {"title": notion_rich_text(title[:1900])}},
                "children": [notion_block(block) for block in blocks],
            },
        )

    async def get_database(self, database_id: str) -> dict[str, Any]:
        return await self.request("GET", f"/v1/databases/{database_id}")

    async def create_database(
        self, parent_page_id: str, title: str, properties: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.request(
            "POST",
            "/v1/databases",
            {
                "parent": {"page_id": parent_page_id},
                # Unlike a page's title *property* ({"title": {"title": [...]}}),
                # a database's own title is a top-level rich_text array.
                "title": notion_rich_text(title[:1900]),
                "properties": properties,
            },
        )

    async def create_database_page(
        self,
        database_id: str,
        properties: dict[str, Any],
        blocks: list[NotionBlock] | None = None,
    ) -> dict[str, Any]:
        return await self.request(
            "POST",
            "/v1/pages",
            {
                "parent": {"database_id": database_id},
                "properties": properties,
                "children": [notion_block(block) for block in blocks or []],
            },
        )


class RealNotionConnector:
    def __init__(self, client: NotionApiClient):
        self.client = client

    async def create_study_page(
        self,
        action: CreateNotionStudyPageAction,
        idempotency_key: str,
    ) -> ExternalArtifactResult:
        if not action.parent_destination_id:
            raise NotionDestinationNotFound()
        blocks = NotionStudyPageMapper().map(action.content.summary)
        marker = NotionBlock(kind="paragraph", text=f"Relay action: {idempotency_key}")
        page_blocks = blocks[: NOTION_MAX_PAGE_CHILDREN - 1]
        result = await self.client.create_page(
            action.parent_destination_id,
            action.title,
            [marker, *page_blocks],
        )
        page_id = result.get("id")
        page_url = result.get("url")
        if not isinstance(page_id, str) or not isinstance(page_url, str):
            raise NotionPublishFailed()
        return ExternalArtifactResult(
            external_id=page_id,
            external_url=page_url,
            title=action.title,
            workspace_id=action.workspace_id,
            workspace_name=action.workspace_name,
            destination_id=action.parent_destination_id,
            destination_title=action.parent_destination_title,
            blocks=blocks,
        )

    async def create_task(
        self,
        action: CreateNotionTaskAction,
        idempotency_key: str,
    ) -> NotionTaskResult:
        marker = NotionBlock(kind="paragraph", text=f"Relay action: {idempotency_key}")
        result = await self.client.create_database_page(
            action.database_id,
            action.properties,
            [marker, *action.body_blocks],
        )
        page_id = result.get("id")
        page_url = result.get("url")
        if not isinstance(page_id, str) or not isinstance(page_url, str):
            raise NotionPublishFailed()
        return NotionTaskResult(external_id=page_id, external_url=page_url, title=action.title)

    async def create_task_database(
        self,
        action: CreateNotionTaskDatabaseAction,
        idempotency_key: str,
    ) -> NotionTaskDatabaseResult:
        database = await self.client.create_database(
            action.parent_page_id, action.title, action.properties
        )
        database_id = database.get("id")
        database_url = database.get("url")
        if not isinstance(database_id, str) or not isinstance(database_url, str):
            raise NotionPublishFailed()
        for row in action.rows:
            marker = NotionBlock(kind="paragraph", text=f"Relay action: {idempotency_key}")
            page = await self.client.create_database_page(database_id, row, [marker])
            if not isinstance(page.get("id"), str) or not isinstance(page.get("url"), str):
                raise NotionPublishFailed()
        return NotionTaskDatabaseResult(
            external_id=database_id,
            external_url=database_url,
            title=action.title,
            task_count=len(action.rows),
        )
