"""OR-Tools CP-SAT based task scheduler.

Working hours, planning horizon, focus window, break length, daily workload
cap and category likes/dislikes all come from the caller as a
`SchedulerPreferences` value, so this module stays free of ORM and settings
imports and can be exercised on plain data. Busy time is only derived from
existing `ScheduledEvent` rows already in our own database - there is no
external calendar (e.g. Google Calendar) integrated yet, so there is nothing
else to avoid conflicting with.

The model discretizes each working day into fixed-size slots and uses
`AddNoOverlap` so no two events (new or pre-existing) collide. Tasks are
represented as *optional* intervals - if the horizon doesn't have room for
every pending task, the solver leaves the lowest priority ones unscheduled
rather than failing outright. The objective favors scheduling as many
(especially higher-urgency) tasks as possible; among scheduled tasks it
places more urgent ones earlier, pulls harder ones into the user's focus
window, and mildly prefers liked categories over disliked ones.
"""

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from ortools.sat.python import cp_model

SOLVER_TIME_LIMIT_SECONDS = 5.0

# Scheduling a task at all must outrank every soft term below, otherwise the
# solver starts dropping tasks to keep others in the focus window.
URGENCY_WEIGHT = 1000
FOCUS_WEIGHT = 20
CATEGORY_WEIGHT = 50


@dataclass
class SchedulerPreferences:
    work_start_hour: int = 8
    work_end_hour: int = 22
    horizon_days: int = 7
    slot_minutes: int = 15
    peak_focus_start_hour: int = 9
    peak_focus_end_hour: int = 12
    min_break_minutes: int = 0
    max_daily_task_minutes: int = 8 * 60
    preferred_categories: list[str] = field(default_factory=list)
    disliked_categories: list[str] = field(default_factory=list)


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
    category: str | None = None


@dataclass
class ScheduleResult:
    task_id: int
    scheduled: bool
    start_time: datetime | None = None
    end_time: datetime | None = None


