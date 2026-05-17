from decimal import Decimal

from django.db import migrations
from django.utils import timezone


def backfill_latest_asset_state(apps, schema_editor):
    AssetIdentity = apps.get_model("telemetry", "AssetIdentity")
    LatestAssetState = apps.get_model("telemetry", "LatestAssetState")
    PositionPing = apps.get_model("telemetry", "PositionPing")

    identities = AssetIdentity.objects.select_related("source").order_by(
        "asset_type",
        "asset_code",
        "-is_primary",
        "source__source_id",
    )
    identity_by_asset = {}
    for identity in identities:
        key = (identity.asset_type, identity.asset_code)
        existing = identity_by_asset.get(key)
        if existing is None or _identity_rank(identity) < _identity_rank(existing):
            identity_by_asset[key] = identity

    latest_pings = PositionPing.objects.select_related("source", "asset_identity").order_by(
        "asset_type",
        "asset_code",
        "-device_timestamp",
        "-id",
    )
    ping_by_asset = {}
    for ping in latest_pings:
        ping_by_asset.setdefault((ping.asset_type, ping.asset_code), ping)

    now = timezone.now()
    for key, identity in identity_by_asset.items():
        ping = ping_by_asset.get(key)
        if ping:
            freshness = _freshness_status(
                source=ping.source,
                last_seen_at=ping.device_timestamp,
                now=now,
                signal_quality=ping.signal_quality,
            )
            LatestAssetState.objects.update_or_create(
                asset_type=ping.asset_type,
                asset_code=ping.asset_code,
                defaults={
                    "source": ping.source,
                    "asset_identity": ping.asset_identity,
                    "last_ping": ping,
                    "derived_status": _derived_status(
                        freshness_status=freshness,
                        speed_knots=ping.speed_knots,
                    ),
                    "latitude": ping.latitude,
                    "longitude": ping.longitude,
                    "speed_knots": ping.speed_knots,
                    "heading_degrees": ping.heading_degrees,
                    "last_seen_at": ping.device_timestamp,
                    "freshness_status": freshness,
                    "confidence_score": _confidence_score(
                        freshness_status=freshness,
                        signal_quality=ping.signal_quality,
                    ),
                    "metadata": {
                        "backfilledFrom": "latest_position_ping",
                        "lastPingId": ping.ping_id,
                    },
                },
            )
            continue

        LatestAssetState.objects.update_or_create(
            asset_type=identity.asset_type,
            asset_code=identity.asset_code,
            defaults={
                "source": identity.source,
                "asset_identity": identity,
                "freshness_status": "missing",
                "derived_status": "unknown",
                "confidence_score": Decimal("0"),
                "metadata": {"backfilledFrom": "asset_identity"},
            },
        )


def noop_reverse(apps, schema_editor):
    pass


def _identity_rank(identity):
    source_type_rank = {
        "synthetic_gps": 0,
        "device_gateway": 1,
        "vendor_api": 2,
        "manual": 3,
        "synthetic_ais": 4,
    }
    primary_rank = 0 if identity.is_primary else 10
    return primary_rank + source_type_rank.get(identity.source.source_type, 9)


def _freshness_status(*, source, last_seen_at, now, signal_quality):
    if last_seen_at is None:
        return "missing"
    if signal_quality in {"invalid", "stale"}:
        return "stale"
    age_seconds = max(0, int((now - last_seen_at).total_seconds()))
    threshold = source.freshness_threshold_seconds
    if age_seconds <= threshold:
        return "fresh"
    if age_seconds <= threshold * 2:
        return "aging"
    return "stale"


def _derived_status(*, freshness_status, speed_knots):
    if freshness_status in {"missing", "stale"}:
        return "unknown"
    if speed_knots is not None and Decimal(speed_knots) >= Decimal("1.00"):
        return "underway"
    return "stopped"


def _confidence_score(*, freshness_status, signal_quality):
    if freshness_status == "missing":
        return Decimal("0")
    if freshness_status == "stale":
        return Decimal("25")
    if signal_quality == "weak":
        return Decimal("65")
    if freshness_status == "aging":
        return Decimal("70")
    return Decimal("96")


class Migration(migrations.Migration):
    dependencies = [
        ("telemetry", "0002_latestassetstate"),
    ]

    operations = [
        migrations.RunPython(backfill_latest_asset_state, noop_reverse),
    ]
