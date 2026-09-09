from uuid import UUID

from app.models.entities import User
from app.repositories.relay import RelayRepository
from app.schemas.domain import PreferenceInput, PreferenceRead, ProfileInput
from app.services.audit import record


class PreferenceService:
    def __init__(self, repository: RelayRepository):
        self.repo = repository

    async def update(self, owner: UUID, data: PreferenceInput) -> PreferenceRead:
        preference = await self.repo.preferences(owner)
        for key, value in data.model_dump().items():
            setattr(preference, key, value)
        record(self.repo.session, owner, "PREFERENCES_UPDATED")
        await self.repo.session.commit()
        return PreferenceRead.model_validate(preference)

    async def profile(self, user: User, data: ProfileInput) -> None:
        user.name = data.name.strip()
        record(self.repo.session, user.id, "PROFILE_UPDATED")
        await self.repo.session.commit()

    async def finish_onboarding(self, user: User) -> None:
        await self.repo.preferences(user.id)
        if not user.onboarding_completed:
            user.onboarding_completed = True
            record(self.repo.session, user.id, "ONBOARDING_COMPLETED")
            await self.repo.session.commit()
