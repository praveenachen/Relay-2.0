"""ORM safeguards for append-only audit and resolved approval records."""

from typing import Any

from sqlalchemy import event, inspect

from app.domain.enums import ApprovalStatus
from app.domain.errors import ApprovalAlreadyResolved, DomainError
from app.models.entities import ApprovalRequest, AuditEvent


@event.listens_for(AuditEvent, "before_update")
@event.listens_for(AuditEvent, "before_delete")
def immutable_audit(mapper: Any, connection: Any, target: AuditEvent) -> None:
    raise DomainError()


@event.listens_for(ApprovalRequest, "before_update")
def immutable_resolution(mapper: Any, connection: Any, target: ApprovalRequest) -> None:
    history = inspect(target).attrs.status.history
    previous = history.deleted[0] if history.deleted else target.status
    if previous != ApprovalStatus.PENDING:
        raise ApprovalAlreadyResolved()