class _Horizon:
    """Maps between absolute minute-slots and real datetimes, respecting the
    user's working hours."""

    def __init__(self, anchor_date: date, prefs: SchedulerPreferences):
        self.anchor_date = anchor_date
        self.slot_minutes = prefs.slot_minutes
        self.work_start_hour = prefs.work_start_hour
        self.work_end_hour = prefs.work_end_hour
        self.horizon_days = prefs.horizon_days
        self.slots_per_day = ((self.work_end_hour - self.work_start_hour) * 60) // self.slot_minutes
        self.total_slots = self.slots_per_day * self.horizon_days

        self.focus_start_slot = self._hour_to_slot_in_day(prefs.peak_focus_start_hour)
        self.focus_end_slot = self._hour_to_slot_in_day(prefs.peak_focus_end_hour)

    def _hour_to_slot_in_day(self, hour: int) -> int:
        offset_minutes = (hour - self.work_start_hour) * 60
        return min(self.slots_per_day, max(0, offset_minutes // self.slot_minutes))

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

    def busy_minutes_by_day(self, busy_blocks: list[BusyBlock]) -> dict[int, int]:
        """Working-hours minutes each day already consumed by existing events,
        so the daily workload cap accounts for what's on the calendar."""
        per_day: dict[int, int] = {}
        for day_index in range(self.horizon_days):
            day = self.anchor_date + timedelta(days=day_index)
            day_start = _combine(day, self.work_start_hour * 60)
            day_end = _combine(day, self.work_end_hour * 60)
            total = 0
            for busy in busy_blocks:
                overlap_start = max(busy.start_time, day_start)
                overlap_end = min(busy.end_time, day_end)
                if overlap_end > overlap_start:
                    total += int((overlap_end - overlap_start).total_seconds() // 60)
            per_day[day_index] = total
        return per_day


def _combine(day: date, minutes_from_midnight: int) -> datetime:
    return datetime(day.year, day.month, day.day) + timedelta(minutes=minutes_from_midnight)


def _normalize(categories: list[str]) -> set[str]:
    return {c.strip().lower() for c in categories if c and c.strip()}


def schedule_pending_tasks(
    tasks: list[SchedulableTask],
    busy_blocks: list[BusyBlock],
    prefs: SchedulerPreferences | None = None,
    anchor_date: date | None = None,
) -> list[ScheduleResult]:
    """Assign start/end times to as many `tasks` as possible within the
    user's working-hours horizon, without overlapping each other or
    `busy_blocks`, and respecting their break and daily workload preferences.
    """
    if not tasks:
        return []

    prefs = prefs or SchedulerPreferences()
    anchor_date = anchor_date or date.today()
    horizon = _Horizon(anchor_date, prefs)

    if horizon.slots_per_day <= 0:
        return [ScheduleResult(task_id=t.id, scheduled=False) for t in tasks]

    preferred = _normalize(prefs.preferred_categories)
    disliked = _normalize(prefs.disliked_categories)

    break_slots = math.ceil(prefs.min_break_minutes / horizon.slot_minutes)
    working_day_minutes = (prefs.work_end_hour - prefs.work_start_hour) * 60
    cap_is_binding = prefs.max_daily_task_minutes < working_day_minutes
    focus_is_binding = (
        horizon.focus_end_slot > horizon.focus_start_slot
        and (horizon.focus_end_slot - horizon.focus_start_slot) < horizon.slots_per_day
    )

    model = cp_model.CpModel()
    intervals: list[cp_model.IntervalVar] = []

    # task_id -> (is_scheduled, effective_start, in_focus) for objective +
    # result extraction; None marks a task that can't fit at all.
    task_vars: dict[int, tuple] = {}
    # day index -> list of (minutes, bool) contributions toward the daily cap
    daily_load: dict[int, list[tuple[int, cp_model.IntVar]]] = {
        d: [] for d in range(horizon.horizon_days)
    }

    for task in tasks:
        duration_slots = max(1, math.ceil(task.estimated_minutes / horizon.slot_minutes))

        if duration_slots > horizon.slots_per_day:
            # Can't fit in a single working day at all in this model; leave it
            # unscheduled rather than failing the whole solve.
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

        # The interval reserves the task plus its trailing break, but the break
        # is truncated at the end of the day so a last-slot task doesn't block
        # the next morning.
        size_var = model.NewIntVar(
            duration_slots, duration_slots + break_slots, f"size_{task.id}"
        )
        if break_slots > 0:
            remaining_in_day = model.NewIntVar(
                duration_slots, horizon.slots_per_day, f"remaining_{task.id}"
            )
            model.Add(remaining_in_day == horizon.slots_per_day - slot_in_day_var)
            model.AddMinEquality(
                size_var,
                [remaining_in_day, model.NewConstant(duration_slots + break_slots)],
            )

        interval = model.NewOptionalIntervalVar(
            start_var, size_var, end_var, is_scheduled, f"interval_{task.id}"
        )
        intervals.append(interval)

        # effective_start is only meaningful (and only counted in the
        # objective) when the task actually gets scheduled.
        effective_start = model.NewIntVar(0, horizon.total_slots, f"effective_start_{task.id}")
        model.Add(effective_start == start_var).OnlyEnforceIf(is_scheduled)
        model.Add(effective_start == 0).OnlyEnforceIf(is_scheduled.Not())

        # Half-reified: the solver can only claim the focus bonus when the
        # task genuinely starts inside the window.
        in_focus = None
        if focus_is_binding:
            in_focus = model.NewBoolVar(f"in_focus_{task.id}")
            model.Add(slot_in_day_var >= horizon.focus_start_slot).OnlyEnforceIf(in_focus)
            model.Add(slot_in_day_var < horizon.focus_end_slot).OnlyEnforceIf(in_focus)
            model.AddImplication(in_focus, is_scheduled)

        if cap_is_binding:
            for day_index in range(horizon.horizon_days):
                on_day = model.NewBoolVar(f"on_day_{task.id}_{day_index}")
                model.Add(day_var == day_index).OnlyEnforceIf(on_day)
                model.Add(day_var != day_index).OnlyEnforceIf(on_day.Not())

                counts = model.NewBoolVar(f"counts_{task.id}_{day_index}")
                model.AddBoolAnd([on_day, is_scheduled]).OnlyEnforceIf(counts)
                model.AddBoolOr([on_day.Not(), is_scheduled.Not()]).OnlyEnforceIf(counts.Not())
                daily_load[day_index].append((task.estimated_minutes, counts))

        task_vars[task.id] = (is_scheduled, effective_start, in_focus)

    # Fixed busy intervals from events already in our own DB.
    for i, busy in enumerate(busy_blocks):
        start_slot = horizon.datetime_to_slot_clamped(busy.start_time)
        # `end_time` is exclusive; if it lands exactly on a slot boundary
        # that's fine, otherwise round up so we never under-block.
        end_slot = horizon.datetime_to_slot_clamped(busy.end_time - timedelta(minutes=1))
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

    if cap_is_binding:
        busy_by_day = horizon.busy_minutes_by_day(busy_blocks)
        for day_index, contributions in daily_load.items():
            if not contributions:
                continue
            remaining_cap = prefs.max_daily_task_minutes - busy_by_day.get(day_index, 0)
            model.Add(
                sum(minutes * flag for minutes, flag in contributions) <= max(0, remaining_cap)
            )

    objective_terms = []
    for task in tasks:
        entry = task_vars[task.id]
        if entry is None:
            continue
        is_scheduled, effective_start, in_focus = entry
        objective_terms.append(task.urgency * URGENCY_WEIGHT * is_scheduled)
        objective_terms.append(-task.urgency * effective_start)

        if in_focus is not None:
            objective_terms.append(task.difficulty * FOCUS_WEIGHT * in_focus)

        category = (task.category or "").strip().lower()
        if category and category in preferred:
            objective_terms.append(CATEGORY_WEIGHT * is_scheduled)
        elif category and category in disliked:
            objective_terms.append(-CATEGORY_WEIGHT * is_scheduled)

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
        _, effective_start, _ = entry
        start_slot = solver.Value(effective_start)
        start_dt = horizon.slot_to_datetime(start_slot)
        end_dt = start_dt + timedelta(minutes=task.estimated_minutes)
        results.append(
            ScheduleResult(task_id=task.id, scheduled=True, start_time=start_dt, end_time=end_dt)
        )

    return results
