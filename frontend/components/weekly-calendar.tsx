"use client";

import { useState } from "react";
import { GripVertical, Pencil, X } from "lucide-react";
import type { BusyInterval, StudySession } from "@/features/plan/api";
import type { ProjectTask } from "@/lib/project-tasks";

const HOUR_HEIGHT = 64;

export type CalendarPreferences = {
  earliest: string;
  latest: string;
  maximumSessionMinutes: number;
  minimumBreakMinutes: number;
};

export function sessionKey(session: StudySession) {
  return session.id || [session.task_id, session.start].join("-");
}

function localDateValue(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return [year, month, day].join("-");
}

function clockMinutes(value: string) {
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

function overlaps(start: Date, end: Date, otherStart: Date, otherEnd: Date) {
  return start < otherEnd && otherStart < end;
}

export function validateSessionPlacement({
  key,
  taskId,
  start,
  duration,
  sessions,
  busyIntervals,
  windowStart,
  windowEnd,
  preferences,
  deadline,
  estimatedMinutes,
}: {
  key: string;
  taskId: string;
  start: Date;
  duration: number;
  sessions: StudySession[];
  busyIntervals: BusyInterval[];
  windowStart: string;
  windowEnd: string;
  preferences: CalendarPreferences;
  deadline?: string;
  estimatedMinutes?: number;
}) {
  const end = new Date(start.getTime() + duration * 60000);
  if (start < new Date(windowStart) || end > new Date(windowEnd))
    return "That time is outside this planning window.";
  const startMinutes = start.getHours() * 60 + start.getMinutes();
  const endMinutes = end.getHours() * 60 + end.getMinutes();
  if (
    localDateValue(start) !== localDateValue(end) ||
    startMinutes < clockMinutes(preferences.earliest) ||
    endMinutes > clockMinutes(preferences.latest)
  )
    return "That time is outside your available hours.";
  if (duration > preferences.maximumSessionMinutes)
    return "That block is longer than your maximum session length.";
  if (deadline && end > new Date(deadline))
    return "That time would place the task after its deadline.";
  if (
    busyIntervals.some((busy) =>
      overlaps(start, end, new Date(busy.start), new Date(busy.end)),
    )
  )
    return "That time overlaps a Busy calendar interval.";
  const otherSessions = sessions.filter(
    (session) => sessionKey(session) !== key,
  );
  const breakMs = preferences.minimumBreakMinutes * 60000;
  const conflictingSession = otherSessions.find((session) => {
    const otherStart = new Date(session.start);
    const otherEnd = new Date(session.end);
    return (
      start < new Date(otherEnd.getTime() + breakMs) &&
      new Date(otherStart.getTime() - breakMs) < end
    );
  });
  if (conflictingSession) {
    if (
      overlaps(
        start,
        end,
        new Date(conflictingSession.start),
        new Date(conflictingSession.end),
      )
    )
      return "Relay time blocks cannot overlap.";
    return `Leave at least ${preferences.minimumBreakMinutes} minutes between Relay blocks.`;
  }
  if (estimatedMinutes) {
    const otherTaskMinutes = otherSessions
      .filter((session) => session.task_id === taskId)
      .reduce(
        (total, session) =>
          total +
          (new Date(session.end).getTime() -
            new Date(session.start).getTime()) /
            60000,
        0,
      );
    if (otherTaskMinutes + duration > estimatedMinutes)
      return "Those blocks exceed the task's estimated time.";
  }
  return null;
}

export function WeeklyCalendar({
  sessions,
  busyIntervals,
  tasks,
  taskDeadlines,
  taskEstimates,
  windowStart,
  windowEnd,
  preferences,
  saving,
  onMove,
  onEdit,
  onInvalid,
}: {
  sessions: StudySession[];
  busyIntervals: BusyInterval[];
  tasks: ProjectTask[];
  taskDeadlines: Record<string, string>;
  taskEstimates: Record<string, number>;
  windowStart: string;
  windowEnd: string;
  preferences: CalendarPreferences;
  saving: boolean;
  onMove: (key: string, start: Date) => void;
  onEdit: (session: StudySession) => void;
  onInvalid: (message: string | null) => void;
}) {
  const [draggingKey, setDraggingKey] = useState<string | null>(null);
  const [invalidDay, setInvalidDay] = useState<number | null>(null);
  const firstDay = new Date(windowStart);
  firstDay.setHours(0, 0, 0, 0);
  const days = Array.from({ length: 7 }, (_, index) => {
    const day = new Date(firstDay);
    day.setDate(firstDay.getDate() + index);
    return day;
  });
  const starts = [
    ...sessions.map((session) => new Date(session.start)),
    ...busyIntervals.map((busy) => new Date(busy.start)),
  ];
  const ends = [
    ...sessions.map((session) => new Date(session.end)),
    ...busyIntervals.map((busy) => new Date(busy.end)),
  ];
  const firstHour = Math.max(
    0,
    Math.min(
      8,
      Math.floor(clockMinutes(preferences.earliest) / 60),
      ...starts.map((date) => date.getHours()),
    ),
  );
  const lastHour = Math.min(
    24,
    Math.max(
      18,
      Math.ceil(clockMinutes(preferences.latest) / 60),
      ...ends.map((date) => date.getHours() + (date.getMinutes() ? 1 : 0)),
    ),
  );
  const hourCount = Math.max(1, lastHour - firstHour);
  const titleFor = (taskId: string) =>
    tasks.find((task) => task.id === taskId)?.title || "Project task";
  const sessionFor = (key: string) =>
    sessions.find((session) => sessionKey(session) === key);
  const placementAt = (
    event: React.DragEvent<HTMLDivElement>,
    dayIndex: number,
  ) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const rawMinutes =
      firstHour * 60 + ((event.clientY - bounds.top) / HOUR_HEIGHT) * 60;
    const snappedMinutes = Math.max(
      firstHour * 60,
      Math.min(lastHour * 60 - 15, Math.round(rawMinutes / 15) * 15),
    );
    const moved = new Date(days[dayIndex]);
    moved.setHours(Math.floor(snappedMinutes / 60), snappedMinutes % 60, 0, 0);
    return moved;
  };
  const placementError = (key: string, start: Date) => {
    const session = sessionFor(key);
    if (!session) return "That time block is no longer available.";
    const duration = Math.round(
      (new Date(session.end).getTime() - new Date(session.start).getTime()) /
        60000,
    );
    return validateSessionPlacement({
      key,
      taskId: session.task_id,
      start,
      duration,
      sessions,
      busyIntervals,
      windowStart,
      windowEnd,
      preferences,
      deadline: taskDeadlines[session.task_id],
      estimatedMinutes: taskEstimates[session.task_id],
    });
  };

  return (
    <div className="project-week-calendar-scroll">
      <div
        className="project-week-calendar"
        aria-label="Editable weekly schedule"
      >
        <div className="project-week-calendar-header">
          <span aria-hidden="true" />
          {days.map((day) => (
            <div key={day.toISOString()}>
              <span>
                {day.toLocaleDateString(undefined, { weekday: "short" })}
              </span>
              <strong>{day.getDate()}</strong>
            </div>
          ))}
        </div>
        <div
          className={"project-week-calendar-body" + (saving ? " saving" : "")}
          style={{ height: hourCount * HOUR_HEIGHT }}
        >
          <div className="project-week-time-rail">
            {Array.from({ length: hourCount + 1 }, (_, index) => (
              <time key={index} style={{ top: index * HOUR_HEIGHT }}>
                {new Date(2000, 0, 1, firstHour + index).toLocaleTimeString(
                  undefined,
                  { hour: "numeric" },
                )}
              </time>
            ))}
          </div>
          <div className="project-week-day-grid">
            {days.map((day, dayIndex) => (
              <div
                className={`project-week-day-column ${invalidDay === dayIndex ? "invalid-drop" : ""}`}
                key={day.toISOString()}
                onDragOver={(event) => {
                  event.preventDefault();
                  if (!draggingKey) return;
                  const message = placementError(
                    draggingKey,
                    placementAt(event, dayIndex),
                  );
                  setInvalidDay(message ? dayIndex : null);
                  event.dataTransfer.dropEffect = message ? "none" : "move";
                }}
                onDragLeave={() => setInvalidDay(null)}
                onDrop={(event) => {
                  event.preventDefault();
                  const key =
                    event.dataTransfer.getData("text/relay-session") ||
                    draggingKey;
                  if (!key) return;
                  const moved = placementAt(event, dayIndex);
                  const message = placementError(key, moved);
                  setInvalidDay(null);
                  setDraggingKey(null);
                  if (message) {
                    onInvalid(message);
                    return;
                  }
                  onInvalid(null);
                  onMove(key, moved);
                }}
              >
                {Array.from({ length: hourCount }, (_, index) => (
                  <i key={index} aria-hidden="true" />
                ))}
                {busyIntervals
                  .filter((busy) => {
                    const dayEnd = new Date(day);
                    dayEnd.setDate(dayEnd.getDate() + 1);
                    return overlaps(
                      new Date(busy.start),
                      new Date(busy.end),
                      day,
                      dayEnd,
                    );
                  })
                  .map((busy, index) => {
                    const start = new Date(busy.start);
                    const end = new Date(busy.end);
                    const dayStartMs = day.getTime();
                    const visibleStart = Math.max(
                      firstHour * 60,
                      (start.getTime() - dayStartMs) / 60000,
                    );
                    const visibleEnd = Math.min(
                      lastHour * 60,
                      (end.getTime() - dayStartMs) / 60000,
                    );
                    if (visibleEnd <= visibleStart) return null;
                    return (
                      <div
                        className="project-week-busy-block"
                        key={`${busy.start}-${busy.end}-${index}`}
                        style={{
                          top:
                            ((visibleStart - firstHour * 60) / 60) *
                            HOUR_HEIGHT,
                          height: Math.max(
                            28,
                            ((visibleEnd - visibleStart) / 60) * HOUR_HEIGHT,
                          ),
                        }}
                      >
                        <strong>Busy</strong>
                        <small>
                          {start.toLocaleTimeString(undefined, {
                            hour: "numeric",
                            minute: "2-digit",
                          })}
                          {" – "}
                          {end.toLocaleTimeString(undefined, {
                            hour: "numeric",
                            minute: "2-digit",
                          })}
                        </small>
                      </div>
                    );
                  })}
                {sessions
                  .filter(
                    (session) =>
                      localDateValue(new Date(session.start)) ===
                      localDateValue(day),
                  )
                  .map((session) => {
                    const start = new Date(session.start);
                    const end = new Date(session.end);
                    const startMinutes =
                      start.getHours() * 60 + start.getMinutes();
                    const duration = Math.max(
                      15,
                      (end.getTime() - start.getTime()) / 60000,
                    );
                    return (
                      <button
                        type="button"
                        draggable={!saving}
                        className="project-week-session-block"
                        key={sessionKey(session)}
                        style={{
                          top:
                            ((startMinutes - firstHour * 60) / 60) *
                            HOUR_HEIGHT,
                          height: Math.max(34, (duration / 60) * HOUR_HEIGHT),
                        }}
                        onDragStart={(event) => {
                          setDraggingKey(sessionKey(session));
                          onInvalid(null);
                          event.dataTransfer.effectAllowed = "move";
                          event.dataTransfer.setData(
                            "text/relay-session",
                            sessionKey(session),
                          );
                        }}
                        onDragEnd={() => {
                          setDraggingKey(null);
                          setInvalidDay(null);
                        }}
                        onClick={() => onEdit(session)}
                        title="Drag to move or click to edit"
                      >
                        <GripVertical aria-hidden="true" />
                        <span>
                          <strong>{titleFor(session.task_id)}</strong>
                          <small>
                            {start.toLocaleTimeString(undefined, {
                              hour: "numeric",
                              minute: "2-digit",
                            })}{" "}
                            · {Math.round(duration)}m
                          </small>
                        </span>
                        <Pencil aria-hidden="true" />
                      </button>
                    );
                  })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function ScheduleBlockModal({
  session,
  title,
  windowStart,
  windowEnd,
  pending,
  close,
  save,
}: {
  session: StudySession;
  title: string;
  windowStart: string;
  windowEnd: string;
  pending: boolean;
  close: () => void;
  save: (start: Date, duration: number) => void;
}) {
  const initialStart = new Date(session.start);
  const finalDay = new Date(windowEnd);
  finalDay.setDate(finalDay.getDate() - 1);
  const [date, setDate] = useState(localDateValue(initialStart));
  const [time, setTime] = useState(
    [
      String(initialStart.getHours()).padStart(2, "0"),
      String(initialStart.getMinutes()).padStart(2, "0"),
    ].join(":"),
  );
  const [duration, setDuration] = useState(
    Math.round(
      (new Date(session.end).getTime() - initialStart.getTime()) / 60000,
    ),
  );
  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && close()}
    >
      <section
        className="project-modal compact"
        role="dialog"
        aria-modal="true"
        aria-labelledby="schedule-block-title"
      >
        <div className="modal-heading">
          <div>
            <p className="eyebrow">Edit time block</p>
            <h2 id="schedule-block-title">{title}</h2>
          </div>
          <button className="icon-button" onClick={close} aria-label="Close">
            <X />
          </button>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const start = new Date(date + "T" + time + ":00");
            if (!Number.isNaN(start.getTime())) save(start, duration);
          }}
        >
          <div className="form-split">
            <label className="field">
              Date
              <input
                type="date"
                required
                min={localDateValue(new Date(windowStart))}
                max={localDateValue(finalDay)}
                value={date}
                onChange={(event) => setDate(event.target.value)}
              />
            </label>
            <label className="field">
              Start time
              <input
                type="time"
                required
                step={900}
                value={time}
                onChange={(event) => setTime(event.target.value)}
              />
            </label>
          </div>
          <label className="field">
            Duration <span className="optional">Minutes</span>
            <input
              type="number"
              min={15}
              max={480}
              step={15}
              value={duration}
              onChange={(event) => setDuration(Number(event.target.value))}
            />
          </label>
          <div className="modal-actions">
            <button
              type="button"
              className="button secondary"
              onClick={close}
              disabled={pending}
            >
              Cancel
            </button>
            <button className="button" disabled={pending || duration < 15}>
              {pending ? "Saving…" : "Save time block"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
