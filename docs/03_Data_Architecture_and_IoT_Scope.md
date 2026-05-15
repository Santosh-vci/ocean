# 03 — Data Architecture, GPS/AIS, Hardware, and IoT Scope

## 1. Architecture objective

The architecture should support a live planning and scheduling simulator for coal transshipment. The key design idea is:

> GPS/AIS/IoT provide live evidence. The scheduling engine converts evidence into operational decisions.

Do not build only a map. The map is an interface. The product value is the plan, exception logic, and recovery simulation.

## 2. Required external data

| Data group | Examples | Usage |
|---|---|---|
| OGV demand | ETA, laycan, cargo grade, cargo quantity, hatch/layering sequence | Planning demand and OGV completion projection. |
| Berau source data | mine/CPP/stockpile, product/brand, available quantity, jetty eligibility | Determines what can be loaded from where. |
| Jetty data | loading rate, queue, working hours, equipment status | Determines loading feasibility. |
| Fleet data | tug, barge, CTS, OGV, capacity, status, location | Determines resource assignment and cycle time. |
| River/route data | route segments, travel times, chokepoints, geofences | Determines ETA and operational movement. |
| Tide data | tide table, tide height, safe crossing windows | Determines river movement feasibility. |
| Bridge data | bridge opening schedule, crossing rules, queue | Determines timing windows. |
| Weather data | wind, rain, waves, visibility, safety alerts | Delay and safety risk. |
| AIS/GPS data | position, speed, course, timestamp | Live status and delay detection. |
| Operational events | breakdown, loading start/end, discharge start/end, stoppage | Triggers schedule revision. |

## 3. Recommended system-of-record split

| Store | Use |
|---|---|
| PostgreSQL | Master data, schedules, assignments, version history, audit, users, permissions. |
| ClickHouse or TimescaleDB | High-volume GPS/AIS/IoT time-series data. |
| Redis | Latest asset state, live ETA cache, alert deduplication. |
| Object storage | Raw files, raw vendor dumps, reports, exported schedules. |
| Kafka/Redpanda/RabbitMQ | Internal event stream for position, status, alert, and schedule-change events. |

## 4. Position and telemetry data model

Every moving asset should publish a standard movement event:

| Field | Description |
|---|---|
| asset_id | Internal asset ID. |
| asset_type | tug, barge, CTS, OGV, service boat, equipment. |
| source_type | GPS, AIS, manual, vendor API, edge gateway. |
| external_id | MMSI, IMO, tracker ID, device serial. |
| latitude / longitude | Position. |
| speed | Movement speed. |
| course / heading | Direction. |
| device_timestamp | Timestamp from device/source. |
| received_timestamp | Timestamp received by platform. |
| signal_quality | Quality/staleness/accuracy signal. |
| battery_level | For standalone tracker. |
| power_status | Main power or battery. |
| geofence_id | Derived location zone. |
| derived_status | loading, sailing, waiting, discharging, returning, unknown. |
| confidence_score | Reliability of derived state. |
| raw_payload_ref | Link/reference to raw message. |

## 5. Geofence model

Geofences should be created for:

- mines/CPP/stockpiles,
- jetty/BLC zones,
- river chokepoints,
- bridge approach/crossing zones,
- tide-restricted segments,
- anchorage,
- CTS operating area,
- OGV loading zone,
- maintenance yards,
- emergency waiting areas.

Derived events:

| Geofence event | Operational meaning |
|---|---|
| Enter jetty | Barge arrived for loading. |
| Dwell inside jetty | Waiting/loading candidate. |
| Exit jetty | Loaded departure candidate. |
| Enter bridge approach | Bridge crossing check. |
| Dwell near bridge | Waiting bridge/tide. |
| Enter CTS/OGV zone | Arrived for discharge. |
| Dwell at CTS | Discharging candidate. |
| Exit CTS zone | Returning or repositioning. |
| Enter maintenance zone | Unavailable asset candidate. |

## 6. Hardware scope

### 6.1 Tug hardware

| Hardware | Purpose |
|---|---|
| AIS transponder | Maritime visibility and compliance where required. |
| Independent GPS tracker | Internal truth even if AIS is weak/off. |
| Rugged onboard tablet | Job dispatch, status updates, alerts. |
| Cellular dual-SIM router | Connectivity. |
| Optional satellite backup | Remote/low-coverage areas. |
| NMEA gateway | Access onboard navigation data. |
| Power integration | Reliable device uptime. |

### 6.2 Barge hardware

| Hardware | Purpose |
|---|---|
| Rugged GPS tracker | Independent barge position. |
| Solar + battery pack | Power for unmanned barge. |
| Weatherproof/tamperproof enclosure | Device protection. |
| Optional AIS beacon/transponder | Maritime visibility if needed. |
| Optional draft/load sensor | Loaded vs empty detection. |

### 6.3 CTS / floating-crane hardware

| Hardware | Purpose |
|---|---|
| GPS/AIS tracking | Live location. |
| Operator tablet | Status confirmation and queue handling. |
| Crane/PLC interface | Actual working/idle state. |
| Fuel/engine sensor later | Utilization and cost analytics. |
| Local router | Data transmission. |

### 6.4 Jetty hardware

