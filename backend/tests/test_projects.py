from conftest import login, register


async def test_project_and_member_crud(client, account):
    created = await client.post("/projects", json={"name": "Capstone", "course": "CS499"})
    assert created.status_code == 201, created.text
    project = created.json()
    assert project["name"] == "Capstone"
    assert project["notion_database_id"] is None

    updated = await client.put(
        f"/projects/{project['id']}",
        json={
            "name": "Capstone",
            "course": "CS499",
            "github_repository_owner": "team",
            "github_repository_name": "app",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["github_repository_owner"] == "team"

    listed = await client.get("/projects")
    assert len(listed.json()) == 1

    member = await client.post(
        f"/projects/{project['id']}/members",
        json={"display_name": "Sarah Chen", "github_username": "sarahc"},
    )
    assert member.status_code == 201, member.text
    member_id = member.json()["id"]

    members = await client.get(f"/projects/{project['id']}/members")
    assert len(members.json()) == 1

    edited = await client.put(
        f"/projects/{project['id']}/members/{member_id}",
        json={"display_name": "Sarah Chen", "email": "sarah@example.com"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["email"] == "sarah@example.com"
    assert edited.json()["github_username"] is None

    removed = await client.delete(f"/projects/{project['id']}/members/{member_id}")
    assert removed.status_code == 204
    assert (await client.get(f"/projects/{project['id']}/members")).json() == []


async def test_delete_project_removes_it_and_its_members(client, account):
    created = await client.post("/projects", json={"name": "Capstone"})
    project_id = created.json()["id"]
    await client.post(f"/projects/{project_id}/members", json={"display_name": "Sarah Chen"})

    deleted = await client.delete(f"/projects/{project_id}")
    assert deleted.status_code == 204

    assert (await client.get(f"/projects/{project_id}")).status_code == 404
    assert (await client.get("/projects")).json() == []


async def test_delete_project_clears_its_sources_tasks_and_proposals(client, account):
    created = await client.post("/projects", json={"name": "Capstone", "space": "SCHOOL"})
    project_id = created.json()["id"]
    captured = await client.post(
        f"/projects/{project_id}/sources",
        data={
            "source_type": "ASSIGNMENT_BRIEF",
            "title": "Design brief",
            "content": "Submit report by 2026-10-12",
        },
    )
    assert captured.status_code == 201, captured.text
    proposals_before = [
        item
        for item in (await client.get("/task-proposals")).json()
        if item["project_id"] == project_id
    ]
    assert proposals_before

    deleted = await client.delete(f"/projects/{project_id}")
    assert deleted.status_code == 204

    remaining_proposals = [
        item
        for item in (await client.get("/task-proposals")).json()
        if item["project_id"] == project_id
    ]
    assert remaining_proposals == []
    assert (await client.get(f"/projects/{project_id}")).status_code == 404


async def test_delete_project_ownership_isolation(client, account):
    created = await client.post("/projects", json={"name": "Capstone"})
    project_id = created.json()["id"]

    await client.post("/auth/logout")
    await register(client, "other-delete@example.com")
    await login(client, "other-delete@example.com")

    assert (await client.delete(f"/projects/{project_id}")).status_code == 404


async def test_project_ownership_isolation(client, account):
    created = await client.post("/projects", json={"name": "Capstone"})
    project_id = created.json()["id"]
    await client.post(f"/projects/{project_id}/members", json={"display_name": "Sarah Chen"})

    await client.post("/auth/logout")
    await register(client, "other@example.com")
    await login(client, "other@example.com")

    assert (await client.get(f"/projects/{project_id}")).status_code == 404
    assert (await client.get("/projects")).json() == []
    assert (await client.get(f"/projects/{project_id}/members")).status_code == 404
    assert (
        await client.post(f"/projects/{project_id}/members", json={"display_name": "Intruder"})
    ).status_code == 404
    assert (
        await client.put(f"/projects/{project_id}", json={"name": "Hijacked"})
    ).status_code == 404
