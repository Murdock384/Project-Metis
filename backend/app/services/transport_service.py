"""Application service for previewing, persisting, and refreshing journeys."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.scheduled_event import ScheduledEvent
from app.models.transport_schedule import TransportRouteRevision, TransportSchedule
from app.schemas.transport_models import (
    LocationInput,
    RefreshReason,
    RoutePlan,
    TransportEventRequest,
    TransportProvider,
)
from app.services.routing import GoogleRoutesProvider, JakdojadeRouteProvider
from app.services.routing.base import RouteCalculationRequest, RouteProvider


class TransportConflictError(Exception):
    pass


def _as_utc(value: datetime) -> datetime:
    """Restore UTC metadata after SQLite's timezone-less datetime round trip."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def get_provider(provider: TransportProvider) -> RouteProvider:
    if provider == TransportProvider.GOOGLE:
        return GoogleRoutesProvider()
    if provider == TransportProvider.JAKDOJADE:
        return JakdojadeRouteProvider()
    raise ValueError(f"Unknown transport provider: {provider}")


def _target_arrival_time(
    db: Session, user_id: int, requested: TransportEventRequest
) -> datetime:
    if requested.target_event_id is None:
        return requested.arrival_time
    target = db.get(ScheduledEvent, requested.target_event_id)
    if target is None or target.user_id != user_id:
        raise LookupError("Target event not found")
    # A linked destination event is authoritative: when it moves, refreshes
    # automatically retain the user's intent to get there for its start.
    return _as_utc(target.start_time)


async def preview_transport(
    db: Session,
    user_id: int,
    request: TransportEventRequest,
    *,
    departure_time: datetime | None = None,
    origin_override: LocationInput | None = None,
    revision: int = 1,
) -> RoutePlan:
    if request.transport_mode.value != "transit" and departure_time is None:
        raise ValueError("Arrival-by planning is currently supported only for transit")
    desired_arrival = _target_arrival_time(db, user_id, request)
    routing_arrival = desired_arrival - timedelta(minutes=request.destination_buffer_minutes)
    calculation = RouteCalculationRequest(
        origin=origin_override or request.starting_location,
        destination=request.destination_location,
        travel_mode=request.transport_mode,
        requested_arrival_time=desired_arrival,
        routing_arrival_time=None if departure_time else routing_arrival,
        departure_time=departure_time,
        safety_buffer_minutes=request.safety_buffer_minutes,
        compute_alternatives=request.compute_alternatives,
        revision=revision,
    )
    candidates = await get_provider(request.provider).calculate_route(calculation)
    # The Google default is usually good, but this deterministic scoring keeps
    # behaviour stable across providers and favors fewer transfers on ties.
    return min(candidates, key=lambda plan: (plan.duration_minutes, plan.transfer_count))


def _title(destination: LocationInput) -> str:
    return f"Travel to {destination.label or destination.address or 'destination'}"[:200]


def _ensure_no_conflict(
    db: Session,
    user_id: int,
    plan: RoutePlan,
    *,
    excluded_event_id: int | None = None,
) -> None:
    statement = select(ScheduledEvent).where(
        ScheduledEvent.user_id == user_id,
        ScheduledEvent.start_time < plan.estimated_arrival_time,
        ScheduledEvent.end_time > plan.safe_leave_time,
    )
    if excluded_event_id is not None:
        statement = statement.where(ScheduledEvent.id != excluded_event_id)
    conflict = db.scalar(statement)
    if conflict is not None:
        raise TransportConflictError("The transport plan overlaps an existing calendar event")


def _write_plan(schedule: TransportSchedule, plan: RoutePlan) -> None:
    schedule.current_revision = plan.revision
    schedule.generated_at = plan.generated_at
    schedule.valid_until = plan.valid_until
    schedule.route_departure_time = plan.route_departure_time
    schedule.safe_leave_time = plan.safe_leave_time
    schedule.estimated_arrival_time = plan.estimated_arrival_time
    schedule.duration_minutes = plan.duration_minutes
    schedule.distance_meters = plan.distance_meters
    schedule.transfer_count = plan.transfer_count
    schedule.summary = plan.summary
    schedule.navigation_url = str(plan.navigation_url) if plan.navigation_url else None
    schedule.route_steps_json = [step.model_dump(mode="json") for step in plan.steps]


def _add_revision(schedule: TransportSchedule, plan: RoutePlan, reason: str) -> None:
    for revision in schedule.revisions:
        revision.selected = False
    schedule.revisions.append(
        TransportRouteRevision(
            revision=plan.revision,
            refresh_reason=reason,
            generated_at=plan.generated_at,
            route_departure_time=plan.route_departure_time,
            safe_leave_time=plan.safe_leave_time,
            estimated_arrival_time=plan.estimated_arrival_time,
            summary=plan.summary,
            route_steps_json=[step.model_dump(mode="json") for step in plan.steps],
            selected=True,
        )
    )


