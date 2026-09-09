from typing import Literal

from app.models.entities import ProjectMember
from app.workflows.lecture_notes.schemas import StrictModel

ResolutionStatus = Literal["resolved", "ambiguous", "unresolved", "unspecified"]


class MemberCandidate(StrictModel):
    id: str
    display_name: str


class IdentityResolution(StrictModel):
    status: ResolutionStatus
    owner_name: str | None
    member_id: str | None = None
    candidates: tuple[MemberCandidate, ...] = ()


def resolve_identity(owner_name: str | None, members: list[ProjectMember]) -> IdentityResolution:
    """Never guesses: an exact (case-insensitive) match on the full display
    name or its first token resolves; more than one match is ambiguous and
    must be picked by the user; no match leaves it unresolved. A transcript
    name is never assumed to equal a GitHub username or Notion identity --
    those live on the resolved ProjectMember, applied by the caller."""
    if not owner_name or not owner_name.strip():
        return IdentityResolution(status="unspecified", owner_name=owner_name)
    needle = owner_name.strip().lower()
    exact = [member for member in members if member.display_name.strip().lower() == needle]
    if len(exact) == 1:
        return IdentityResolution(
            status="resolved", owner_name=owner_name, member_id=str(exact[0].id)
        )
    if len(exact) > 1:
        return _ambiguous(owner_name, exact)
    first_name_matches = [
        member for member in members if member.display_name.strip().lower().split(" ")[0] == needle
    ]
    if len(first_name_matches) == 1:
        return IdentityResolution(
            status="resolved", owner_name=owner_name, member_id=str(first_name_matches[0].id)
        )
    if len(first_name_matches) > 1:
        return _ambiguous(owner_name, first_name_matches)
    return IdentityResolution(status="unresolved", owner_name=owner_name)


def _ambiguous(owner_name: str, matches: list[ProjectMember]) -> IdentityResolution:
    return IdentityResolution(
        status="ambiguous",
        owner_name=owner_name,
        candidates=tuple(
            MemberCandidate(id=str(member.id), display_name=member.display_name)
            for member in matches
        ),
    )


def member_by_id(members: list[ProjectMember], member_id: str | None) -> ProjectMember | None:
    if not member_id:
        return None
    for member in members:
        if str(member.id) == member_id:
            return member
    return None
