import asyncio
import os

import pytest
from test_application import proposed


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RELAY_TEST_DATABASE") != "1", reason="Requires PostgreSQL row locks")
async def test_concurrent_approval_resolves_once(client, account, session_factory):
    run, approvals = await proposed(client, session_factory, account)
    approval = approvals[0]

    async def approve():
        return await client.post(
            f"/approvals/{approval['id']}/approve",
            json={"approved_payload": approval["original_payload"]},
        )

    responses = await asyncio.gather(approve(), approve())
    assert sorted(response.status_code for response in responses) == [200, 409]
    events = (await client.get(f"/workflow-runs/{run['id']}/events")).json()
    assert sum(event["event_type"] == "ACTION_APPROVED" for event in events) == 1
