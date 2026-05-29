# Visual Presentation Brief: Live Tide Data for ABL Scheduling

## Purpose

This document summarizes the discussion on using live tide information for Indonesia-based tug-barge scheduling, especially for ABL’s transshipment operations. It is written as a slide-building brief for stakeholders and the developer team.

The goal of the presentation is to explain:

- What tide data means.
- How BMKG tide data should be interpreted.
- Why MSL and LAT matter.
- How tide data should influence tug-barge scheduling.
- What the software system must do with this data.

---

# 1. Business Context

ABL operates tug-barge, CTS, jetty, and transshipment activities in Indonesia. In the current operating reality, tug-barge movement is affected by multiple dynamic factors:

- OGV laycan and vessel arrival uncertainty.
- Jetty readiness and production readiness.
- Coal grade / buyer-specific cargo combination.
- Tug and barge availability.
- Bridge crossing windows.
- Weather and marine conditions.
- Tide windows.
- Grounding risk in shallow river sections.

From the business discussion, the most important tide-related issue is:

> Barges can get stuck or grounded when they move into shallow river sections during low tide.

Therefore, tide data should not be treated as background information. It should become a hard scheduling constraint.

---

# 2. Why Tide Data Matters

In the current/manual operating mode, a tug master may start movement without full system-backed visibility of the upcoming tide condition. If the barge reaches a shallow section during low tide, it may have to stop, moor, or wait until the tide rises.

This creates:

- Lost sailing time.
- Higher waiting time.
- Poor tug-barge utilization.
- Grounding risk.
- Confusion over whether waiting is laziness or the correct operational decision.
- Blame between field teams, ABL, and Berau/Braco-side planning teams.

The future system should make the decision visible:

> “Do not release now because the barge will reach the shallow segment during a low-tide window.”

This converts waiting from an informal decision into a system-backed operational recommendation.

---

# 3. Tide Data Source: BMKG Maritime Tide Page

The BMKG Maritime page provides tide prediction data for Indonesian stations.

Typical data elements include:

- Tide station.
- Start and end date.
- Time range, such as 3 days, 1 week, or 1 month.
- Timezone: UTC, WIB, WITA, or WIT.
- Datum/reference level: MSL or LAT.
- Tide height series.
- High tide points.
- Low tide points.
- Downloadable data series.

For ABL operations in East Kalimantan / Berau context, timezone handling is important because operational decisions may be taken locally, while downloaded data may be displayed in UTC or local Indonesian time.

---

# 4. Core Tide Concepts

## 4.1 Tide Height

Tide height is the water level at a given time relative to a selected reference baseline.

The same physical water level can have different numbers depending on the selected datum.

---

## 4.2 MSL: Mean Sea Level

MSL means Mean Sea Level.

It is an average sea-level reference. When the BMKG chart says:

```text
MSL = -0.97 m
```

It means:

```text
The water level is 0.97 metres below Mean Sea Level.
```

MSL is useful for understanding the broad tide curve, but it is not always the best reference for navigation clearance.

---

## 4.3 LAT: Lowest Astronomical Tide

LAT means Lowest Astronomical Tide.

It is a lower reference level and is commonly more relevant for navigation and clearance decisions.

When the BMKG data says:

```text
LAT = +0.80 m
```

It means:

```text
The water level is 0.80 metres above the Lowest Astronomical Tide reference.
```

For navigation, LAT is often preferred because charted depth may also be based on LAT.

---

# 5. Interpreting the Highlighted Data Point

Example data point discussed:

| Field | Value |
|---|---:|
| Date / Time | 28-05-2026 03:00 UTC |
| EST | 2.91 |
| MSL | -0.97 m |
| LAT | +0.80 m |

## Interpretation

At 28 May 2026, 03:00 UTC:

- The tide is **0.97 m below Mean Sea Level**.
- The same tide level is **0.80 m above Lowest Astronomical Tide**.

These are not two different water levels. They are two different measurements of the same physical water height against two different baselines.

---

# 6. Relationship Between MSL and LAT

From the example:

```text
MSL value = -0.97 m
LAT value = +0.80 m
```

The difference is:

```text
0.80 - (-0.97) = 1.77 m
```

So, in this station/datum context:

```text
MSL is approximately 1.77 m above LAT.
```

This is operationally important because mixing MSL and LAT in the same calculation can create a major error.

---

# 7. The Main Mistake to Avoid

Do not mix datum references.

## Wrong

```text
Charted depth based on LAT + tide height from MSL
```

## Correct

```text
Charted depth based on LAT + tide height from LAT
```

or

```text
Charted depth based on MSL + tide height from MSL
```

