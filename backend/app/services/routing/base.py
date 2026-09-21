from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.schemas.transport_models import (
    LocationInput,
    RoutePlan,
    TransportProvider,
    TravelMode,
)


class RouteProviderError(Exception):
    """A provider failed to return a usable route."""


class ProviderConfigurationError(RouteProviderError):
    """The provider is enabled in code but lacks required configuration."""


class ProviderNotImplementedError(RouteProviderError):
    """A known provider has deliberately not been integrated yet."""


@dataclass(frozen=True)
class RouteCalculationRequest:
    origin: LocationInput
    destination: LocationInput
    travel_mode: TravelMode
    requested_arrival_time: datetime
    routing_arrival_time: datetime | None = None
    departure_time: datetime | None = None
    safety_buffer_minutes: int = 0
    compute_alternatives: bool = True
    revision: int = 1

    def __post_init__(self) -> None:
        if (self.routing_arrival_time is None) == (self.departure_time is None):
            raise ValueError("Set exactly one of routing_arrival_time or departure_time")


class RouteProvider(Protocol):
    provider: TransportProvider

    async def calculate_route(self, request: RouteCalculationRequest) -> list[RoutePlan]:
        ...