async def create_transport_event(
    db: Session, user_id: int, request: TransportEventRequest
) -> tuple[ScheduledEvent, RoutePlan]:
    plan = await preview_transport(db, user_id, request)
    _ensure_no_conflict(db, user_id, plan)

    event = ScheduledEvent(
        user_id=user_id,
        task_id=None,
        title=_title(request.destination_location),
        event_type="transport",
        source="transport",
        start_time=plan.safe_leave_time,
        end_time=plan.estimated_arrival_time,
    )
    db.add(event)
    db.flush()

    schedule = TransportSchedule(
        scheduled_event_id=event.id,
        target_event_id=request.target_event_id,
        user_id=user_id,
        provider=request.provider.value,
        transport_mode=request.transport_mode.value,
        origin_json=request.starting_location.model_dump(mode="json"),
        destination_json=request.destination_location.model_dump(mode="json"),
        requested_arrival_time=_target_arrival_time(db, user_id, request),
        destination_buffer_minutes=request.destination_buffer_minutes,
        safety_buffer_minutes=request.safety_buffer_minutes,
        current_revision=plan.revision,
        generated_at=plan.generated_at,
        route_departure_time=plan.route_departure_time,
        safe_leave_time=plan.safe_leave_time,
        estimated_arrival_time=plan.estimated_arrival_time,
        duration_minutes=plan.duration_minutes,
        distance_meters=plan.distance_meters,
        transfer_count=plan.transfer_count,
        summary=plan.summary,
        navigation_url=str(plan.navigation_url) if plan.navigation_url else None,
        route_steps_json=[step.model_dump(mode="json") for step in plan.steps],
    )
    db.add(schedule)
    db.flush()
    _add_revision(schedule, plan, "initial")
    db.commit()
    db.refresh(event)
    return event, plan


def _request_from_schedule(schedule: TransportSchedule) -> TransportEventRequest:
    return TransportEventRequest(
        starting_location=LocationInput.model_validate(schedule.origin_json),
        destination_location=LocationInput.model_validate(schedule.destination_json),
        arrival_time=_as_utc(schedule.requested_arrival_time),
        transport_mode=schedule.transport_mode,
        provider=schedule.provider,
        target_event_id=schedule.target_event_id,
        safety_buffer_minutes=schedule.safety_buffer_minutes,
        destination_buffer_minutes=schedule.destination_buffer_minutes,
    )


async def refresh_transport_event(
    db: Session,
    user_id: int,
    event_id: int,
    reason: RefreshReason,
    current_location: LocationInput | None,
    observed_at: datetime | None,
) -> tuple[ScheduledEvent, RoutePlan, RoutePlan]:
    event = db.get(ScheduledEvent, event_id)
    if event is None or event.user_id != user_id or event.transport_schedule is None:
        raise LookupError("Transport event not found")
    schedule = event.transport_schedule
    previous = _plan_from_schedule(schedule)
    request = _request_from_schedule(schedule)
    now = observed_at or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    # Once it is time to leave, arrive-by routing can be impossible. Ask for
    # the earliest route departing now and report lateness instead.
    is_late = reason == RefreshReason.RUNNING_LATE or now >= _as_utc(schedule.safe_leave_time)
    plan = await preview_transport(
        db,
        user_id,
        request,
        departure_time=now if is_late else None,
        origin_override=current_location,
        revision=schedule.current_revision + 1,
    )
    _ensure_no_conflict(db, user_id, plan, excluded_event_id=event.id)

    event.start_time = plan.safe_leave_time
    event.end_time = plan.estimated_arrival_time
    _write_plan(schedule, plan)
    _add_revision(schedule, plan, reason.value)
    db.commit()
    db.refresh(event)
    return event, previous, plan


def _plan_from_schedule(schedule: TransportSchedule) -> RoutePlan:
    """Rebuild the selected normalized plan from persisted provider-neutral data."""
    from uuid import uuid5, NAMESPACE_URL
    from app.schemas.transport_models import RouteStep

    return RoutePlan(
        plan_id=uuid5(NAMESPACE_URL, f"transport:{schedule.id}:revision:{schedule.current_revision}"),
        revision=schedule.current_revision,
        provider=schedule.provider,
        generated_at=_as_utc(schedule.generated_at),
        valid_until=_as_utc(schedule.valid_until) if schedule.valid_until else None,
        route_departure_time=_as_utc(schedule.route_departure_time),
        safe_leave_time=_as_utc(schedule.safe_leave_time),
        estimated_arrival_time=_as_utc(schedule.estimated_arrival_time),
        requested_arrival_time=_as_utc(schedule.requested_arrival_time),
        duration_minutes=schedule.duration_minutes,
        distance_meters=schedule.distance_meters,
        transfer_count=schedule.transfer_count,
        summary=schedule.summary,
        steps=[RouteStep.model_validate(step) for step in schedule.route_steps_json],
        navigation_url=schedule.navigation_url,
        projected_late_by_minutes=max(
            0,
            int((_as_utc(schedule.estimated_arrival_time) - _as_utc(schedule.requested_arrival_time)).total_seconds() // 60),
        ),
    )