| Hardware | Purpose |
|---|---|
| Operator workstation/tablet | Confirm loading events. |
| Weighbridge integration | Actual loaded quantity. |
| Conveyor/BLC PLC integration | Loading start/end/rate. |
| RFID/BLE/barcode optional | Asset confirmation. |
| CCTV optional | Visual confirmation. |
| Local edge gateway | Offline buffering. |
| UPS/network equipment | Operational resilience. |

### 6.5 Bridge/tide/chokepoint hardware

| Hardware | Purpose |
|---|---|
| AIS receiver | Vessel approach/crossing visibility. |
| Tide/water-level sensor | Real water-level data. |
| Weather station | Local weather inputs. |
| Operator terminal | Bridge open/close confirmation. |
| Camera optional | Visual verification. |
| Edge gateway | Local event ingestion and buffering. |

## 7. IoT architecture

Recommended event flow:

```text
Device / AIS / GPS / PLC / Sensor
        ↓
Edge gateway or vendor API
        ↓
MQTT / HTTP / TCP-NMEA ingestion
        ↓
IoT/event broker
        ↓
Stream processor
        ↓
Latest operational state
        ↓
Scheduling simulation engine
        ↓
Alerts / UI / recovery recommendation
```

## 8. Suitable protocols

| Protocol | Use |
|---|---|
| MQTT | GPS trackers, IoT sensors, status events. |
| HTTP/REST | Vendor APIs and simple callbacks. |
| WebSocket | Live UI refresh. |
| TCP/UDP NMEA stream | AIS receiver/marine data. |
| Kafka/Redpanda | Internal event backbone. |
| OPC-UA / Modbus | Industrial/PLC integration. |
| NMEA 0183 / NMEA 2000 | Marine navigation data interface. |

## 9. Open-source framework options

| Framework/tool | Applicability |
|---|---|
| Mosquitto | Lightweight MQTT broker for MVP. |
| EMQX | Production-grade MQTT broker. |
| ThingsBoard | IoT device management, dashboards, rules. |
| Node-RED | Prototyping device flows and integrations. |
| OpenCPN | Marine chart/AIS/GPS integration reference/prototype. |
| AIS decoder tools | Prototype shore AIS receiver ingestion. |
| ChirpStack | LoRaWAN, if low-power shore sensors are used. |
| Kafka/Redpanda | Scalable event streaming. |

## 10. Device health monitoring

The platform should monitor device health separately from operational status.

| Health signal | Why it matters |
|---|---|
| Last seen timestamp | Detect stale devices. |
| Battery level | Avoid tracker failure. |
| Power mode | Main power vs battery. |
| GPS accuracy | Position reliability. |
| AIS freshness | Signal coverage. |
| Network status | Connectivity issue. |
| Firmware version | Maintenance/security. |
| Data gap duration | Confidence scoring. |

## 11. Scheduling engine integration

The live data layer should feed the scheduler through derived operational events:

| Live input | Derived scheduling event |
|---|---|
| GPS enters jetty | Candidate arrival at loading point. |
| GPS exits jetty after load confirmation | Loaded departure. |
| AIS/GPS speed below threshold near bridge | Waiting bridge/tide. |
| GPS late vs planned route ETA | Delay alert. |
| CTS operator confirms breakdown | Remove CTS from available pool. |
| Jetty PLC stops loading | Loading stoppage. |
| Tide sensor below threshold | Movement constraint active. |
| OGV ETA update | Re-sequence demand and barge dispatch. |

## 12. Build sequence

### Step 1 — Manual digital scheduler

- Build masters.
- Load OGV schedule.
- Load tide/bridge calendars.
- Produce feasible schedule.
- Store version history.

### Step 2 — GPS tracking

- Install trackers on tugs, barges, and CTS.
- Build live map and geofence detection.
- Show plan vs actual ETA.

### Step 3 — AIS ingestion

- Add shore AIS receiver where coverage is weak.
- Integrate vendor AIS for OGV/sea coverage.
- Map MMSI/IMO to internal asset registry.

### Step 4 — IoT event broker

- Add MQTT broker.
- Standardize event payloads.
- Add device health dashboard.

### Step 5 — Edge gateways

- Add local buffering at jetties and chokepoints.
- Prevent data loss during network outage.

### Step 6 — Optimization and recovery

- Add conflict repair and recommended reassignment.
- Keep planner approval before schedule lock.

## 13. Key design rule

The platform must separate:

- planned schedule,
- actual observed movement,
- manually confirmed status,
- derived/inferred status,
- recommended future schedule.

This prevents noisy AIS/GPS data from corrupting the operational schedule.

## 14. Source URLs used

- Uploaded BRD: `BRD - Schedulling Simulation.docx`
- Berau Coal Energy — Operations: https://beraucoalenergy.co.id/our-profile/operation/
- Berau Coal Energy — Marketing / Our Market: https://beraucoalenergy.co.id/our-profile/our-market/
- Berau Coal Energy — Shipping Devices: https://beraucoalenergy.co.id/shipping-devices/
- ABL — Home: https://abl.co.id/
- ABL — Transshipment: https://abl.co.id/transhipment
- ABL — Tug Boat / Barging: https://abl.co.id/tug-boat
- ABL — Dry Bulk / OGV: https://abl.co.id/dry-bulk
- ABL — Port Management: https://abl.co.id/port-management
