# 01 — Ground Reality of Berau Coal × ABL Operations

## 1. Executive summary

The operation being planned is a coal logistics and transshipment network connecting Berau Coal’s mining/coal-processing operations in East Kalimantan with ABL’s marine logistics capability. The actual planning problem is not only “where are the vessels?” but “how do we sequence coal movement from mine/stockpile/jetty into barges, through river constraints, into transshipment units, and finally into Ocean Going Vessels while protecting cargo quality, OGV timing, and fleet productivity?”

The uploaded BRD frames the business problem as replacing manual/static Excel scheduling with a real-time planning workflow between Berau Coal as the mining/scheduling party and ABL as tug-and-barge/transshipment operator. The intended workflow ingests demand, constraints, and fleet status, then produces a unified real-time fleet schedule and alerts when operational/environmental conditions change.

## 2. Berau Coal operational source context

Berau Coal’s public operations page describes PT Berau Coal as the main operating subsidiary with a 108,900 hectare mining concession in Berau Regency, approximately 300 km north of Samarinda in East Kalimantan.

The key mining areas relevant for planning are:

| Mining area | Product/brand association | Publicly described flow implication |
|---|---|---|
| Lati | Agathis and Sungkai | Coal is extracted, transported around 11 km over haul road to coal processing plant, crushed/blended/stockpiled, then loaded into barges. |
| Binungan | Ebony and Mahoni/Mahoni-B | Coal is mined, processed, and transported over a longer road distance to Suaran coal terminal, blended into product stockpile, then loaded into barges. |
| Sambarata | Ebony | Coal is transported around 2 km to CPP, crushed/blended/stockpiled, then loaded into barges. |

### Planning implication

The scheduling tool must model the upstream source of cargo, not only downstream fleet movement. For each cargo demand, the system should understand:

- Which mine/stockpile/terminal can supply the grade/product.
- Which jetty/loading point serves that product.
- Whether the required coal is already available in stockpile or dependent on processing/blending.
- Whether a product can be loaded in a required sequence for the OGV.
- Whether alternate source/jetty routing is possible if a planned source becomes constrained.

## 3. Berau product and market reality

Berau publicly lists five main coal brand names: Ebony, Mahoni, Mahoni-B, Agathis, and Sungkai. Its public marketing page describes Asia as the main export market outside the domestic market, historically including China, Taiwan, India, and South Korea.

### Planning implication

The tool should treat cargo not as a generic tonnage but as grade/product-specific demand. This is important because:

- OGV cargo plans may specify grade sequencing/layering.
- Stockpile and blending availability may differ by brand.
- A wrong barge sequence may break the planned OGV loading pattern.
- Customer/market commitments may have different priority levels.
- Demurrage risk and customer priority may influence recovery decisions.

## 4. Mine-to-river-to-transshipment flow

Berau’s shipping-devices page states that coal products are shipped through rivers. Coal is transferred to barges/tongkangs along the river and moved to transshipment points near the estuary of the Sulawesi Sea. Berau also lists several floating/transshipment assets with loading capacities such as:

| Asset publicly listed by Berau | Publicly stated loading capacity |
|---|---:|
| FTS Bulk Borneo | 32,000 MT/day |
| FTS Bulk Java | 28,000 MT/day |
| FOTP Derawan | 28,000 MT/day |
| FTS Bulk Sumatera | 30,000 MT/day |
| FC Chloe | 30,000 MT/day |
| FC Blitz | 20,000 MT/day |

### Planning implication

The operating flow is multi-leg:

1. Mine/CPP/stockpile readiness.
2. Jetty loading.
3. Barge loading and departure.
4. River movement under tide/bridge/channel constraints.
5. Arrival at transshipment area.
6. CTS/floating-crane discharge into OGV.
7. Return cycle of tug/barge.
8. Next assignment.

The tool must represent the full cycle time, not merely the loading or sailing leg.

## 5. ABL capability context

ABL’s website positions it as an integrated logistics and infrastructure solutions provider for dry bulk and other commodities. It publicly claims transshipping over 100 million tonnes annually and lists capability across transshipment, barging, OGV, rail freight, stevedoring, port management, working barges, and containers.

Publicly visible fleet/capability numbers on the ABL site include:

| Capability | Public figure |
|---|---:|
| Ocean-going vessels | 11 |
| Cargo Transfer Ships | 15 |
| Sets of tugs and barges | 61 |
| Train sets | 54 |
| Wagons | 1,596 |
| Heavy equipment | 35 |
| Containers | 14,000 |

