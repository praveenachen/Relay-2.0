from uuid import uuid4

from app.workflows.project_meeting.identity import member_by_id, resolve_identity


class FakeMember:
    def __init__(self, display_name: str, github_username: str | None = None):
        self.id = uuid4()
        self.display_name = display_name
        self.github_username = github_username


def test_exact_match_resolves():
    members = [FakeMember("Sarah Chen"), FakeMember("Alex Kim")]
    result = resolve_identity("Sarah Chen", members)
    assert result.status == "resolved"
    assert result.member_id == str(members[0].id)


def test_first_name_match_resolves_when_unambiguous():
    members = [FakeMember("Sarah Chen"), FakeMember("Alex Kim")]
    result = resolve_identity("Sarah", members)
    assert result.status == "resolved"
    assert result.member_id == str(members[0].id)


def test_ambiguous_first_name_requires_user_selection():
    members = [FakeMember("Sarah Chen"), FakeMember("Sarah Lopez")]
    result = resolve_identity("Sarah", members)
    assert result.status == "ambiguous"
    assert {c.id for c in result.candidates} == {str(m.id) for m in members}


def test_unknown_member_is_unresolved_not_guessed():
    members = [FakeMember("Sarah Chen")]
    result = resolve_identity("Priya", members)
    assert result.status == "unresolved"
    assert result.member_id is None


def test_missing_owner_name_is_unspecified():
    result = resolve_identity(None, [FakeMember("Sarah Chen")])
    assert result.status == "unspecified"


def test_resolved_member_without_github_username_is_not_auto_assigned():
    member = FakeMember("Sarah Chen", github_username=None)
    result = resolve_identity("Sarah Chen", [member])
    assert result.status == "resolved"
    resolved_member = member_by_id([member], result.member_id)
    assert resolved_member is not None
    assert resolved_member.github_username is None


def test_member_by_id_returns_none_for_missing_id():
    assert member_by_id([FakeMember("Sarah Chen")], None) is None
    assert member_by_id([FakeMember("Sarah Chen")], str(uuid4())) is None
