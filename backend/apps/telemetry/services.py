from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import AssetIdentity, PositionPing, TelemetrySource

SYNTHETIC_SOURCE_TYPES = {
    TelemetrySource.SourceType.SYNTHETIC_GPS,
    TelemetrySource.SourceType.SYNTHETIC_AIS,
}


def ingest_position_ping(*, payload: dict) -> dict:
    normalized = _normalize_payload(payload)
    with transaction.atomic():
        source = _resolve_source(normalized)
        asset_identity = _resolve_asset_identity(source=source, payload=normalized)
        ping = PositionPing.objects.create(
            ping_id=_next_ping_id(source_id=source.source_id),
            source=source,
            asset_identity=asset_identity,
            asset_type=asset_identity.asset_type,
            asset_code=asset_identity.asset_code,
            latitude=normalized["latitude"],
            longitude=normalized["longitude"],
            speed_knots=normalized.get("speed_knots"),
            course_degrees=normalized.get("course_degrees"),
            heading_degrees=normalized.get("heading_degrees"),
            device_timestamp=normalized["device_timestamp"],
            received_timestamp=timezone.now(),
            signal_quality=normalized.get("signal_quality", PositionPing.SignalQuality.GOOD),
            accuracy_m=normalized.get("accuracy_m"),
            battery_level=normalized.get("battery_level"),
            raw_payload=normalized.get("raw_payload", {}),
            raw_payload_ref=normalized.get("raw_payload_ref", ""),
            is_synthetic=source.source_type in SYNTHETIC_SOURCE_TYPES,
        )
    return {
        "ping": ping,
        "latest_state_updated": False,
        "geofence_events": [],
        "alerts": [],
    }


def _normalize_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError("Telemetry payload must be an object.")

    required = [
        "source_id",
        "source_type",
        "external_id",
        "asset_type",
        "asset_code",
        "latitude",
        "longitude",
        "device_timestamp",
    ]
    missing = [field for field in required if payload.get(field) in {None, ""}]
    if missing:
        raise ValidationError({field: "This field is required." for field in missing})

    latitude = _decimal_in_range(payload["latitude"], "latitude", Decimal("-90"), Decimal("90"))
    longitude = _decimal_in_range(
        payload["longitude"],
        "longitude",
        Decimal("-180"),
        Decimal("180"),
    )
    speed_knots = _optional_decimal(payload.get("speed_knots"), "speed_knots")
    if speed_knots is not None and speed_knots < 0:
        raise ValidationError({"speed_knots": "Speed cannot be negative."})

    course_degrees = _optional_decimal(payload.get("course_degrees"), "course_degrees")
    heading_degrees = _optional_decimal(payload.get("heading_degrees"), "heading_degrees")
    for field, value in {
        "course_degrees": course_degrees,
        "heading_degrees": heading_degrees,
    }.items():
        if value is not None and (value < 0 or value >= 360):
            raise ValidationError({field: "Degrees must be >= 0 and < 360."})

    device_timestamp = payload["device_timestamp"]
    if timezone.is_naive(device_timestamp):
        device_timestamp = timezone.make_aware(device_timestamp)

    battery_level = payload.get("battery_level")
    if battery_level is not None and not 0 <= int(battery_level) <= 100:
        raise ValidationError({"battery_level": "Battery level must be between 0 and 100."})

    return {
        **payload,
        "source_id": str(payload["source_id"]).strip(),
        "source_type": str(payload["source_type"]).strip(),
        "external_id": str(payload["external_id"]).strip(),
        "asset_type": str(payload["asset_type"]).strip(),
        "asset_code": str(payload["asset_code"]).strip(),
        "external_id_type": str(
            payload.get("external_id_type") or AssetIdentity.ExternalIdType.SYNTHETIC_ID
        ).strip(),
        "latitude": latitude,
        "longitude": longitude,
        "speed_knots": speed_knots,
        "course_degrees": course_degrees,
        "heading_degrees": heading_degrees,
        "device_timestamp": device_timestamp,
        "battery_level": battery_level,
        "signal_quality": payload.get("signal_quality") or PositionPing.SignalQuality.GOOD,
        "raw_payload": payload.get("raw_payload") or {},
        "raw_payload_ref": str(payload.get("raw_payload_ref") or "").strip(),
    }


def _resolve_source(payload: dict) -> TelemetrySource:
    source_type = payload["source_type"]
    if source_type not in dict(TelemetrySource.SourceType.choices):
        raise ValidationError({"source_type": "Unsupported telemetry source type."})

    source, created = TelemetrySource.objects.get_or_create(
        source_id=payload["source_id"],
        defaults={
            "name": payload.get("source_name") or payload["source_id"],
            "source_type": source_type,
            "status": TelemetrySource.Status.ACTIVE,
            "metadata": {"createdFromIngest": True},
        },
    )
    if not created and source.source_type != source_type:
        raise ValidationError(
            {"source_type": f"{source.source_id} is registered as {source.source_type}."}
        )
    return source


def _resolve_asset_identity(*, source: TelemetrySource, payload: dict) -> AssetIdentity:
    if payload["asset_type"] not in dict(AssetIdentity.AssetType.choices):
        raise ValidationError({"asset_type": "Unsupported tracked asset type."})
    if payload["external_id_type"] not in dict(AssetIdentity.ExternalIdType.choices):
        raise ValidationError({"external_id_type": "Unsupported external ID type."})

    identity, created = AssetIdentity.objects.get_or_create(
        source=source,
        external_id=payload["external_id"],
        defaults={
            "asset_type": payload["asset_type"],
            "asset_code": payload["asset_code"],
            "asset_object_id": payload.get("asset_object_id"),
            "external_id_type": payload["external_id_type"],
            "is_primary": True,
            "metadata": {"createdFromIngest": True},
        },
    )
    if created:
        return identity

    changed_fields = []
    for field in ["asset_type", "asset_code", "external_id_type"]:
        incoming_value = payload[field]
        if getattr(identity, field) != incoming_value:
            setattr(identity, field, incoming_value)
            changed_fields.append(field)
    incoming_object_id = payload.get("asset_object_id")
    if incoming_object_id and identity.asset_object_id != incoming_object_id:
        identity.asset_object_id = incoming_object_id
        changed_fields.append("asset_object_id")
    if changed_fields:
        changed_fields.append("updated_at")
        identity.save(update_fields=changed_fields)
    return identity


def _decimal_in_range(value, field: str, minimum: Decimal, maximum: Decimal) -> Decimal:
    decimal_value = _optional_decimal(value, field)
    if decimal_value is None or decimal_value < minimum or decimal_value > maximum:
        raise ValidationError({field: f"{field} must be between {minimum} and {maximum}."})
    return decimal_value


def _optional_decimal(value, field: str) -> Decimal | None:
    if value in {None, ""}:
        return None
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise ValidationError({field: "Must be a valid decimal value."}) from exc


def _next_ping_id(*, source_id: str) -> str:
    return f"PNG-{source_id}-{uuid4().hex[:12].upper()}"
