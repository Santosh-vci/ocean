from django.db import migrations


def backfill_geofence_zones(apps, schema_editor):
    Location = apps.get_model("masters", "Location")
    GeofenceZone = apps.get_model("telemetry", "GeofenceZone")

    for location in Location.objects.order_by("code"):
        GeofenceZone.objects.update_or_create(
            zone_id=f"GEO-{location.code}",
            defaults={
                "name": location.name,
                "zone_type": location.location_type,
                "source_location": location,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "radius_m": location.geofence_radius_m,
                "status": "active",
                "metadata": {
                    "parentArea": location.parent_area,
                    "operationalNotes": location.operational_notes,
                    "source": "master_location_migration",
                },
            },
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("telemetry", "0004_geofencezone_latestassetstate_current_geofence_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_geofence_zones, noop_reverse),
    ]
