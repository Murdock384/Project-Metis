"""OR-Tools CP-SAT based task scheduler.

Phase 0 simplification: working hours are a fixed constant (see
`app.core.config.Settings`) instead of being read from a per-user
`UserPreference` record (that model doesn't exist yet). Busy time is only
derived from existing `ScheduledEvent` rows already in our own database -
there is no external calendar (e.g. Google Calendar) integrated yet, so
there is nothing else to avoid conflicting with.

The model discretizes each working day into fixed-size slots and uses
`AddNoOverlap` so no two events (new or pre-existing) collide. Tasks are
represented as *optional* intervals - if the horizon doesn't have room for
every pending task, the solver leaves the lowest priority ones unscheduled
rather than failing outright. The objective favors scheduling as many
(especially higher-urgency) tasks as possible, and among scheduled tasks,
placing more urgent ones earlier.
"""

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from ortools.sat.python import cp_model

from app.core.config import settings

SOLVER_TIME_LIMIT_SECONDS = 5.0


@dataclass
class BusyBlock:
    start_time: datetime
    end_time: datetime


@dataclass
class SchedulableTask:
    id: int
    urgency: int
    difficulty: int
    estimated_minutes: int


@dataclass
class ScheduleResult:
    task_id: int
    scheduled: bool
    start_time: datetime | None = None
    end_time: datetime | None = None


class _Horizon:
    """Maps between absolute minute-slots and real datetimes, respecting
    fixed daily working hours (Phase 0's stand-in for user preferences)."""

    def __init__(self, anchor_date: date):
        self.anchor_date = anchor_date
        self.slot_minutes = settings.slot_minutes
        self.work_start_hour = settings.work_start_hour
        self.work_end_hour = settings.work_end_hour
        self.horizon_days = settings.horizon_days
        self.slots_per_day = ((self.work_end_hour - self.work_start_hour) * 60) // self.slot_minutes
        self.total_slots = self.slots_per_day * self.horizon_days

    def slot_to_datetime(self, slot: int) -> datetime:
        day_index, slot_in_day = divmod(slot, self.slots_per_day)
        day = self.anchor_date + timedelta(days=day_index)
        minutes_from_midnight = self.work_start_hour * 60 + slot_in_day * self.slot_minutes
        return _combine(day, minutes_from_midnight)

    def datetime_to_slot_clamped(self, dt: datetime) -> int | None:
        """Best-effort conversion of a real datetime into a slot index.

        Returns None if the datetime falls outside working hours/horizon
        (those busy blocks simply can't conflict with anything we schedule
        inside working hours, so they're safely ignored).
        """
        day_index = (dt.date() - self.anchor_date).days
        if day_index < 0 or day_index >= self.horizon_days:
            return None
        minutes_from_midnight = dt.hour * 60 + dt.minute
        work_start_minutes = self.work_start_hour * 60
        work_end_minutes = self.work_end_hour * 60
        if minutes_from_midnight < work_start_minutes or minutes_from_midnight >= work_end_minutes:
            return None
        slot_in_day = (minutes_from_midnight - work_start_minutes) // self.slot_minutes
        return day_index * self.slots_per_day + slot_in_day


def _combine(day: date, minutes_from_midnight: int) -> datetime:
    return datetime(day.year, day.month, day.day) + timedelta(minutes=minutes_from_midnight)


def schedule_pending_tasks(
    tasks: list[SchedulableTask],
    busy_blocks: list[BusyBlock],
    anchor_date: date | None = None,
) -> list[ScheduleResult]:
    """Assign start/end times to as many `tasks` as possible within the
    working-hours horizon, without overlapping each other or `busy_blocks`.
    """
    if not tasks:
        return []

    anchor_date = anchor_date or date.today()
    horizon = _Horizon(anchor_date)

    model = cp_model.CpModel()
    intervals: list[cp_model.IntervalVar] = []

    # task_id -> (is_scheduled, effective_start) for objective + result extraction
    task_vars: dict[int, tuple[cp_model.IntVar, cp_model.IntVar]] = {}

    for task in tasks:
        duration_slots = max(1, math.ceil(task.estimated_minutes / horizon.slot_minutes))

        if duration_slots > horizon.slots_per_day:
            # Can't fit in a single working day at all in this Phase 0 model;
            # leave it unscheduled rather than failing the whole solve.
            task_vars[task.id] = None
            continue

        day_var = model.NewIntVar(0, horizon.horizon_days - 1, f"day_{task.id}")
        slot_in_day_var = model.NewIntVar(
            0, horizon.slots_per_day - duration_slots, f"slot_in_day_{task.id}"
        )
        start_var = model.NewIntVar(0, horizon.total_slots - duration_slots, f"start_{task.id}")
        model.Add(start_var == day_var * horizon.slots_per_day + slot_in_day_var)

        end_var = model.NewIntVar(0, horizon.total_slots, f"end_{task.id}")
        is_scheduled = model.NewBoolVar(f"scheduled_{task.id}")

        interval = model.NewOptionalIntervalVar(
            start_var, duration_slots, end_var, is_scheduled, f"interval_{task.id}"
        )
        intervals.append(interval)

        # effective_start is only meaningful (and only counted in the
        # objective) when the task actually gets scheduled.
        effective_start = model.NewIntVar(0, horizon.total_slots, f"effective_start_{task.id}")
        model.Add(effective_start == start_var).OnlyEnforceIf(is_scheduled)
        model.Add(effective_start == 0).OnlyEnforceIf(is_scheduled.Not())

        task_vars[task.id] = (is_scheduled, effective_start)

    # Fixed busy intervals from events already in our own DB.
    for i, busy in enumerate(busy_blocks):
        start_slot = horizon.datetime_to_slot_clamped(busy.start_time)
        # `end_time` is exclusive; if it lands exactly on a slot boundary
        # that's fine, otherwise round up so we never under-block.
        end_slot = horizon.datetime_to_slot_clamped(
            busy.end_time - timedelta(minutes=1)
        )
        if start_slot is None or end_slot is None:
            continue
        end_slot += 1
        if end_slot <= start_slot:
            continue
        fixed_interval = model.NewIntervalVar(
            start_slot, end_slot - start_slot, end_slot, f"busy_{i}"
        )
        intervals.append(fixed_interval)

    if intervals:
        model.AddNoOverlap(intervals)

    # Objective: heavily reward scheduling tasks (weighted by urgency), then
    # as a tie-breaker prefer placing urgent tasks earlier in the horizon.
    URGENCY_WEIGHT = 1000
    objective_terms = []
    for task in tasks:
        entry = task_vars[task.id]
        if entry is None:
            continue
        is_scheduled, effective_start = entry
        objective_terms.append(task.urgency * URGENCY_WEIGHT * is_scheduled)
        objective_terms.append(-task.urgency * effective_start)

    if objective_terms:
        model.Maximize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVER_TIME_LIMIT_SECONDS
    status = solver.Solve(model)

    results: list[ScheduleResult] = []
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return [ScheduleResult(task_id=t.id, scheduled=False) for t in tasks]

    for task in tasks:
        entry = task_vars[task.id]
        if entry is None or not solver.Value(entry[0]):
            results.append(ScheduleResult(task_id=task.id, scheduled=False))
            continue
        is_scheduled, effective_start = entry
        start_slot = solver.Value(effective_start)
        start_dt = horizon.slot_to_datetime(start_slot)
        end_dt = start_dt + timedelta(minutes=task.estimated_minutes)
        results.append(
            ScheduleResult(task_id=task.id, scheduled=True, start_time=start_dt, end_time=end_dt)
        )

    return results
