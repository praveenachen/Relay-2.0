from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.runtime.client import ExecutionSnapshot, ExecutionStatus
from app.runtime.local import LocalRuntimeClient


@pytest.fixture(autouse=True)
def use_fake_language_model():
    settings = get_settings()
    previous = settings.language_model_provider
    settings.language_model_provider = "fake"
    yield
    settings.language_model_provider = previous


async def create_project(client, *, space="SCHOOL"):
    response = await client.post(
        "/projects", json={"name": f"{space.title()} project", "space": space}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def capture(client, project, source_type, content, title="Source"):
    response = await client.post(
        f"/projects/{project['id']}/sources",
        data={"source_type": source_type, "title": title, "content": content},
    )
    assert response.status_code == 201, response.text
    proposals = (await client.get("/task-proposals")).json()
    return response.json(), [
        item
        for item in proposals
        if item["source_id"] == response.json()["id"]
    ]


async def test_work_transcript_extracts_current_user_action(client, account):
    project = await create_project(client, space="WORK")
    source, proposals = await capture(
        client,
        project,
        "MEETING_TRANSCRIPT",
        "Student: I will prepare the launch checklist.\nAlex: I will update the API.",
        "Launch meeting",
    )
    assert source["status"] == "READY"
    assert len(proposals) == 1
    assert proposals[0]["proposal"]["owner"] == "Student"
    assert "launch checklist" in proposals[0]["proposal"]["title"].lower()
    assert "due_date" in proposals[0]["proposal"]["needs_confirmation"]


@pytest.mark.parametrize(
    ("source_type", "content", "expected"),
    [
        (
            "ASSIGNMENT_BRIEF",
            "Deliverable: Submit design report by 2026-10-12",
            "design report",
        ),
        (
            "COURSE_OUTLINE",
            "Lecture 1: Intro\nMidterm exam 2026-10-20\nLecture 2: Review",
            "midterm",
        ),
        (
            "STUDY_GOAL",
            "Prepare for SYDE 223 Midterm",
            "SYDE 223",
        ),
    ],
)
async def test_school_source_types_create_typed_proposals(
    client, account, source_type, content, expected
):
    project = await create_project(client)
    _, proposals = await capture(client, project, source_type, content)
    assert proposals
    assert any(expected.lower() in item["proposal"]["title"].lower() for item in proposals)
    if source_type != "STUDY_GOAL":
        assert proposals[0]["proposal"]["due_date"] is not None


async def test_personal_goal_creates_small_practical_set(client, account):
    project = await create_project(client, space="PERSONAL")
    _, proposals = await capture(
        client, project, "PERSONAL_GOAL", "Prepare for my first 10K"
    )
    assert 2 <= len(proposals) <= 6
    assert all(item["proposal"]["needs_confirmation"] for item in proposals)


async def test_reject_proposal_creates_no_task(client, account):
    project = await create_project(client)
    _, proposals = await capture(
        client, project, "ASSIGNMENT_BRIEF", "Submit report by 2026-10-12"
    )
    response = await client.post(
        f"/task-proposals/{proposals[0]['approval_id']}/reject"
    )
    assert response.status_code == 200
    assert (await client.get(f"/projects/{project['id']}/tasks")).json() == []


async def test_edit_accept_runtime_creation_and_source_provenance(client, account):
    project = await create_project(client)
    source, proposals = await capture(
        client,
        project,
        "ASSIGNMENT_BRIEF",
        "Submit the final design report by 2026-10-12",
        "Design brief",
    )
    item = proposals[0]
    payload = {
        **item["proposal"],
        "title": "Draft the final design report",
        "needs_confirmation": [],
    }
    edited = await client.put(
        f"/task-proposals/{item['approval_id']}", json=payload
    )
    assert edited.status_code == 200, edited.text
    accepted = await client.post(
        f"/task-proposals/{item['approval_id']}/accept", json=payload
    )
    assert accepted.status_code == 200, accepted.text
    tasks = (await client.get(f"/projects/{project['id']}/tasks")).json()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Draft the final design report"
    assert tasks[0]["source_id"] == source["id"]
    assert tasks[0]["source_title"] == "Design brief"
    assert tasks[0]["source_reference"]


async def test_resubmit_is_idempotent(client, account):
    project = await create_project(client)
    _, proposals = await capture(
        client, project, "ASSIGNMENT_BRIEF", "Submit report by 2026-10-12"
    )
    item = proposals[0]
    payload = {**item["proposal"], "needs_confirmation": []}
    first = await client.post(
        f"/task-proposals/{item['approval_id']}/accept", json=payload
    )
    second = await client.post(
        f"/task-proposals/{item['approval_id']}/accept", json=payload
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert len((await client.get(f"/projects/{project['id']}/tasks")).json()) == 1


async def test_runtime_failure_creates_no_task(client, account, monkeypatch):
    project = await create_project(client)
    _, proposals = await capture(
        client, project, "ASSIGNMENT_BRIEF", "Submit report by 2026-10-12"
    )
    item = proposals[0]
    payload = {**item["proposal"], "needs_confirmation": []}

    async def fail(self, request):
        return ExecutionSnapshot(
            execution_id=uuid4(),
            status=ExecutionStatus.FAILED,
            error_code="SIMULATED_FAILURE",
            submitted_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )

    monkeypatch.setattr(LocalRuntimeClient, "submit_execution", fail)
    response = await client.post(
        f"/task-proposals/{item['approval_id']}/accept", json=payload
    )
    assert response.status_code == 502
    assert response.json()["message"] == "Relay couldn't create the selected task. Please retry."
    assert (await client.get(f"/projects/{project['id']}/tasks")).json() == []


async def test_explicit_month_name_date_is_extracted(client, account):
    project = await create_project(client, space="WORK")
    _, proposals = await capture(
        client, project, "DOCUMENT_BRIEF", "Freeze scope by Sep 30, 2026"
    )
    assert proposals
    due = proposals[0]["proposal"]["due_date"]
    assert due is not None and due.startswith("2026-09-30")
    assert "due_date" not in proposals[0]["proposal"]["needs_confirmation"]


async def test_vague_timing_does_not_invent_a_due_date(client, account):
    project = await create_project(client, space="WORK")
    _, proposals = await capture(
        client, project, "DOCUMENT_BRIEF", "Let's tackle this when you have time."
    )
    assert proposals
    assert proposals[0]["proposal"]["due_date"] is None
    assert "due_date" in proposals[0]["proposal"]["needs_confirmation"]


async def test_relative_deadline_phrase_extracts_the_stated_date_not_an_offset(
    client, account
):
    project = await create_project(client, space="WORK")
    _, proposals = await capture(
        client, project, "DOCUMENT_BRIEF", "Finish the deck before Demo Day on Oct 3."
    )
    assert proposals
    due = proposals[0]["proposal"]["due_date"]
    assert due is not None
    # Must resolve to the explicit Oct 3, never an invented "day before" (Oct 2).
    assert due[5:10] == "10-03"


async def test_duplicate_proposal_flagged_across_sources_with_different_filenames(
    client, account
):
    project = await create_project(client)
    content = "Submit the final design report by 2026-10-12"
    _, first_proposals = await capture(
        client, project, "ASSIGNMENT_BRIEF", content, title="Design brief v1.pdf"
    )
    assert first_proposals
    assert first_proposals[0]["proposal"]["possible_duplicate"] is False

    _, second_proposals = await capture(
        client,
        project,
        "ASSIGNMENT_BRIEF",
        content,
        title="Design brief v1 (copy).pdf",
    )
    assert second_proposals
    assert second_proposals[0]["proposal"]["possible_duplicate"] is True
    assert (
        second_proposals[0]["proposal"]["duplicate_of_title"]
        == first_proposals[0]["proposal"]["title"]
    )

    all_pending = (await client.get("/task-proposals")).json()
    assert any(item["proposal"]["possible_duplicate"] for item in all_pending)


async def test_duplicate_detection_is_scoped_to_the_same_project(client, account):
    project_a = await create_project(client)
    project_b = await create_project(client)
    content = "Submit the final design report by 2026-10-12"
    _, proposals_a = await capture(client, project_a, "ASSIGNMENT_BRIEF", content)
    _, proposals_b = await capture(client, project_b, "ASSIGNMENT_BRIEF", content)
    assert proposals_a[0]["proposal"]["possible_duplicate"] is False
    assert proposals_b[0]["proposal"]["possible_duplicate"] is False


async def test_history_reset_clears_source_tasks_and_proposals(client, account):
    project = await create_project(client)
    _, proposals = await capture(
        client, project, "ASSIGNMENT_BRIEF", "Submit report by 2026-10-12"
    )
    item = proposals[0]
    payload = {**item["proposal"], "needs_confirmation": []}
    accepted = await client.post(
        f"/task-proposals/{item['approval_id']}/accept", json=payload
    )
    assert accepted.status_code == 200

    reset = await client.post("/users/me/history/reset")

    assert reset.status_code == 204, reset.text
    assert (await client.get("/projects")).json() == []
    assert (await client.get("/task-proposals")).json() == []
