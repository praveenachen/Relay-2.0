from app.models.entities import UserPreference
from app.scheduling.models import (
    SchedulingPreference,
    SchedulingProblem,
    SchedulingResult,
    StudySession,
)
from app.scheduling.solver import CPSATStudyScheduler


class StudySchedulingService:
    def __init__(self, scheduler: CPSATStudyScheduler | None = None):
        self.scheduler = scheduler or CPSATStudyScheduler()

    def preference_from_user(self, preference: UserPreference) -> SchedulingPreference:
        return SchedulingPreference(
            timezone=preference.timezone,
            earliest_study_time=preference.earliest_study_time,
            latest_study_time=preference.latest_study_time,
            preferred_session_minutes=preference.preferred_session_minutes,
            maximum_session_minutes=preference.maximum_session_minutes,
            minimum_break_minutes=preference.minimum_break_minutes,
        )

    def solve(self, problem: SchedulingProblem) -> SchedulingResult:
        return self.scheduler.solve(problem)

    def regenerate_remaining(
        self, problem: SchedulingProblem, locked_sessions: tuple[StudySession, ...]
    ) -> SchedulingResult:
        return self.scheduler.solve(problem.model_copy(update={"locked_sessions": locked_sessions}))
