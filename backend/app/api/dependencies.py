from typing import Annotated

from fastapi import Depends

from app.auth.users import Session
from app.repositories.relay import RelayRepository


def repository(session: Session) -> RelayRepository:
    return RelayRepository(session)


Repository = Annotated[RelayRepository, Depends(repository)]