The software must enforce one consistent datum for clearance calculations.

---

# 8. Clearance Calculation Logic

For navigation, the practical question is not:

> “Is the tide high or low?”

The correct question is:

> “At the time the loaded barge reaches the shallow segment, is the available water depth enough for the barge draft plus safety clearance?”

## Formula

```text
Available Water Depth = Charted Depth + Tide Height
```

If charted depth is based on LAT, then tide height must also be LAT.

## Example

Assume:

```text
Charted depth above LAT = 3.0 m
Tide height above LAT = 0.80 m
```

Then:

```text
Available water depth = 3.0 + 0.80 = 3.80 m
```

Now compare this with vessel requirement:

```text
Required depth = Loaded barge draft + Under-keel clearance
```

Example:

```text
Loaded draft = 3.20 m
Safety clearance = 0.50 m
Required depth = 3.70 m
```

Result:

```text
Available = 3.80 m
Required = 3.70 m
Margin = 0.10 m
```

This may be technically passable, but operationally tight. The system may mark it as AMBER rather than GREEN.

---

# 9. Tide Data Should Become an Operational Window

The raw tide number should be converted into route-wise movement windows.

Recommended classification:

| Status | Meaning | Scheduling Action |
|---|---|---|
| GREEN | Safe clearance available | Release / proceed |
| AMBER | Borderline clearance | Proceed with caution / marine approval |
| RED | Insufficient clearance | Do not release |
| WAIT RECOMMENDED | Better to wait before starting | Hold at safe point / delay release |

The key point is that sometimes waiting is the correct decision. The system must justify why waiting improves overall flow.

---

# 10. How Tide Should Affect Tug-Barge Scheduling

The scheduler should not only check whether a tug and barge are available.

It must jointly evaluate:

```text
OGV laycan
+ jetty readiness
+ cargo / coal grade requirement
+ tug-barge availability
+ route travel time
+ bridge window
+ tide window
+ shallow segment risk
+ weather / marine conditions
+ maintenance / breakdown risk
```

For every proposed trip, the system should calculate:

1. Current tug-barge location.
2. Planned departure time.
3. ETA at jetty.
4. Loading start and end time.
5. ETA at bridge / shallow segment.
6. Tide height at that ETA.
7. Loaded or empty draft condition.
8. Available clearance.
9. Movement decision: release, wait, slow-steam, or reject.

---

# 11. System Behaviour Example

## Scenario

A loaded barge can depart now, but if it departs immediately, it will reach a shallow river segment at low tide.

## Current/manual behaviour risk

The master may proceed, then get stuck or grounded.

## Future system recommendation

```text
Recommendation: Hold release for 2 hours.
Reason: If released now, the loaded barge reaches Segment X at 03:00 UTC, where tide is only +0.80 m LAT and clearance margin is below the safe threshold.
Next safe movement window begins at 05:15 UTC.
```

This makes the waiting decision explainable and defensible.

---

# 12. Data Accuracy Position

BMKG/BIG tide data should be treated as a strong baseline, but not as blind truth for dispatch.

Accuracy should be viewed in three layers:

| Layer | Use |
|---|---|
| Official tide forecast | Baseline planning |
| Observed tide station data | Live validation / correction |
| Route-specific calibration | Final operational decision |

For ABL, the final decision should depend on:

```text
Forecast tide
+ observed/local data
+ route calibration
+ safety margin
+ marine team override
```

---

# 13. Developer Implementation Notes

## 13.1 Tide Station Master

Create a master table for tide stations:

- Station ID.
- Station name.
- Latitude / longitude.
- Source: BMKG, BIG, manual, or other.
- Datum availability: MSL, LAT.
- Timezone.
- Reliability status.

---

## 13.2 Route-to-Tide Mapping

Each operational route should be mapped to relevant tide stations and constrained segments:

- Jetty to transshipment route.
- Transshipment to jetty return route.
- Bridge approach.
- River shallow section.
- Anchorage / mooring point.

The system should not assume one station represents every segment equally. Local calibration must be supported.

---

## 13.3 Tide Series Storage

Store tide data as a time series:

| Field | Description |
|---|---|
| station_id | Tide station |
| timestamp_utc | Standard timestamp |
| local_timestamp | Local operation time |
| timezone | WIB / WITA / WIT |
| datum | MSL / LAT |
| tide_height_m | Tide height in metres |
| source | BMKG / BIG / manual |
| ingestion_time | When system received the data |

---

## 13.4 Safe Movement Window Generator

A daily/intraday process should convert tide series into movement windows:

