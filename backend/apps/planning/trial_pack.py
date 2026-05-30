from datetime import datetime, time, timedelta

from django.utils import timezone


def trial_start_date():
    return timezone.localdate() + timedelta(days=1)


def trial_dt(day_offset: int, hour: int, minute: int = 0):
    return timezone.make_aware(
        datetime.combine(trial_start_date() + timedelta(days=day_offset), time(hour, minute))
    )


def operator_trial_demand_rows() -> list[dict]:
    def iso(day_offset: int, hour: int, minute: int = 0) -> str:
        return trial_dt(day_offset, hour, minute).isoformat()

    return [
        {
            "voyage_id": "VOY-PACIFIC-PRIDE",
            "vessel_name": "MV PACIFIC PRIDE",
            "customer_name": "GLENCORE",
            "vessel_class": "Panamax",
            "eta": iso(0, 3),
            "etb": iso(0, 8),
            "etc_target": iso(2, 18),
            "laycan_start": iso(0, 0),
            "laycan_end": iso(3, 23),
            "required_mt": 165000,
            "loaded_mt": 142500,
            "in_transit_mt": 12000,
            "priority": 1,
            "demurrage_rate_usd_per_day": "14200.00",
            "current_stage": "H5 STAGE",
            "next_blocking_constraint": "No critical blockers",
            "cargo_requirements": [
                _requirement("EBONY", "LOC-SAMBARATA-PORT", "JTY-SUARAN", 98000, 86000, 6000),
                _requirement("AGATHIS", "LOC-LATI-PORT", "JTY-LATI", 67000, 56500, 6000),
            ],
            "cargo_layers": [
                _layer("EBONY", 1, 1, 1, 32000, 0, "BRG-VAL-08", "JTY-SUARAN", "CTS-BORNEO", "completed", "", "DISCHARGED", False, iso(0, 8), iso(0, 18)),
                _layer("AGATHIS", 1, 2, 2, 28000, 6500, "BRG-NUS-17", "JTY-LATI", "CTS-JAVA", "loading", "", "CTS FEED ACTIVE", False, iso(0, 19), iso(1, 4)),
                _layer("EBONY", 2, 1, 3, 34000, 34000, "BRG-KAL-22", "JTY-SUARAN", "CTS-BORNEO", "blocked", "Waiting for tide window at Rantau Delta", "TIDE GATE HOLD", False, iso(1, 6), iso(1, 17)),
            ],
        },
        {
            "voyage_id": "VOY-OCEAN-VOYAGER",
            "vessel_name": "MV OCEAN VOYAGER",
            "customer_name": "VITOL",
            "vessel_class": "Supramax",
            "eta": iso(0, 6),
            "etb": iso(0, 11),
            "etc_target": iso(2, 9),
            "laycan_start": iso(0, 0),
            "laycan_end": iso(2, 20),
            "required_mt": 120000,
            "loaded_mt": 118200,
            "in_transit_mt": 0,
            "priority": 2,
            "demurrage_rate_usd_per_day": "12800.00",
            "current_stage": "FINAL TOP-OFF",
            "next_blocking_constraint": "LOW TIDE DRAFT RESTR.",
            "cargo_requirements": [
                _requirement("MAHONI", "LOC-SUARAN-PORT", "JTY-SUARAN", 120000, 118200, 0),
            ],
            "cargo_layers": [],
        },
        {
            "voyage_id": "VOY-NORTH-STAR",
            "vessel_name": "MV NORTH STAR",
            "customer_name": "NIPPON STEEL",
            "vessel_class": "Handymax",
            "eta": iso(1, 1),
            "etb": iso(1, 9),
            "etc_target": iso(3, 4),
            "laycan_start": iso(1, 0),
            "laycan_end": iso(4, 8),
            "required_mt": 98000,
            "loaded_mt": 54000,
            "in_transit_mt": 18500,
            "priority": 2,
            "demurrage_rate_usd_per_day": "10900.00",
            "current_stage": "H2/L2",
            "next_blocking_constraint": "GRADE SEQUENCE VIOLATION",
            "cargo_requirements": [
                _requirement("SUNGKAI", "LOC-LATI-PORT", "JTY-LATI", 52000, 31000, 9000),
                _requirement("AGATHIS", "LOC-LATI-PORT", "JTY-LATI", 46000, 23000, 9500),
            ],
            "cargo_layers": [
                _layer("SUNGKAI", 2, 2, 1, 26000, 26000, "BRG-NUS-17", "JTY-LATI", "FC-CHLOE", "blocked", "Mahoni layer cannot precede Sungkai approval", "SEQUENCE VIOLATION", True, iso(1, 9), iso(1, 17)),
            ],
        },
        {
            "voyage_id": "VOY-GOLDEN-ORIOLE",
            "vessel_name": "MV GOLDEN ORIOLE",
            "customer_name": "KOREA POWER",
            "vessel_class": "Capesize",
            "eta": iso(3, 15),
            "etb": iso(4, 6),
            "etc_target": iso(7, 18),
            "laycan_start": iso(3, 0),
            "laycan_end": iso(7, 23),
            "required_mt": 210000,
            "loaded_mt": 0,
            "in_transit_mt": 0,
            "priority": 4,
            "demurrage_rate_usd_per_day": "15600.00",
            "current_stage": "PRE-LAYCAN",
            "next_blocking_constraint": "Awaiting ETA confirm",
            "cargo_requirements": [
                _requirement("EBONY", "LOC-SAMBARATA-PORT", "JTY-SUARAN", 130000, 0, 0),
                _requirement("MAHONI", "LOC-SUARAN-PORT", "JTY-SUARAN", 80000, 0, 0),
            ],
            "cargo_layers": [
                _layer("MAHONI", 1, 1, 1, 42000, 42000, "BRG-KAL-22", "JTY-SUARAN", "CTS-JAVA", "planned", "ETA not confirmed", "PRE-LAYCAN", False, iso(4, 6), iso(4, 18)),
            ],
        },
        {
            "voyage_id": "VOY-TRITON-STAR",
            "vessel_name": "MV TRITON STAR",
            "customer_name": "TRAFIGURA",
            "vessel_class": "Panamax",
            "eta": iso(0, 22),
            "etb": iso(1, 5),
            "etc_target": iso(4, 20),
            "laycan_start": iso(0, 12),
            "laycan_end": iso(4, 12),
            "required_mt": 180000,
            "loaded_mt": 22000,
            "in_transit_mt": 14500,
            "priority": 1,
            "demurrage_rate_usd_per_day": "15100.00",
            "current_stage": "H1/L1",
            "next_blocking_constraint": "Feeder delay (+4h)",
            "cargo_requirements": [
                _requirement("EBONY", "LOC-SAMBARATA-PORT", "JTY-SUARAN", 180000, 22000, 14500),
            ],
            "cargo_layers": [
                _layer("EBONY", 1, 1, 1, 36000, 36000, "BRG-VAL-08", "JTY-SUARAN", "CTS-BORNEO", "queued", "Feeder delay (+4h)", "BARGE QUEUE", False, iso(1, 2), iso(1, 12)),
            ],
        },
    ]


