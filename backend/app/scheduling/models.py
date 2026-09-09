from datetime import datetime, time
from enum import StrEnum
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SchedulingStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"


class StrictSchedulingModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AcademicTask(StrictSchedulingModel):
    id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    course: str | None = Field(default=None, max_length=120)
    deadline: datetime
    estimated_minutes: int = Field(gt=0, le=100_000)
    priority: int = Field(default=3, ge=1, le=5)
    status: str = Field(default="todo", max_length=80)

    @model_validator(mode="after")
    def require_aware_deadline(self) -> "AcademicTask":
        if self.deadline.tzinfo is None or self.deadline.utcoffset() is None:
            raise ValueError("deadline must be timezone-aware")
        return self


class StudyRequirement(StrictSchedulingModel):
    task_id: str
    remaining_minutes: int = Field(ge=0)
    deadline: datetime
    priority: int = Field(ge=1, le=5)


class AvailabilityWindow(StrictSchedulingModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_window(self) -> "AvailabilityWindow":
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("availability windows must be timezone-aware")
        if self.start >= self.end:
            raise ValueError("availability window start must be before end")
        return self


class BusyInterval(StrictSchedulingModel):
    start: datetime
    end: datetime
    source_event_id: str | None = None

    @model_validator(mode="after")
    def validate_interval(self) -> "BusyInterval":
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("busy intervals must be timezone-aware")
        if self.start >= self.end:
            raise ValueError("busy interval start must be before end")
        return self


class StudySession(StrictSchedulingModel):
    id: str | None = None
    task_id: str
    start: datetime
    end: datetime
    locked: bool = False

    @model_validator(mode="after")
    def validate_session(self) -> "StudySession":
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("study sessions must be timezone-aware")
        if self.start >= self.end:
            raise ValueError("study session start must be before end")
        return self

    @property
    def duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


class SchedulingPreference(StrictSchedulingModel):
    timezone: str = "UTC"
    earliest_study_time: time
    latest_study_time: time
    preferred_session_minutes: int = Field(ge=5, le=480)
    maximum_session_minutes: int = Field(ge=5, le=480)
    minimum_break_minutes: int = Field(ge=0, le=240)
    weekend_available: bool = True
    preferred_period: Literal["morning", "afternoon", "evening", "any"] = "any"

    @model_validator(mode="after")
    def validate_preferences(self) -> "SchedulingPreference":
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError("unknown timezone") from error
        if self.earliest_study_time >= self.latest_study_time:
            raise ValueError("earliest study time must be before latest study time")
        if self.preferred_session_minutes > self.maximum_session_minutes:
            raise ValueError("preferred session length cannot exceed maximum")
        return self


class SchedulingConflict(StrictSchedulingModel):
    code: str
    message: str
    task_id: str | None = None
    unscheduled_minutes: int = 0


class SchedulingMetrics(StrictSchedulingModel):
    tasks_fully_scheduled: int = 0
    tasks_partially_scheduled: int = 0
    unscheduled_minutes: int = 0
    session_count: int = 0
    average_session_minutes: float = 0
    deadline_violations: int = 0
    preference_violations: int = 0


class SchedulingProblem(StrictSchedulingModel):
    tasks: tuple[AcademicTask, ...]
    availability_windows: tuple[AvailabilityWindow, ...]
    busy_intervals: tuple[BusyInterval, ...]
    preferences: SchedulingPreference
    locked_sessions: tuple[StudySession, ...] = ()
    now: datetime

    @model_validator(mode="after")
    def validate_problem(self) -> "SchedulingProblem":
        if self.now.tzinfo is None or self.now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        return self


class SchedulingResult(StrictSchedulingModel):
    status: SchedulingStatus
    sessions: tuple[StudySession, ...] = ()
    conflicts: tuple[SchedulingConflict, ...] = ()
    metrics: SchedulingMetrics
    unscheduled_minutes_by_task: dict[str, int] = Field(default_factory=dict)
