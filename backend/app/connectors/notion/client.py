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
    ExternalArtifactResult,
    NotionBlock,
    NotionDestination,
)

NOTION_VERSION = "2026-03-11"


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
    return {
        "object": "block",
        "type": block.kind,
        block.kind: {"rich_text": notion_rich_text(block.text)},
    }


class NotionApiClient:
    def __init__(
        self,
        access_token: str,
        *,
        base_url: str = "https://api.notion.com",
        timeout: int = 20,
    ):
        self.access_token, self.base_url, self.timeout = access_token, base_url, timeout

    async def request(self, method: str, path: str, json: dict[str, Any]) -> dict[str, Any]:
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
                if item.get("object") == "page" and isinstance(item.get("id"), str):
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
        result = await self.client.create_page(
            action.parent_destination_id,
            action.title,
            [marker, *blocks],
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
