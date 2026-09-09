from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, exceptions, schemas
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy.db import DatabaseStrategy
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from pydantic import Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.models.entities import AccessToken, User, UserPreference
from app.services.audit import record

Session = Annotated[AsyncSession, Depends(get_session)]


class UserRead(schemas.BaseUser[UUID]):
    name: str
    avatar_url: str | None
    onboarding_completed: bool


class UserCreate(schemas.BaseUserCreate):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name cannot be blank")
        return value.strip()


class UserDatabase(SQLAlchemyUserDatabase[User, UUID]):
    async def create(self, create_dict: dict[str, Any]) -> User:
        # The library manages hashing; this adapter makes account, defaults and audit atomic.
        create_dict["email"] = str(create_dict["email"]).lower()
        user = User(**create_dict)
        self.session.add(user)
        try:
            await self.session.flush()
            self.session.add(UserPreference(user_id=user.id))
            record(self.session, user.id, "USER_CREATED")
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise exceptions.UserAlreadyExists() from None
        await self.session.refresh(user)
        return user


async def get_user_db(session: Session) -> AsyncIterator[UserDatabase]:
    yield UserDatabase(session, User)


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    async def validate_password(self, password: str, user: schemas.BaseUserCreate | User) -> None:
        if len(password) < 12 or len(password) > 128:
            raise exceptions.InvalidPasswordException(
                reason="Use a password of 12 to 128 characters."
            )


async def get_user_manager(
    database: Annotated[UserDatabase, Depends(get_user_db)],
) -> AsyncIterator[UserManager]:
    yield UserManager(database)


async def get_strategy(session: Session) -> DatabaseStrategy[User, UUID, AccessToken]:
    return DatabaseStrategy(
        SQLAlchemyAccessTokenDatabase(session, AccessToken),
        lifetime_seconds=get_settings().session_lifetime_seconds,
    )


cookie_transport = CookieTransport(
    cookie_name="relay_session",
    cookie_max_age=get_settings().session_lifetime_seconds,
    cookie_secure=get_settings().cookie_secure,
    cookie_httponly=True,
    cookie_samesite="lax",
)
backend = AuthenticationBackend(
    name="cookie", transport=cookie_transport, get_strategy=get_strategy
)
users = FastAPIUsers[User, UUID](get_user_manager, [backend])
current_user = users.current_user(active=True)
CurrentUser = Annotated[User, Depends(current_user)]
