"""Google Routes API adapter that returns only provider-neutral route plans."""

import asyncio
import json
import math
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from app.core.config import settings
from app.schemas.transport_models import (
    LocationInput,
    RoutePlan,
    RouteStep,
    RouteStepType,
    TransitLine,
    TransportProvider,
    TravelMode,
)
from app.services.routing.base import (
    ProviderConfigurationError,
    RouteCalculationRequest,
    RouteProviderError,
)


FIELD_MASK = ",".join(
    [
        "routes.duration",
        "routes.distanceMeters",
        "routes.legs.steps.travelMode",
        "routes.legs.steps.duration",
        "routes.legs.steps.distanceMeters",
        "routes.legs.steps.navigationInstruction",
        "routes.legs.steps.transitDetails",
        "routes.legs.steps.startLocation",
        "routes.legs.steps.endLocation",
    ]
)


class GoogleRoutesProvider:
    provider = TransportProvider.GOOGLE

    async def calculate_route(self, request: RouteCalculationRequest) -> list[RoutePlan]:
        if not settings.google_maps_api_key:
            raise ProviderConfigurationError("GOOGLE_MAPS_API_KEY is not configured")

        body: dict = {
            "origin": _to_waypoint(request.origin),
            "destination": _to_waypoint(request.destination),
            "travelMode": _google_travel_mode(request.travel_mode),
            "computeAlternativeRoutes": request.compute_alternatives,
        }
        if request.routing_arrival_time:
            body["arrivalTime"] = _to_rfc3339(request.routing_arrival_time)
        else:
            body["departureTime"] = _to_rfc3339(request.departure_time)

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": settings.google_maps_api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }
        try:
            data = await asyncio.to_thread(_post_json, settings.google_routes_base_url, body, headers)
        except TimeoutError as exc:
            raise RouteProviderError("Google Routes request timed out") from exc
        except HTTPError as exc:
            # Do not include the body: it can contain provider implementation
            # details and should not be exposed to API clients.
            raise RouteProviderError(f"Google Routes returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise RouteProviderError("Google Routes request failed") from exc

        routes = data.get("routes", [])
        if not routes:
            raise RouteProviderError("Google could not find a usable route")
        return [_to_plan(route, request) for route in routes]


def _post_json(url: str, body: dict, headers: dict[str, str]) -> dict:
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.google_routes_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except TimeoutError:
        raise


def _to_waypoint(location: LocationInput) -> dict:
    if location.place_id:
        return {"placeId": location.place_id}
    if location.coordinates:
        return {
            "location": {
                "latLng": {
                    "latitude": location.coordinates.latitude,
                    "longitude": location.coordinates.longitude,
                }
            }
        }
    return {"address": location.address}


def _google_travel_mode(mode: TravelMode) -> str:
    return {
        TravelMode.TRANSIT: "TRANSIT",
        TravelMode.DRIVING: "DRIVE",
        TravelMode.WALKING: "WALK",
        TravelMode.BICYCLING: "BICYCLE",
    }[mode]


def _to_rfc3339(value: datetime | None) -> str:
    if value is None or value.tzinfo is None:
        raise ValueError("Google route times must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _seconds(value: str | None) -> int:
    if not value:
        return 0
    return max(0, math.ceil(float(value.removesuffix("s"))))


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _step_type(value: str | None) -> RouteStepType:
    return {
        "TRANSIT": RouteStepType.TRANSIT,
        "WALK": RouteStepType.WALK,
        "DRIVE": RouteStepType.DRIVE,
        "BICYCLE": RouteStepType.BICYCLE,
    }.get(value or "", RouteStepType.WALK)


def _to_plan(route: dict, request: RouteCalculationRequest) -> RoutePlan:
    raw_steps = [step for leg in route.get("legs", []) for step in leg.get("steps", [])]
    steps = [_to_step(step) for step in raw_steps]
    duration_seconds = _seconds(route.get("duration"))
    duration_minutes = max(1, math.ceil(duration_seconds / 60))

    # The first transit departure anchors the timetable. Adding Google's total
    # route duration back on also preserves any walking after the final stop.
    transit_steps = [step for step in steps if step.step_type == RouteStepType.TRANSIT]
    first_transit_index = next(
        (index for index, step in enumerate(steps) if step.step_type == RouteStepType.TRANSIT and step.start_time),
        None,
    )
    if first_transit_index is not None:
        leading_seconds = sum(_seconds(step.get("duration")) for step in raw_steps[:first_transit_index])
        route_departure = steps[first_transit_index].start_time - timedelta(seconds=leading_seconds)
        route_arrival = route_departure + timedelta(seconds=duration_seconds)
    elif request.departure_time is not None:
        route_departure = request.departure_time
        route_arrival = route_departure + timedelta(seconds=duration_seconds)
    else:
        route_arrival = request.routing_arrival_time
        route_departure = route_arrival - timedelta(seconds=duration_seconds)

    safe_leave = route_departure - timedelta(minutes=request.safety_buffer_minutes)
    transfer_count = max(0, len(transit_steps) - 1)
    late_minutes = max(
        0, math.ceil((route_arrival - request.requested_arrival_time).total_seconds() / 60)
    )
    summary = _summary(steps, route_arrival, late_minutes)

    return RoutePlan(
        plan_id=uuid4(),
        revision=request.revision,
        provider=TransportProvider.GOOGLE,
        generated_at=datetime.now(UTC),
        route_departure_time=route_departure,
        safe_leave_time=safe_leave,
        estimated_arrival_time=route_arrival,
        requested_arrival_time=request.requested_arrival_time,
        duration_minutes=duration_minutes,
        distance_meters=route.get("distanceMeters"),
        transfer_count=transfer_count,
        summary=summary,
        steps=steps,
        navigation_url=_navigation_url(request.origin, request.destination, request.travel_mode),
        projected_late_by_minutes=late_minutes,
    )


def _to_step(step: dict) -> RouteStep:
    transit = step.get("transitDetails") or {}
    stop_details = transit.get("stopDetails") or {}
    line = transit.get("transitLine") or {}
    vehicle = line.get("vehicle") or {}
    travel_mode = _step_type(step.get("travelMode"))
    start_time = _parse_time(stop_details.get("departureTime"))
    end_time = _parse_time(stop_details.get("arrivalTime"))
    start_name = (stop_details.get("departureStop") or {}).get("name")
    end_name = (stop_details.get("arrivalStop") or {}).get("name")
    duration_minutes = max(1, math.ceil(_seconds(step.get("duration")) / 60))

    if travel_mode == RouteStepType.TRANSIT:
        line_name = line.get("nameShort") or line.get("name") or "public transport"
        direction = f" toward {transit['headsign']}" if transit.get("headsign") else ""
        instruction = f"Take {line_name}{direction}"
    else:
        instruction = (step.get("navigationInstruction") or {}).get("instructions") or (
            f"{travel_mode.value.capitalize()} for {duration_minutes} min"
        )

    return RouteStep(
        step_type=travel_mode,
        instruction=instruction,
        start_name=start_name,
        end_name=end_name,
        start_time=start_time,
        end_time=end_time,
        duration_minutes=duration_minutes,
        distance_meters=step.get("distanceMeters"),
        transit_line=TransitLine(
            name=line.get("name"),
            short_name=line.get("nameShort"),
            vehicle_type=(vehicle.get("type") if vehicle else None),
            headsign=transit.get("headsign"),
            color=line.get("color"),
        ) if travel_mode == RouteStepType.TRANSIT else None,
        stop_count=transit.get("stopCount"),
    )


def _summary(steps: list[RouteStep], arrival: datetime, late_minutes: int) -> str:
    transit = [step for step in steps if step.step_type == RouteStepType.TRANSIT]
    if transit:
        lines = " → ".join(
            step.transit_line.short_name or step.transit_line.name or "transit"
            for step in transit
            if step.transit_line
        )
        text = f"Take {lines}; arrive around {arrival.strftime('%H:%M')}"
    else:
        text = f"Arrive around {arrival.strftime('%H:%M')}"
    return f"{text} ({late_minutes} min late)" if late_minutes else text


def _navigation_url(origin: LocationInput, destination: LocationInput, mode: TravelMode) -> str:
    params = {
        "api": "1",
        "origin": _location_text(origin),
        "destination": _location_text(destination),
        "travelmode": mode.value,
    }
    if origin.place_id:
        params["origin_place_id"] = origin.place_id
    if destination.place_id:
        params["destination_place_id"] = destination.place_id
    return "https://www.google.com/maps/dir/?" + urlencode(params)


def _location_text(location: LocationInput) -> str:
    if location.address:
        return location.address
    if location.coordinates:
        return f"{location.coordinates.latitude},{location.coordinates.longitude}"
    return location.label or location.place_id or ""