ABL also lists a Berau office in Tanjung Redeb, Berau, East Kalimantan, indicating local operational relevance.

### Planning implication

The product should support multiple asset classes, even if the MVP starts with marine assets:

- Tug
- Barge
- Cargo Transfer Ship / Floating Transfer Station / Floating Crane
- OGV
- Jetty/port asset
- Optional later: rail, heavy equipment, containers, crew transfer vessels

## 6. ABL transshipment capability

ABL’s transshipment page describes two broad CTS modes:

| CTS type | Publicly described capacity | Notes |
|---|---:|---|
| Conveyor CTS | 40,000–55,000 ton/day | Includes 30-ton grab capacity, conveyor belt metal detector, rotating ship chute to load cargo into OGV. |
| Conventional CTS | 20,000–30,000 ton/day | Uses 30-ton crane grab and conventional loader method. |

### Planning implication

The scheduling tool must model CTS type and discharge rate because CTS is a major capacity bottleneck. The same OGV plan may have different completion times depending on whether the assigned transshipment unit is conveyor-based or conventional.

The tool should maintain:

- CTS ID
- CTS type
- daily capacity
- grab/loading method
- region/location
- compatibility with OGV/anchorage
- current assignment
- queue
- downtime/breakdown status
- expected release time

## 7. ABL barging capability

ABL’s tug page lists tug classes such as below 1200 HP, 1600 HP, 2000 HP, 2200 HP, 3200 HP, and 3300 HP, with different bollard pull capacities and regional deployment.

### Planning implication

Tug assignment should not be generic. The tool should model tug capacity and compatibility:

- Tug horsepower
- Bollard pull
- region/operating area
- compatible barge class
- loaded vs empty speed
- river/bridge/tide eligibility
- current location
- next available time
- maintenance/breakdown state

## 8. ABL OGV capability

ABL’s dry bulk page publicly describes dry-bulk vessels such as Bulk Batavia, Bulk Nusantara, and Bulk Halmahera, each around 76,000 MT DWT class, with LOA around 225 m and beam around 32 m.

### Planning implication

Even where the OGV is customer/voyage-specific and not necessarily owned by ABL, the scheduling tool must maintain OGV-level operating details:

- OGV name/voyage
- ETA/ETB/laycan
- DWT/cargo requirement
- hatch plan / layering sequence
- compatible anchorage/transshipment location
- loading/discharge plan
- demurrage risk
- customer priority

## 9. Port-management reality

ABL’s port-management page describes on-shore infrastructure including coal processing plant for crushing raw material from mining and Barge Coal Loading (BLC), transferring finished coal from stockpile to jetty via long belt conveyor. It refers to Jetty Gurimbang in East Kalimantan and a capability of approximately 6 million tonnes.

### Planning implication

The tool should not see the jetty as a simple point on a map. The jetty has a queue and loading capacity, and it connects to stockpile/CPP/conveyor infrastructure. Required entities include:

- CPP/stockpile
- conveyor/loader
- jetty
- BLC loading slot
- barge arrival/load/departure events
- stockpile grade availability
- planned vs actual loaded quantity

## 10. Operational reality summarized

The real planning environment is a synchronized network:

```text
Mine / CPP / Stockpile
        ↓
Jetty / BLC loading
        ↓
Tug + Barge river movement
        ↓
Tide / bridge / channel constraints
        ↓
CTS / FTS / FC transshipment
        ↓
Ocean Going Vessel loading
        ↓
Customer / market delivery commitment
```

The tool must therefore be a multi-resource, multi-constraint, event-driven scheduler. A map-only or vessel-tracking-only tool will not solve the core problem.

## 11. Source URLs used

- Berau Coal Energy — Operations: https://beraucoalenergy.co.id/our-profile/operation/
- Berau Coal Energy — Marketing / Our Market: https://beraucoalenergy.co.id/our-profile/our-market/
- Berau Coal Energy — Shipping Devices: https://beraucoalenergy.co.id/shipping-devices/
- ABL — Home: https://abl.co.id/
- ABL — Transshipment: https://abl.co.id/transhipment
- ABL — Tug Boat / Barging: https://abl.co.id/tug-boat
- ABL — Dry Bulk / OGV: https://abl.co.id/dry-bulk
- ABL — Port Management: https://abl.co.id/port-management
