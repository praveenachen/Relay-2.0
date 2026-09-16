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
    NotionRichText,
    NotionTaskDatabaseResult,
    NotionTaskResult,
    PublishNotionProjectAction,
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
    return notion_rich_text_items([NotionRichText(text=text)])


def notion_rich_text_items(items: list[NotionRichText]) -> list[dict[str, Any]]:
    return [
        {
            "type": "text",
            "text": {
                "content": item.text,
                "link": {"url": item.href} if item.href else None,
            },
            "annotations": {
                "bold": item.bold,
                "italic": item.italic,
                "strikethrough": False,
                "underline": False,
                "code": False,
                "color": item.color,
            },
        }
        for item in items
    ]


def notion_block(block: NotionBlock) -> dict[str, Any]:
    if block.kind == "equation":
        return {"object": "block", "type": "equation", "equation": {"expression": block.text}}
    if block.kind == "divider":
        return {"object": "block", "type": "divider", "divider": {}}
    rich_text = (
        notion_rich_text_items(block.rich_text) if block.rich_text else notion_rich_text(block.text)
    )
    payload: dict[str, Any] = {
        "object": "block",
        "type": block.kind,
        block.kind: {"rich_text": rich_text, "color": block.color},
    }
    if block.kind == "callout":
        payload[block.kind]["icon"] = {
            "type": "emoji",
            "emoji": block.icon_emoji or "📌",
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
        self,
        parent_page_id: str,
        title: str,
        blocks: list[NotionBlock],
        *,
        icon_emoji: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "parent": {"page_id": parent_page_id},
            "properties": {"title": {"title": notion_rich_text(title[:1900])}},
            "children": [notion_block(block) for block in blocks],
        }
        if icon_emoji:
            payload["icon"] = {"type": "emoji", "emoji": icon_emoji}
        return await self.request("POST", "/v1/pages", payload)

    async def block_children(self, block_id: str) -> list[dict[str, Any]]:
        cursor: str | None = None
        children: list[dict[str, Any]] = []
        while True:
            suffix = f"?page_size=100&start_cursor={cursor}" if cursor else "?page_size=100"
            data = await self.request("GET", f"/v1/blocks/{block_id}/children{suffix}")
            children.extend(item for item in data.get("results", []) if isinstance(item, dict))
            cursor = data.get("next_cursor") if data.get("has_more") else None
            if not cursor:
                return children

    @staticmethod
    def block_text(block: dict[str, Any]) -> str:
        value = block.get(str(block.get("type")), {})
        return "".join(
            str(part.get("plain_text") or part.get("text", {}).get("content") or "")
            for part in value.get("rich_text", [])
            if isinstance(part, dict)
        )

    async def replace_page(
        self,
        page_id: str,
        title: str,
        blocks: list[NotionBlock],
        *,
        icon_emoji: str | None = None,
        legacy_blocks: tuple[NotionBlock, ...] = (),
    ) -> dict[str, Any]:
        page_payload: dict[str, Any] = {
            "properties": {"title": {"title": notion_rich_text(title[:1900])}}
        }
        if icon_emoji:
            page_payload["icon"] = {"type": "emoji", "emoji": icon_emoji}
        page = await self.request(
            "PATCH",
            f"/v1/pages/{page_id}",
            page_payload,
        )
        children = await self.block_children(page_id)
        managed = next(
            (
                child
                for child in children
                if child.get("type") == "callout"
                and self.block_text(child).startswith("Relay snapshot ·")
            ),
            None,
        )
        if managed is not None and blocks and blocks[0].kind == "callout":
            managed_id = managed.get("id")
            if isinstance(managed_id, str):
                replacement = notion_block(blocks[0])["callout"]
                nested = replacement.pop("children", [])
                await self.request("PATCH", f"/v1/blocks/{managed_id}", {"callout": replacement})
                for child in await self.block_children(managed_id):
                    child_id = child.get("id")
                    if isinstance(child_id, str):
                        await self.request("DELETE", f"/v1/blocks/{child_id}")
                if nested:
                    await self.request(
                        "PATCH",
                        f"/v1/blocks/{managed_id}/children",
                        {"children": nested},
                    )
                return page

        # Migrate pages produced by the original Relay publisher without
        # deleting user-authored additions. Remove the internal marker and
        # only blocks that still exactly match the previously approved Relay
        # snapshot; edited or unrelated blocks remain outside the new managed
        # callout.
        expected: list[tuple[str, str]] = [(block.kind, block.text) for block in legacy_blocks]
        for child in children:
            child_id = child.get("id")
            signature = (str(child.get("type")), self.block_text(child))
            generated = signature in expected
            if generated:
                expected.remove(signature)
            if isinstance(child_id, str) and (
                self.block_text(child).startswith("Relay action:") or generated
            ):
                await self.request("DELETE", f"/v1/blocks/{child_id}")
        if blocks:
            await self.request(
                "PATCH",
                f"/v1/blocks/{page_id}/children",
                {"children": [notion_block(block) for block in blocks]},
            )
        return page

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

    async def publish_project(
        self,
        action: PublishNotionProjectAction,
        idempotency_key: str,
    ) -> ExternalArtifactResult:
        blocks = list(action.blocks[:NOTION_MAX_PAGE_CHILDREN])
        if action.existing_page_id:
            result = await self.client.replace_page(
                action.existing_page_id,
                action.title,
                blocks,
                icon_emoji=action.icon_emoji,
                legacy_blocks=action.legacy_blocks,
            )
            page_id_result: object = action.existing_page_id
            page_url_result: object = result.get("url") or action.existing_page_url
        else:
            result = await self.client.create_page(
                action.parent_destination_id,
                action.title,
                blocks,
                icon_emoji=action.icon_emoji,
            )
            page_id_result = result.get("id")
            page_url_result = result.get("url")
        if not isinstance(page_id_result, str) or not isinstance(page_url_result, str):
            raise NotionPublishFailed()
        return ExternalArtifactResult(
            external_id=page_id_result,
            external_url=page_url_result,
            title=action.title,
            destination_id=action.parent_destination_id,
            destination_title=action.parent_destination_title,
            blocks=list(action.blocks),
        )

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