```text
For each route segment:
    calculate tide at ETA
    calculate available depth
    compare with required depth
    assign GREEN / AMBER / RED / WAIT_RECOMMENDED
```

---

## 13.5 Scheduling Engine Integration

The scheduling engine should reject or delay trips where:

```text
Available depth < loaded draft + required under-keel clearance + safety buffer
```

It should also explain the decision in business terms.

Example:

```text
Trip held because loaded barge will reach Segment B during RED tide window.
Recommended release: 05:15 UTC / 13:15 WITA.
```

---

# 14. Visual Slide Structure

## Slide 1: Title

**Live Tide Data as a Scheduling Constraint**

Subtitle:

**Using BMKG/BIG tide information to reduce grounding risk and improve tug-barge flow**

---

## Slide 2: Business Problem

Visual idea:

A tug-barge route from Jetty → River Segment → Bridge → Transshipment Point.

Show a red low-tide zone where the barge gets stuck.

Message:

```text
The problem is not only asset availability. The vessel must reach each constrained segment at the right tide window.
```

---

## Slide 3: What BMKG Tide Data Shows

Visual idea:

Screenshot-style chart with tide curve and highlighted point.

Callouts:

- Date/time.
- MSL height.
- LAT height.
- High tide.
- Low tide.
- Timezone.

---

## Slide 4: MSL vs LAT

Visual idea:

Vertical ruler diagram:

```text
Mean Sea Level  ─────────────
                 1.77 m gap
Lowest Astronomical Tide ────
```

Example:

```text
At the same time:
MSL = -0.97 m
LAT = +0.80 m
```

Message:

```text
Same water level, different reference baselines.
```

---

## Slide 5: Clearance Calculation

Visual idea:

Cross-section of river:

- Riverbed.
- Charted depth.
- Tide height.
- Barge draft.
- Safety clearance.

Formula:

```text
Available Depth = Charted Depth + Tide Height
Required Depth = Draft + Safety Clearance
```

---

## Slide 6: Operational Decision Matrix

Visual idea:

Traffic-light table:

| Tide Status | Decision |
|---|---|
| GREEN | Release |
| AMBER | Proceed with caution |
| RED | Hold |
| WAIT RECOMMENDED | Wait before release |

Message:

```text
Waiting can be the correct decision if it prevents grounding.
```

---

## Slide 7: Scheduling Engine Logic

Visual idea:

Flowchart:

```text
Trip Proposal
→ ETA Calculation
→ Tide Lookup
→ Clearance Check
→ Bridge Window Check
→ Decision
→ Explainable Recommendation
```

---

## Slide 8: Example Recommendation

Visual idea:

System card:

```text
Trip: Tug Barge 12 → Jetty F → OGV MV X
Status: HOLD
Reason: Low tide at Segment B during ETA
Current ETA tide: +0.80 m LAT
Required minimum: +1.10 m LAT
Recommended release: 05:15 UTC / 13:15 WITA
```

---

## Slide 9: Data Architecture

Visual idea:

System blocks:

```text
BMKG / BIG Tide Data
        ↓
Tide Adapter
        ↓
Normalized Tide Series
        ↓
Route Calibration Layer
        ↓
Safe Movement Windows
        ↓
Scheduling Engine
        ↓
Dispatcher Dashboard
```

---

## Slide 10: Implementation Roadmap

| Phase | Scope |
|---|---|
| Phase 1 | Manual tide upload / BMKG download ingestion |
| Phase 2 | Station and route mapping |
| Phase 3 | Tide window generation |
| Phase 4 | Scheduling integration with GREEN/AMBER/RED decisions |
| Phase 5 | AIS/GPS validation and actual-vs-planned comparison |
| Phase 6 | Route-specific calibration and predictive recommendation |

---

# 15. Key Takeaways

1. Tide data is not just an information layer; it is a scheduling constraint.
2. MSL and LAT are different baselines for the same water level.
3. Navigation calculations must use one consistent datum.
4. The useful output is not raw tide height, but safe movement windows.
5. The system should justify wait/release decisions to reduce blame and improve operational discipline.
6. ABL should start with official BMKG/BIG data, then calibrate it using actual AIS/GPS and grounding/waiting events.
7. The final scheduling objective is to reduce grounding risk, reduce waiting waste, and improve tug-barge utilization without risking OGV commitments.

---

# 16. Suggested Stakeholder Message

The scheduling system should not simply ask whether a tug and barge are free. It should ask whether the movement will remain feasible across the entire route, including tide-sensitive shallow segments. By converting BMKG/BIG tide data into route-wise safe movement windows, ABL can create system-backed decisions for release, hold, slow-steam, or wait. This makes the operation safer, more explainable, and more synchronized.

