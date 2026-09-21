"""Transport preview, persistence, and dynamic refresh endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints.events import _to_event_read
from app.core.config import settings
from app.db.base import get_db
from app.models.scheduled_event import ScheduledEvent
from app.schemas.transport_models import (
    ProviderAvailability,
    RoutePlan,
    TransportEventRequest,
    TransportEventResponse,
    TransportProvider,
    TransportRefreshRequest,
    TransportRefreshResponse,
)
from app.services.routing.base import (
    ProviderConfigurationError,
    ProviderNotImplementedError,
    RouteProviderError,
)
from app.services.transport_service import (
    TransportConflictError,
    _plan_from_schedule,
    create_transport_event,
    preview_transport,
    refresh_transport_event,
)

router = APIRouter(prefix="/transport-events", tags=["transport-events"])


def _translate_error(error: Exception) -> HTTPException:
    if isinstance(error, ValueError):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, LookupError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, TransportConflictError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, ProviderNotImplementedError):
        return HTTPException(status_code=501, detail=str(error))
    if isinstance(error, ProviderConfigurationError):
        return HTTPException(status_code=503, detail=str(error))
    if isinstance(error, RouteProviderError):
        return HTTPException(status_code=502, detail=str(error))
    return HTTPException(status_code=500, detail="Could not plan transport")


@router.get("/providers", response_model=list[ProviderAvailability])
def list_providers():
    return [
        ProviderAvailability(id=TransportProvider.GOOGLE, available=bool(settings.google_maps_api_key)),
        ProviderAvailability(
            id=TransportProvider.JAKDOJADE,
            available=False,
            reason="Not implemented",
        ),
    ]


@router.post("/preview", response_model=RoutePlan)
async def preview(payload: TransportEventRequest, db: Session = Depends(get_db)):
    try:
        return await preview_transport(db, settings.dev_user_id, payload)
    except Exception as error:
        raise _translate_error(error) from error


@router.post("", response_model=TransportEventResponse, status_code=201)
async def create(payload: TransportEventRequest, db: Session = Depends(get_db)):
    try:
        event, plan = await create_transport_event(db, settings.dev_user_id, payload)
        return TransportEventResponse(scheduled_event=_to_event_read(event), route_plan=plan)
    except Exception as error:
        db.rollback()
        raise _translate_error(error) from error


@router.get("/{event_id}", response_model=TransportEventResponse)
def read(event_id: int, db: Session = Depends(get_db)):
    event = db.get(ScheduledEvent, event_id)
    if event is None or event.user_id != settings.dev_user_id or event.transport_schedule is None:
        raise HTTPException(status_code=404, detail="Transport event not found")
    return TransportEventResponse(
        scheduled_event=_to_event_read(event),
        route_plan=_plan_from_schedule(event.transport_schedule),
    )


@router.post("/{event_id}/refresh", response_model=TransportRefreshResponse)
async def refresh(
    event_id: int,
    payload: TransportRefreshRequest,
    db: Session = Depends(get_db),
):
    try:
        event, previous, plan = await refresh_transport_event(
            db,
            settings.dev_user_id,
            event_id,
            payload.reason,
            payload.current_location,
            payload.observed_at,
        )
        return TransportRefreshResponse(
            scheduled_event=_to_event_read(event),
            previous_plan_id=previous.plan_id,
            route_plan=plan,
            event_changed=(
                event.start_time != previous.safe_leave_time
                or event.end_time != previous.estimated_arrival_time
            ),
            old_safe_leave_time=previous.safe_leave_time,
            new_safe_leave_time=plan.safe_leave_time,
        )
    except Exception as error:
        db.rollback()
        raise _translate_error(error) from error