def operator_happy_path_demand_rows() -> list[dict]:
    def iso(day_offset: int, hour: int, minute: int = 0) -> str:
        return trial_dt(day_offset, hour, minute).isoformat()

    return [
        {
            "voyage_id": "VOY-HAPPY-001",
            "vessel_name": "MV HAPPY PATH ONE",
            "customer_name": "BERAU PILOT",
            "vessel_class": "Panamax",
            "eta": iso(0, 6),
            "etb": iso(0, 10),
            "etc_target": iso(2, 14),
            "laycan_start": iso(0, 0),
            "laycan_end": iso(4, 0),
            "required_mt": 144000,
            "loaded_mt": 0,
            "in_transit_mt": 0,
            "priority": 1,
            "demurrage_rate_usd_per_day": "12500.00",
            "current_stage": "READY_TO_PLAN",
            "next_blocking_constraint": "Ready for scheduling",
            "cargo_requirements": [
                _requirement("EBONY", "LOC-SAMBARATA-PORT", "JTY-SUARAN", 96000, 0, 0),
                _requirement("AGATHIS", "LOC-LATI-PORT", "JTY-LATI", 48000, 0, 0),
            ],
            "cargo_layers": [
                _layer("EBONY", 1, 1, 1, 48000, 48000, "BRG-VAL-08", "JTY-SUARAN", "CTS-BORNEO", "planned", "", "READY", False, iso(0, 10), iso(0, 16)),
                _layer("AGATHIS", 2, 1, 2, 48000, 48000, "BRG-NUS-17", "JTY-LATI", "CTS-JAVA", "planned", "", "READY", False, iso(0, 18), iso(1, 0)),
                _layer("EBONY", 3, 2, 3, 48000, 48000, "BRG-VAL-08", "JTY-SUARAN", "FC-CHLOE", "planned", "", "READY", False, iso(1, 6), iso(1, 12)),
            ],
        },
        {
            "voyage_id": "VOY-HAPPY-002",
            "vessel_name": "MV HAPPY PATH TWO",
            "customer_name": "ABL PILOT",
            "vessel_class": "Supramax",
            "eta": iso(1, 6),
            "etb": iso(1, 12),
            "etc_target": iso(3, 10),
            "laycan_start": iso(1, 0),
            "laycan_end": iso(5, 0),
            "required_mt": 108000,
            "loaded_mt": 0,
            "in_transit_mt": 0,
            "priority": 2,
            "demurrage_rate_usd_per_day": "11800.00",
            "current_stage": "READY_TO_PLAN",
            "next_blocking_constraint": "Ready for scheduling",
            "cargo_requirements": [
                _requirement("MAHONI", "LOC-SUARAN-PORT", "JTY-SUARAN", 72000, 0, 0),
                _requirement("AGATHIS", "LOC-LATI-PORT", "JTY-LATI", 36000, 0, 0),
            ],
            "cargo_layers": [
                _layer("MAHONI", 1, 1, 1, 36000, 36000, "BRG-NUS-17", "JTY-SUARAN", "CTS-BORNEO", "planned", "", "READY", False, iso(1, 14), iso(1, 20)),
                _layer("AGATHIS", 2, 1, 2, 36000, 36000, "BRG-VAL-08", "JTY-LATI", "CTS-JAVA", "planned", "", "READY", False, iso(2, 4), iso(2, 10)),
                _layer("MAHONI", 3, 2, 3, 36000, 36000, "BRG-NUS-17", "JTY-SUARAN", "FC-CHLOE", "planned", "", "READY", False, iso(2, 12), iso(2, 18)),
            ],
        },
    ]


def _requirement(grade, source, jetty, required, loaded, in_transit):
    return {
        "coal_grade_code": grade,
        "source_location_code": source,
        "preferred_jetty_code": jetty,
        "required_mt": required,
        "loaded_mt": loaded,
        "in_transit_mt": in_transit,
        "discharged_mt": 0,
        "status": "loading" if loaded else "planned",
    }


def _layer(
    grade,
    hatch,
    layer,
    sequence,
    required,
    remaining,
    barge,
    jetty,
    cts,
    status,
    blocking_reason,
    chain_status,
    sequence_violation,
    planned_start,
    planned_end,
):
    return {
        "coal_grade_code": grade,
        "hatch_no": hatch,
        "layer_no": layer,
        "required_sequence_no": sequence,
        "required_mt": required,
        "remaining_mt": remaining,
        "planned_barge_code": barge,
        "preferred_jetty_code": jetty,
        "planned_cts_code": cts,
        "status": status,
        "blocking_reason": blocking_reason,
        "chain_status": chain_status,
        "sequence_violation": sequence_violation,
        "planned_start": planned_start,
        "planned_end": planned_end,
    }
