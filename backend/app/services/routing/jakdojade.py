from app.schemas.transport_models import RoutePlan, TransportProvider
from app.services.routing.base import (
    ProviderNotImplementedError,
    RouteCalculationRequest,
)


class JakdojadeRouteProvider:
    """Intentional extension point; no silent fallback to Google."""

    provider = TransportProvider.JAKDOJADE

    async def calculate_route(self, request: RouteCalculationRequest) -> list[RoutePlan]:
        raise ProviderNotImplementedError("Jakdojade routing is not implemented yet")
