"""Public transport-planning contracts, independent of any route provider."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.schemas.event import EventRead


class TransportProvider(StrEnum):
    GOOGLE = "google"
    JAKDOJADE = "jakdojade"


class TravelMode(StrEnum):
    TRANSIT = "transit"
    DRIVING = "driving"
    WALKING = "walking"
    BICYCLING = "bicycling"


class RouteStepType(StrEnum):
    WALK = "walk"
    TRANSIT = "transit"
    DRIVE = "drive"
    BICYCLE = "bicycle"
    WAIT = "wait"


class RefreshReason(StrEnum):
    MANUAL = "manual"
    RUNNING_LATE = "running_late"
    RUNNING_EARLY = "running_early"
    LOCATION_CHANGED = "location_changed"
    TARGET_EVENT_CHANGED = "target_event_changed"


class Coordinates(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class LocationInput(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    place_id: str | None = Field(default=None, max_length=255)
    coordinates: Coordinates | None = None

    @model_validator(mode="after")
    def require_location_value(self):
        if not any((self.address, self.place_id, self.coordinates)):
            raise ValueError("Provide an address, place_id, or coordinates")
        return self


class TransportEventRequest(BaseModel):
    starting_location: LocationInput
    destination_location: LocationInput
    arrival_time: datetime
    transport_mode: TravelMode = TravelMode.TRANSIT
    provider: TransportProvider = TransportProvider.GOOGLE
    target_event_id: int | None = None
    safety_buffer_minutes: int = Field(default=10, ge=0, le=120)
    destination_buffer_minutes: int = Field(default=5, ge=0, le=120)
    compute_alternatives: bool = True

    @model_validator(mode="after")
    def require_timezone(self):
        if self.arrival_time.tzinfo is None:
            raise ValueError("arrival_time must include a timezone")
        return self


class TransitLine(BaseModel):
    name: str | None = None
    short_name: str | None = None
    vehicle_type: str | None = None
    headsign: str | None = None
    color: str | None = None


class RouteStep(BaseModel):
    step_type: RouteStepType
    instruction: str
    start_name: str | None = None
    end_name: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_minutes: int = Field(ge=0)
    distance_meters: int | None = Field(default=None, ge=0)
    transit_line: TransitLine | None = None
    stop_count: int | None = Field(default=None, ge=0)


class RoutePlan(BaseModel):
    plan_id: UUID
    revision: int = Field(ge=1)
    provider: TransportProvider
    generated_at: datetime
    valid_until: datetime | None = None
    route_departure_time: datetime
    safe_leave_time: datetime
    estimated_arrival_time: datetime
    requested_arrival_time: datetime
    duration_minutes: int = Field(ge=0)
    distance_meters: int | None = Field(default=None, ge=0)
    transfer_count: int = Field(default=0, ge=0)
    summary: str
    steps: list[RouteStep]
    navigation_url: HttpUrl | None = None
    projected_late_by_minutes: int = Field(default=0, ge=0)


class TransportEventResponse(BaseModel):
    scheduled_event: EventRead
    route_plan: RoutePlan


class TransportRefreshRequest(BaseModel):
    reason: RefreshReason = RefreshReason.MANUAL
    current_location: LocationInput | None = None
    observed_at: datetime | None = None

    @model_validator(mode="after")
    def observed_at_requires_timezone(self):
        if self.observed_at is not None and self.observed_at.tzinfo is None:
            raise ValueError("observed_at must include a timezone")
        return self


class TransportRefreshResponse(BaseModel):
    scheduled_event: EventRead
    previous_plan_id: UUID
    route_plan: RoutePlan
    event_changed: bool
    old_safe_leave_time: datetime
    new_safe_leave_time: datetime


class ProviderAvailability(BaseModel):
    id: TransportProvider
    available: bool
    reason: str | None = None
