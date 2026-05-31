/**
 * Creates the ABL Proposal Fact Verification Google Form.
 * Run createABLProposalFactVerificationForm() from Apps Script while signed into thapa.santosh@gmail.com.
 */
const FORM_DEF = {
  "title": "ABL Proposal Fact Verification Questionnaire",
  "description": "Business-owner verification questionnaire for facts assumed in the ABL Flow Management and Transshipment Scheduling proposal. Please answer with facts, source documents, screenshots, sample files, data dictionaries or system extracts where available. Questions are grouped by operating topic; each section is capped at 10 questions.",
  "sections": [
    {
      "number": 1,
      "title": "1. Operating Scope, Ownership and Control Boundaries",
      "questions": [
        {
          "no": "1.1",
          "question": "Which parts of the Berau flow are directly operated by ABL: port facility, coal processing/blending, stockpile handling, jetty queue, BLC operation, tug-barge dispatch, CTS/floating crane operation, OGV loading coordination, survey coordination, documentation closure?",
          "expected": "Checklist with owner per activity: ABL / Berau / contractor / surveyor / agent / other.",
          "type": "CHECKBOX_GRID",
          "rows": [
            "Port facility",
            "Coal processing / blending",
            "Stockpile handling",
            "Jetty queue",
            "BLC operation",
            "Tug-barge dispatch",
            "CTS / floating crane operation",
            "OGV loading coordination",
            "Survey coordination",
            "Documentation closure"
          ],
          "columns": [
            "ABL",
            "Berau",
            "Contractor",
            "Surveyor",
            "Agent",
            "Other / unknown"
          ],
          "help": "Checklist with owner per activity: ABL / Berau / contractor / surveyor / agent / other."
        },
        {
          "no": "1.2",
          "question": "What is ABL's decision authority for each operating layer: can ABL decide, recommend, execute after approval, or only receive instruction?",
          "expected": "Matrix: activity vs decision authority.",
          "type": "GRID",
          "rows": [
            "Demand / OGV plan",
            "Source-jetty plan",
            "Coal quality / blend plan",
            "Jetty loading sequence",
            "Tug-barge assignment",
            "CTS / floating crane assignment",
            "Route deviation / intentional waiting",
            "Charter mobilization"
          ],
          "columns": [
            "Can decide",
            "Can recommend",
            "Execute after approval",
            "Receive instruction only",
            "Not involved"
          ],
          "help": "Matrix: activity vs decision authority."
        },
        {
          "no": "1.3",
          "question": "Which Berau-side functions create or modify the demand plan, source-jetty plan, coal quality plan, and OGV loading priority?",
          "expected": "Text response with role/team names.",
          "type": "SHORT_TEXT",
          "help": "Text response with role/team names."
        },
        {
          "no": "1.4",
          "question": "What formal handoff points exist between Berau and ABL from cargo plan release to OGV departure?",
          "expected": "Process step list with document/system used at each handoff.",
          "type": "PARAGRAPH",
          "help": "Process step list with document/system used at each handoff. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "1.5",
          "question": "Which locations are in scope for the current proposal: mine/CPP/stockpile names, jetties, river routes, transshipment points, anchorage zones, OGV loading areas?",
          "expected": "Location list with codes/names and map if available.",
          "type": "PARAGRAPH",
          "help": "Location list with codes/names and map if available. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "1.6",
          "question": "Are Lati, Binungan, Sambarata and Suaran/KM locations part of the active operating scope for this proposal?",
          "expected": "Yes/no per location with current operational role.",
          "type": "GRID",
          "rows": [
            "Lati",
            "Binungan",
            "Sambarata",
            "Suaran / KM locations"
          ],
          "columns": [
            "Active scope",
            "Reference only",
            "Not in scope",
            "Unknown"
          ],
          "help": "Yes/no per location with current operational role."
        },
        {
          "no": "1.7",
          "question": "What entities own the operational KPIs for jetty productivity, fleet utilization, CTS productivity, OGV completion, demurrage, and safety?",
          "expected": "KPI owner table.",
          "type": "PARAGRAPH",
          "help": "KPI owner table. Paste a table or provide a link to the source file if easier."
        }
      ]
    },
    {
      "number": 2,
      "title": "2. Demand, OGV Programme and Customer Commitments",
      "questions": [
        {
          "no": "2.1",
          "question": "What demand fields does ABL receive today for each OGV or shipment: vessel name, voyage, buyer, quantity, coal grade, laycan, ETA/ETB, priority, source jetty, hatch plan, layering sequence, completion target?",
          "expected": "Checklist with field source and format.",
          "type": "CHECKBOX",
          "choices": [
            "vessel name",
            "voyage",
            "buyer",
            "quantity",
            "coal grade",
            "laycan",
            "ETA/ETB",
            "priority",
            "source jetty",
            "hatch plan",
            "layering sequence",
            "completion target",
            "Other / not listed"
          ],
          "help": "Checklist with field source and format."
        },
        {
          "no": "2.2",
          "question": "How often is the OGV programme updated: monthly, weekly, daily, intra-day, or event-driven?",
          "expected": "Frequency plus examples of actual update cadence.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Monthly",
            "Weekly",
            "Daily",
            "Intra-day",
            "Event-driven",
            "Not fixed / varies"
          ],
          "help": "Frequency plus examples of actual update cadence."
        },
        {
          "no": "2.3",
          "question": "What is the current change notification process when Berau changes source jetty, buyer requirement, coal quality, quantity, or OGV timing?",
          "expected": "Process description with communication channel and approval owner.",
          "type": "PARAGRAPH",
          "help": "Process description with communication channel and approval owner."
        },
        {
          "no": "2.4",
          "question": "Are OGV hatch plans and layering sequences available before barge assignment, during execution, or only at OGV loading stage?",
          "expected": "Multiple choice plus sample document if available.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Before barge assignment",
            "During execution",
            "Only at OGV loading stage",
            "Not available",
            "Varies by shipment"
          ],
          "help": "Multiple choice plus sample document if available."
        },
        {
          "no": "2.5",
          "question": "What fields identify shipment priority or customer urgency in the current plan?",
          "expected": "Field name/value examples or note if informal.",
          "type": "PARAGRAPH",
          "help": "Field name/value examples or note if informal."
        },
        {
          "no": "2.6",
          "question": "How is demurrage risk currently calculated or recognized: by date threshold, laycan breach, OGV waiting time, manual escalation, or no formal calculation?",
          "expected": "Text response with formula/rule if any.",
          "type": "PARAGRAPH",
          "help": "Text response with formula/rule if any. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "2.7",
          "question": "What are typical OGV cargo sizes and typical barge-load counts per OGV by cargo type or barge size?",
          "expected": "Numeric ranges and representative example.",
          "type": "PARAGRAPH",
          "help": "Numeric ranges and representative example. Paste a table or provide a link to the source file if easier."
        }
      ]
    },
    {
      "number": 3,
      "title": "3. Mine, CPP, Stockpile, Cargo Quality and Blending",
      "questions": [
        {
          "no": "3.1",
          "question": "What cargo-readiness levels are visible to ABL today: mine production readiness, CPP output, stockpile quantity, jetty availability, blend plan, sample status, quality release, or ready-to-load status?",
          "expected": "Checklist with source and update frequency.",
          "type": "CHECKBOX_GRID",
          "rows": [
            "Mine production readiness",
            "CPP output",
            "Stockpile quantity",
            "Jetty availability",
            "Blend plan",
            "Sample status",
            "Quality release",
            "Ready-to-load status"
          ],
          "columns": [
            "Excel / file",
            "System / database",
            "Manual report / chat",
            "Vendor platform",
            "Not available",
            "Unknown"
          ],
          "help": "Checklist with source and update frequency."
        },
        {
          "no": "3.2",
          "question": "Which coal quality parameters are used operationally for scheduling or assignment: CV, ash, moisture, sulphur, fines, contamination, brand/grade, buyer spec, other?",
          "expected": "Checklist with parameter owner.",
          "type": "CHECKBOX_GRID",
          "rows": [
            "CV",
            "ash",
            "moisture",
            "sulphur",
            "fines",
            "contamination",
            "brand/grade",
            "buyer spec"
          ],
          "columns": [
            "ABL",
            "Berau",
            "Contractor / vendor",
            "Other",
            "Unknown"
          ],
          "help": "Checklist with parameter owner."
        },
        {
          "no": "3.3",
          "question": "Does ABL receive the blend recipe or only the final required grade/brand for execution?",
          "expected": "Multiple choice with sample artifact.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Available before execution",
            "Available during execution",
            "Available after execution",
            "Not available",
            "Unknown / varies"
          ],
          "help": "Multiple choice with sample artifact."
        },
        {
          "no": "3.4",
          "question": "When one OGV uses cargo from multiple jetties or grades, how is the required loading sequence communicated to ABL?",
          "expected": "Process description and document/source.",
          "type": "PARAGRAPH",
          "help": "Process description and document/source."
        },
        {
          "no": "3.5",
          "question": "How is quality-locking handled when a barge has been assigned to a buyer/OGV/grade combination?",
          "expected": "Text response with reassignment rules.",
          "type": "PARAGRAPH",
          "help": "Text response with reassignment rules."
        },
        {
          "no": "3.6",
          "question": "Are rain, moisture change, stockpile age, drainage, rehandling, or contamination events captured as operational constraints today?",
          "expected": "Checklist with event source and impact rule.",
          "type": "CHECKBOX",
          "choices": [
            "Other / not listed"
          ],
          "help": "Checklist with event source and impact rule."
        },
        {
          "no": "3.7",
          "question": "What are the current status values for cargo quality or release: planned, sampled, released, blocked, disputed, under recheck, ready-to-load, other?",
          "expected": "Status list with definitions.",
          "type": "PARAGRAPH",
          "help": "Status list with definitions. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "3.8",
          "question": "Are blocked/disputed quantities visible in the operating plan before tug-barge dispatch?",
          "expected": "Yes/no/partial plus data source.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Yes",
            "No",
            "Partial",
            "Unknown / not currently available"
          ],
          "help": "Yes/no/partial plus data source."
        },
        {
          "no": "3.9",
          "question": "What is the normal lead time between quality release and physical BLC/jetty loading?",
          "expected": "Numeric range by jetty/grade if available.",
          "type": "PARAGRAPH",
          "help": "Numeric range by jetty/grade if available. Paste a table or provide a link to the source file if easier."
        }
      ]
    },
    {
      "number": 4,
      "title": "4. Port, Jetty and BLC Operations",
      "questions": [
        {
          "no": "4.1",
          "question": "Which jetties and BLCs are currently used for the operation, and what are their operating codes/names?",
          "expected": "Master-data list.",
          "type": "PARAGRAPH",
          "help": "Master-data list. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "4.2",
          "question": "What is the confirmed BLC capacity by loading point, and is 2,000 tph the correct planning value for the main BLC?",
          "expected": "Numeric value by asset with source.",
          "type": "PARAGRAPH",
          "help": "Numeric value by asset with source. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "4.3",
          "question": "What is the typical barge loading duration by jetty, cargo type, and barge size?",
          "expected": "Numeric range/table.",
          "type": "PARAGRAPH",
          "help": "Numeric range/table. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "4.4",
          "question": "What is the typical pre-loading waiting time at each jetty, and how often does it exceed the planning assumption?",
          "expected": "Numeric range/table plus comments.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Monthly",
            "Weekly",
            "Daily",
            "Intra-day",
            "Event-driven",
            "Not fixed / varies"
          ],
          "help": "Numeric range/table plus comments."
        },
        {
          "no": "4.5",
          "question": "What operational statuses exist for a jetty/BLC: available, queueing, loading, breakdown, maintenance, no cargo, weather hold, survey hold, other?",
          "expected": "Status list with definitions.",
          "type": "PARAGRAPH",
          "help": "Status list with definitions. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "4.6",
          "question": "Is jetty queue currently captured as a structured queue with vessel/barge sequence, or managed informally by field coordination?",
          "expected": "Multiple choice plus sample if structured.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Structured queue with sequence",
            "Partly structured",
            "Managed informally",
            "Not confirmed"
          ],
          "help": "Multiple choice plus sample if structured."
        },
        {
          "no": "4.7",
          "question": "What data is available for BLC downtime, loader rate, loading start/end, queue arrival, queue release, and loading completion?",
          "expected": "Field list with source and update frequency.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Monthly",
            "Weekly",
            "Daily",
            "Intra-day",
            "Event-driven",
            "Not fixed / varies"
          ],
          "help": "Field list with source and update frequency."
        },
        {
          "no": "4.8",
          "question": "Are survey or inspection readiness checks required before jetty loading, or are they relevant only at OGV loading/closure?",
          "expected": "Text response by stage.",
          "type": "PARAGRAPH",
          "help": "Text response by stage."
        }
      ]
    },
    {
      "number": 5,
      "title": "5. Tug-Barge Fleet, Route Cycle and Closed-Loop Availability",
      "questions": [
        {
          "no": "5.1",
          "question": "What is the current owned and chartered fleet count by asset class: tug, barge, self-propelled barge, assist tug, support craft?",
          "expected": "Master-data table.",
          "type": "PARAGRAPH",
          "help": "Master-data table. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "5.2",
          "question": "What vessel identifiers are used across systems: asset code, AIS MMSI, IMO, tug/barge name, Spinergie ID, internal ERP ID?",
          "expected": "ID-mapping table.",
          "type": "PARAGRAPH",
          "help": "ID-mapping table. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "5.3",
          "question": "What tug HP range and barge capacity range should be used for planning?",
          "expected": "Numeric range by asset class.",
          "type": "PARAGRAPH",
          "help": "Numeric range by asset class. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "5.4",
          "question": "What are the standard route cycle components currently tracked: assignment time, departure, arrival jetty, queue start, loading start/end, departure loaded, arrival CTS/OGV, discharge start/end, return start, available time?",
          "expected": "Checklist with source per event.",
          "type": "CHECKBOX_GRID",
          "rows": [
            "Assignment time",
            "Departure",
            "Arrival at jetty",
            "Queue start",
            "Loading start/end",
            "Departure loaded",
            "Arrival at CTS/OGV",
            "Discharge start/end",
            "Return start",
            "Available time"
          ],
          "columns": [
            "Excel / file",
            "System / database",
            "Manual report / chat",
            "Vendor platform",
            "Not available",
            "Unknown"
          ],
          "help": "Checklist with source per event."
        },
        {
          "no": "5.5",
          "question": "Are loaded sailing time and empty return time separately measured today?",
          "expected": "Yes/no/partial plus sample data.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Yes",
            "No",
            "Partial",
            "Unknown / not currently available"
          ],
          "help": "Yes/no/partial plus sample data."
        },
        {
          "no": "5.6",
          "question": "What are the planning cycle-time ranges for each active route, including near, medium and far jetties?",
          "expected": "Route-time table.",
          "type": "PARAGRAPH",
          "help": "Route-time table. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "5.7",
          "question": "Are the indicative assumptions valid: nearby movement around 9-12 hours plus loading/unloading, farthest movement around 48-70 hours?",
          "expected": "Confirm/correct with route examples.",
          "type": "PARAGRAPH",
          "help": "Confirm/correct with route examples."
        },
        {
          "no": "5.8",
          "question": "How is mid-route reassignment recorded when a tug-barge is redirected to another jetty, OGV or buyer?",
          "expected": "Text response plus event/status fields.",
          "type": "PARAGRAPH",
          "help": "Text response plus event/status fields."
        },
        {
          "no": "5.9",
          "question": "What makes an asset \"available\" for next assignment: discharge complete, return started, arrived safe point, empty at jetty, crew ready, maintenance clear, other?",
          "expected": "Definition list.",
          "type": "PARAGRAPH",
          "help": "Definition list. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "5.10",
          "question": "Are breakdown, maintenance, crew availability and inspection status captured in a structured way?",
          "expected": "Checklist with source.",
          "type": "CHECKBOX",
          "choices": [
            "Other / not listed"
          ],
          "help": "Checklist with source."
        }
      ]
    },
    {
      "number": 6,
      "title": "6. Tide, Bridge, River Navigation and Safety Constraints",
      "questions": [
        {
          "no": "6.1",
          "question": "What tide data source is used for dispatch planning, and what format is available: PDF/table, Excel, API, website, internal system, manual update?",
          "expected": "Source and format description.",
          "type": "PARAGRAPH",
          "help": "Source and format description."
        },
        {
          "no": "6.2",
          "question": "What bridge-window data source is used, and is it available as structured time windows?",
          "expected": "Source, format, update frequency.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Monthly",
            "Weekly",
            "Daily",
            "Intra-day",
            "Event-driven",
            "Not fixed / varies"
          ],
          "help": "Source, format, update frequency."
        },
        {
          "no": "6.3",
          "question": "Which river segments, bridges, draft restrictions, choke points, and safe waiting points must be represented in the schedule?",
          "expected": "Route constraint list/map.",
          "type": "PARAGRAPH",
          "help": "Route constraint list/map. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "6.4",
          "question": "What vessel, barge, cargo, tide-height or draft rules determine whether a movement is safe?",
          "expected": "Rule table or operational guideline.",
          "type": "PARAGRAPH",
          "help": "Rule table or operational guideline. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "6.5",
          "question": "How is grounding currently recorded: event type, delay code, safety incident, operational exception, or informal report?",
          "expected": "Status/event code list.",
          "type": "PARAGRAPH",
          "help": "Status/event code list. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "6.6",
          "question": "What data exists for historical missed tide windows, bridge waits, grounding, traffic congestion and weather-related stoppage?",
          "expected": "Dataset/source list with date range.",
          "type": "PARAGRAPH",
          "help": "Dataset/source list with date range. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "6.7",
          "question": "What are the current field rules for intentional waiting at a safe point before a tide/bridge bottleneck?",
          "expected": "Text response with approval owner.",
          "type": "PARAGRAPH",
          "help": "Text response with approval owner."
        },
        {
          "no": "6.8",
          "question": "Are speed adjustments used operationally to align with tide/bridge windows, and are they recorded anywhere?",
          "expected": "Yes/no/partial plus source.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Yes",
            "No",
            "Partial",
            "Unknown / not currently available"
          ],
          "help": "Yes/no/partial plus source."
        }
      ]
    },
    {
      "number": 7,
      "title": "7. CTS, Floating Crane, Transshipment and OGV Loading",
      "questions": [
        {
          "no": "7.1",
          "question": "Which CTS, FTS and floating crane assets are in scope, and what are their operating names/codes?",
          "expected": "Asset master list.",
          "type": "PARAGRAPH",
          "help": "Asset master list. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "7.2",
          "question": "What is the confirmed daily capacity or discharge rate for each CTS/floating crane, and is 55,000 t/day a valid peak planning value?",
          "expected": "Numeric table by asset.",
          "type": "PARAGRAPH",
          "help": "Numeric table by asset. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "7.3",
          "question": "Which capability attributes matter for assignment: conveyor, crane-and-grab, sampler, metal detector, rotating chute, blending capability, hatch reach, weather limit, other?",
          "expected": "Checklist by asset.",
          "type": "CHECKBOX_GRID",
          "rows": [
            "Conveyor",
            "Crane-and-grab",
            "Sampler",
            "Metal detector",
            "Rotating chute",
            "Blending capability",
            "Hatch reach",
            "Weather limit"
          ],
          "columns": [
            "Available / applicable",
            "Not available / not applicable",
            "Unknown"
          ],
          "help": "Checklist by asset."
        },
        {
          "no": "7.4",
          "question": "Is CTS/floating crane queue captured as a structured queue, and does it link to OGV/hatch sequence?",
          "expected": "Multiple choice plus sample.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Structured and linked to OGV/hatch sequence",
            "Structured but not linked",
            "Partly structured",
            "Informal only",
            "Not confirmed"
          ],
          "help": "Multiple choice plus sample."
        },
        {
          "no": "7.5",
          "question": "What event timestamps are captured for CTS execution: barge arrived, discharge start, discharge end, CTS downtime, hatch change, OGV loading complete?",
          "expected": "Checklist with source.",
          "type": "CHECKBOX_GRID",
          "rows": [
            "Barge arrived",
            "Discharge start",
            "Discharge end",
            "CTS downtime",
            "Hatch change",
            "OGV loading complete"
          ],
          "columns": [
            "Excel / file",
            "System / database",
            "Manual report / chat",
            "Vendor platform",
            "Not available",
            "Unknown"
          ],
          "help": "Checklist with source."
        },
        {
          "no": "7.6",
          "question": "How are CTS downtime and productivity losses categorized today?",
          "expected": "Reason-code list.",
          "type": "PARAGRAPH",
          "help": "Reason-code list. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "7.7",
          "question": "Is OGV loading progress tracked by hatch, by cargo grade, by barge, by tonnage, or only at total-vessel level?",
          "expected": "Multiple choice with sample.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "By hatch",
            "By cargo grade",
            "By barge",
            "By tonnage",
            "Total-vessel level only",
            "Not tracked"
          ],
          "help": "Multiple choice with sample."
        },
        {
          "no": "7.8",
          "question": "What happens operationally if barge arrival sequence conflicts with hatch/layering plan?",
          "expected": "Text response with escalation path.",
          "type": "PARAGRAPH",
          "help": "Text response with escalation path."
        }
      ]
    },
    {
      "number": 8,
      "title": "8. Survey, Certification and Shipment Closure",
      "questions": [
        {
          "no": "8.1",
          "question": "Which survey milestones are mandatory for the operation: hold inspection, initial draft survey, sampling, barge-wise quantity record, loading supervision, final draft survey, certificate of weight, certificate of quality, statement of facts?",
          "expected": "Checklist with responsible party.",
          "type": "CHECKBOX_GRID",
          "rows": [
            "Hold inspection",
            "Initial draft survey",
            "Sampling",
            "Barge-wise quantity record",
            "Loading supervision",
            "Final draft survey",
            "Certificate of weight",
            "Certificate of quality",
            "Statement of facts"
          ],
          "columns": [
            "ABL",
            "Berau",
            "Surveyor",
            "Agent",
            "Contractor",
            "Unknown"
          ],
          "help": "Checklist with responsible party."
        },
        {
          "no": "8.2",
          "question": "Which survey milestones can block loading, OGV completion or departure?",
          "expected": "Checklist with blocker definition.",
          "type": "CHECKBOX",
          "choices": [
            "Other / not listed"
          ],
          "help": "Checklist with blocker definition."
        },
        {
          "no": "8.3",
          "question": "Where are survey milestone statuses recorded today: Excel, surveyor report, email, Spinergie/SOF, operational database, WhatsApp, other?",
          "expected": "Source list.",
          "type": "PARAGRAPH",
          "help": "Source list. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "8.4",
          "question": "Are certificate dates/times and document closure dates/times available as data fields?",
          "expected": "Yes/no/partial plus sample.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Yes",
            "No",
            "Partial",
            "Unknown / not currently available"
          ],
          "help": "Yes/no/partial plus sample."
        },
        {
          "no": "8.5",
          "question": "Who confirms shipment closure and OGV departure readiness?",
          "expected": "Role/team response.",
          "type": "SHORT_TEXT",
          "help": "Role/team response."
        },
        {
          "no": "8.6",
          "question": "Are operational exceptions recorded before statement-of-facts closure?",
          "expected": "Yes/no/partial with process description.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Yes",
            "No",
            "Partial",
            "Unknown / not currently available"
          ],
          "help": "Yes/no/partial with process description."
        }
      ]
    },
    {
      "number": 9,
      "title": "9. Spinergie, AIS and Live Position Data: Technical Verification",
      "questions": [
        {
          "no": "9.1",
          "question": "Which Spinergie modules are actively used in the Berau operation: Smart Fleet Management, live map, AIS tracking, reporting, daily reports, statement of facts, activity tracking, fuel/ROB, performance dashboards?",
          "expected": "Checklist with usage level: active / occasional / not used.",
          "type": "CHECKBOX_GRID",
          "rows": [
            "Smart Fleet Management",
            "Live map",
            "AIS tracking",
            "Reporting",
            "Daily reports",
            "Statement of facts",
            "Activity tracking",
            "Fuel/ROB",
            "Performance dashboards"
          ],
          "columns": [
            "Active",
            "Occasional",
            "Not used",
            "Unknown"
          ],
          "help": "Checklist with usage level: active / occasional / not used."
        },
        {
          "no": "9.2",
          "question": "What is the current method for accessing Spinergie data: web UI only, scheduled export, manual report download, API, database extract, webhook/event feed, or vendor-managed integration?",
          "expected": "Multiple choice plus details.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Web UI only",
            "Scheduled export",
            "Manual report download",
            "API",
            "Database extract",
            "Webhook / event feed",
            "Vendor-managed integration",
            "Not currently available"
          ],
          "help": "Multiple choice plus details."
        },
        {
          "no": "9.3",
          "question": "If an API exists, what API type is available: REST, GraphQL, SOAP, streaming API, webhook, SFTP file drop, other?",
          "expected": "Interface type and vendor documentation if available.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "REST API",
            "GraphQL",
            "SOAP",
            "Streaming API",
            "Webhook",
            "SFTP file drop",
            "No API confirmed yet"
          ],
          "help": "Interface type and vendor documentation if available."
        },
        {
          "no": "9.4",
          "question": "What authentication method is used or available for integration: API key, OAuth2, bearer token, basic auth, IP allowlist, VPN, SFTP credentials, vendor-managed token, other?",
          "expected": "Technical description.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "API key",
            "OAuth2",
            "Bearer token",
            "Basic auth",
            "IP allowlist",
            "VPN",
            "SFTP credentials",
            "Vendor-managed token",
            "Not confirmed"
          ],
          "help": "Technical description."
        },
        {
          "no": "9.5",
          "question": "What data format can be shared: JSON, CSV, Excel, XML, PDF report, database view, Parquet, other?",
          "expected": "Format list with sample file.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "JSON",
            "CSV",
            "Excel",
            "XML",
            "PDF report",
            "Database view",
            "Parquet",
            "Not confirmed"
          ],
          "help": "Format list with sample file."
        },
        {
          "no": "9.6",
          "question": "What is the available data refresh cadence for live position: real-time, 1-minute, 5-minute, 15-minute, hourly, daily report, manual export?",
          "expected": "Cadence value by data type.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Real-time",
            "1-minute",
            "5-minute",
            "15-minute",
            "Hourly",
            "Daily report",
            "Manual export",
            "Not confirmed"
          ],
          "help": "Cadence value by data type."
        },
        {
          "no": "9.8",
          "question": "What fields are available in each AIS/position record: timestamp, latitude, longitude, speed, heading, course, MMSI, asset name, tug/barge link, source system ID, geofence, status, destination, ETA?",
          "expected": "Field dictionary or sample extract.",
          "type": "PARAGRAPH",
          "help": "Field dictionary or sample extract."
        },
        {
          "no": "9.11",
          "question": "Are geofence events available directly from Spinergie, or must geofence events be generated by the new platform from raw AIS coordinates?",
          "expected": "Multiple choice plus available geofence list.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Available directly from Spinergie",
            "Must be generated from raw AIS coordinates",
            "Both are available",
            "Not confirmed"
          ],
          "help": "Multiple choice plus available geofence list."
        },
        {
          "no": "9.19",
          "question": "Can Spinergie exports be joined to Excel schedule data through a stable key such as asset code, MMSI, trip ID, OGV name, jetty code or timestamp range?",
          "expected": "Join-key mapping.",
          "type": "PARAGRAPH",
          "help": "Join-key mapping. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "9.20",
          "question": "What data-sharing approach is feasible for the current build phase: one-time historical extract, daily CSV export, scheduled SFTP feed, API polling, webhook feed, database view, manual upload?",
          "expected": "Preferred method plus constraints.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "One-time historical extract",
            "Daily CSV export",
            "Scheduled SFTP feed",
            "API polling",
            "Webhook feed",
            "Database view",
            "Manual upload",
            "Not feasible / not confirmed"
          ],
          "help": "Preferred method plus constraints."
        }
      ]
    },
    {
      "number": 10,
      "title": "10. Excel, Master Data and Operational Report Data",
      "questions": [
        {
          "no": "10.1",
          "question": "What Excel planning files are currently used, and what is the owner, update frequency and file structure for each?",
          "expected": "File inventory.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Monthly",
            "Weekly",
            "Daily",
            "Intra-day",
            "Event-driven",
            "Not fixed / varies"
          ],
          "help": "File inventory."
        },
        {
          "no": "10.2",
          "question": "Which master-data lists already exist: jetties, routes, tug assets, barges, CTS assets, OGVs, cargo grades, buyers, reason codes, tide/bridge windows?",
          "expected": "Checklist with source file/system.",
          "type": "CHECKBOX_GRID",
          "rows": [
            "Jetties",
            "Routes",
            "Tug assets",
            "Barges",
            "CTS assets",
            "OGVs",
            "Cargo grades",
            "Buyers",
            "Reason codes",
            "Tide/bridge windows"
          ],
          "columns": [
            "Excel / file",
            "System / database",
            "Manual report / chat",
            "Vendor platform",
            "Not available",
            "Unknown"
          ],
          "help": "Checklist with source file/system."
        },
        {
          "no": "10.3",
          "question": "Are asset master IDs consistent across Excel, Spinergie, AIS, operational reports and finance/charter records?",
          "expected": "Yes/no/partial plus mismatch examples.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Yes",
            "No",
            "Partial",
            "Unknown / not currently available"
          ],
          "help": "Yes/no/partial plus mismatch examples."
        },
        {
          "no": "10.4",
          "question": "What fields define route master data: origin, destination, distance, standard loaded time, standard empty time, tide dependency, bridge dependency, draft restriction, safe waiting point?",
          "expected": "Field list with sample.",
          "type": "PARAGRAPH",
          "help": "Field list with sample. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "10.5",
          "question": "Are delay and waiting reason codes standardized today?",
          "expected": "Yes/no/partial plus code list.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Yes",
            "No",
            "Partial",
            "Unknown / not currently available"
          ],
          "help": "Yes/no/partial plus code list."
        },
        {
          "no": "10.6",
          "question": "What historical operational reports are available for calibration of waiting time, cycle time and productivity?",
          "expected": "Dataset list with date range.",
          "type": "PARAGRAPH",
          "help": "Dataset list with date range. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "10.7",
          "question": "Can operational reports be shared as structured data rather than PDF/image/manual notes?",
          "expected": "Available formats and constraints.",
          "type": "PARAGRAPH",
          "help": "Available formats and constraints."
        },
        {
          "no": "10.8",
          "question": "What data fields are required to calculate planned-vs-actual at trip level?",
          "expected": "Confirm/correct field list.",
          "type": "PARAGRAPH",
          "help": "Confirm/correct field list. Paste a table or provide a link to the source file if easier."
        }
      ]
    },
    {
      "number": 11,
      "title": "11. Event Model and Business-State Inference",
      "questions": [
        {
          "no": "11.1",
          "question": "Which business states are valid for a tug-barge trip: planned, assigned, en route empty, arrived jetty, waiting jetty, loading, loaded, en route loaded, waiting tide/bridge, arrived CTS/OGV, discharging, discharged, returning, available, breakdown, maintenance, reassigned, cancelled?",
          "expected": "Status list with definitions.",
          "type": "PARAGRAPH",
          "help": "Status list with definitions. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "11.2",
          "question": "Which of these states are confirmed manually, which can be inferred from AIS/geofence, and which need both?",
          "expected": "State vs source matrix.",
          "type": "PARAGRAPH",
          "help": "State vs source matrix."
        },
        {
          "no": "11.3",
          "question": "What event timestamps are mandatory for operational control versus only useful for analytics?",
          "expected": "Event priority list.",
          "type": "PARAGRAPH",
          "help": "Event priority list. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "11.4",
          "question": "What confidence level is acceptable for inferred events before planner confirmation is required?",
          "expected": "Rule/threshold response.",
          "type": "PARAGRAPH",
          "help": "Rule/threshold response."
        },
        {
          "no": "11.5",
          "question": "How should conflicting signals be resolved, for example AIS shows arrived but field report says still waiting outside jetty?",
          "expected": "Business rule response.",
          "type": "PARAGRAPH",
          "help": "Business rule response."
        },
        {
          "no": "11.6",
          "question": "Which exception events require immediate alerting: missed tide, bridge wait, grounding risk, breakdown, cargo hold, OGV delay, CTS queue, survey hold, reassignment?",
          "expected": "Alert priority list.",
          "type": "PARAGRAPH",
          "help": "Alert priority list. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "11.7",
          "question": "Are current WhatsApp/voice updates structured enough to convert into reason codes, or do new field-event forms need to be introduced?",
          "expected": "Multiple choice plus examples.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Structured enough today",
            "Partly structured",
            "Requires new field-event forms",
            "Not confirmed"
          ],
          "help": "Multiple choice plus examples."
        }
      ]
    },
    {
      "number": 12,
      "title": "12. Third-Party Charter Fleet and Capacity Planning",
      "questions": [
        {
          "no": "12.1",
          "question": "How many tugboats and barges are owned versus chartered in the operating scope?",
          "expected": "Numeric table.",
          "type": "PARAGRAPH",
          "help": "Numeric table. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "12.2",
          "question": "What is the normal process for requesting, inspecting, approving and mobilizing a charter tug?",
          "expected": "Process steps and lead time.",
          "type": "PARAGRAPH",
          "help": "Process steps and lead time."
        },
        {
          "no": "12.3",
          "question": "Is one week a reliable planning assumption for charter tug readiness?",
          "expected": "Confirm/correct numeric range.",
          "type": "PARAGRAPH",
          "help": "Confirm/correct numeric range. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "12.4",
          "question": "What statuses exist for charter assets: requested, vendor confirmed, inspection pending, inspection passed, mobilizing, ready, rejected, unavailable?",
          "expected": "Status list.",
          "type": "PARAGRAPH",
          "help": "Status list. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "12.5",
          "question": "Are charter costs or commercial constraints considered in dispatch/recovery decisions?",
          "expected": "Yes/no/partial plus owner.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Yes",
            "No",
            "Partial",
            "Unknown / not currently available"
          ],
          "help": "Yes/no/partial plus owner."
        },
        {
          "no": "12.6",
          "question": "Are third-party assets tracked in the same planning files and AIS systems as owned assets?",
          "expected": "Yes/no/partial with source.",
          "type": "MULTIPLE_CHOICE",
          "choices": [
            "Yes",
            "No",
            "Partial",
            "Unknown / not currently available"
          ],
          "help": "Yes/no/partial with source."
        }
      ]
    },
    {
      "number": 13,
      "title": "13. Governance, KPIs, Decision Rights and Adoption",
      "questions": [
        {
          "no": "13.1",
          "question": "Who approves source-jetty changes, cargo reassignment, tug-barge reassignment, intentional waiting, route deviation, and charter mobilization?",
          "expected": "Decision-right matrix.",
          "type": "PARAGRAPH",
          "help": "Decision-right matrix."
        },
        {
          "no": "13.2",
          "question": "What is the current escalation path for OGV delay, quality hold, grounding risk, CTS congestion and fleet shortage?",
          "expected": "Escalation process.",
          "type": "PARAGRAPH",
          "help": "Escalation process."
        },
        {
          "no": "13.3",
          "question": "Which KPIs are currently measured by ABL, and which are measured by Berau or other parties?",
          "expected": "KPI table with owner and formula.",
          "type": "PARAGRAPH",
          "help": "KPI table with owner and formula. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "13.4",
          "question": "What formulas are used for fleet productive time, floating crane productive time, waiting time, idle time, OGV delay and demurrage risk?",
          "expected": "Formula list.",
          "type": "PARAGRAPH",
          "help": "Formula list. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "13.5",
          "question": "Are fleet productive time around 55-60% and floating crane productive time around 35% current accepted baselines?",
          "expected": "Confirm/correct with date period.",
          "type": "PARAGRAPH",
          "help": "Confirm/correct with date period."
        },
        {
          "no": "13.6",
          "question": "What delay attribution categories are acceptable for operational reporting: jetty queue, cargo hold, tide wait, bridge wait, CTS queue, OGV delay, survey, breakdown, instruction wait, weather, other?",
          "expected": "Reason-code list.",
          "type": "PARAGRAPH",
          "help": "Reason-code list. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "13.7",
          "question": "Which user groups will operate or consume the platform: planner, dispatcher, field coordinator, tug master, CTS operator, port/BLC user, Berau planner, management, IT admin?",
          "expected": "User-role list.",
          "type": "PARAGRAPH",
          "help": "User-role list. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "13.8",
          "question": "What language, device, connectivity and access constraints exist for field users?",
          "expected": "Text response.",
          "type": "PARAGRAPH",
          "help": "Text response."
        },
        {
          "no": "13.9",
          "question": "What operating process changes are already acceptable: standard event reporting, reason codes, approval workflow, planned-vs-actual review, daily control-tower meeting?",
          "expected": "Checklist with adoption constraints.",
          "type": "CHECKBOX_GRID",
          "rows": [
            "Standard event reporting",
            "Reason codes",
            "Approval workflow",
            "Planned-vs-actual review",
            "Daily control-tower meeting"
          ],
          "columns": [
            "Available / applicable",
            "Not available / not applicable",
            "Unknown"
          ],
          "help": "Checklist with adoption constraints."
        }
      ]
    },
    {
      "number": 14,
      "title": "14. Validation Inputs Requested",
      "questions": [
        {
          "no": "14.1",
          "question": "Latest OGV programme and historical OGV schedule changes.",
          "expected": "Excel/CSV with 3-6 months history.",
          "type": "PARAGRAPH",
          "help": "Excel/CSV with 3-6 months history."
        },
        {
          "no": "14.2",
          "question": "Current Excel scheduling files used by ABL.",
          "expected": "Native Excel files.",
          "type": "PARAGRAPH",
          "help": "Native Excel files."
        },
        {
          "no": "14.3",
          "question": "Tug, barge, CTS and jetty master data.",
          "expected": "Excel/CSV with IDs and names.",
          "type": "PARAGRAPH",
          "help": "Excel/CSV with IDs and names."
        },
        {
          "no": "14.4",
          "question": "Route and cycle-time assumptions.",
          "expected": "Table by origin/destination.",
          "type": "PARAGRAPH",
          "help": "Table by origin/destination. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "14.5",
          "question": "Tide, bridge and draft restriction data.",
          "expected": "Structured table/API details where available.",
          "type": "PARAGRAPH",
          "help": "Structured table/API details where available. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "14.6",
          "question": "Spinergie/AIS sample export and data dictionary.",
          "expected": "CSV/JSON sample plus field definitions.",
          "type": "PARAGRAPH",
          "help": "CSV/JSON sample plus field definitions."
        },
        {
          "no": "14.7",
          "question": "Historical operational reports and delay logs.",
          "expected": "Excel/CSV preferred; PDF acceptable if no structured data exists.",
          "type": "PARAGRAPH",
          "help": "Excel/CSV preferred; PDF acceptable if no structured data exists. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "14.8",
          "question": "Survey and statement-of-facts sample documents.",
          "expected": "PDF/Excel sample with sensitive fields redacted if required.",
          "type": "PARAGRAPH",
          "help": "PDF/Excel sample with sensitive fields redacted if required."
        },
        {
          "no": "14.9",
          "question": "Current reason codes, status codes and event definitions.",
          "expected": "Code list or screenshot.",
          "type": "PARAGRAPH",
          "help": "Code list or screenshot. Paste a table or provide a link to the source file if easier."
        },
        {
          "no": "14.10",
          "question": "Integration/security constraints for sharing operational data.",
          "expected": "IT/security note or vendor documentation.",
          "type": "PARAGRAPH",
          "help": "IT/security note or vendor documentation."
        }
      ]
    }
  ]
};

function createABLProposalFactVerificationForm() {
  const form = FormApp.create(FORM_DEF.title);
  form.setDescription(FORM_DEF.description);
  form.setCollectEmail(false);
  form.setProgressBar(true);
  form.setConfirmationMessage('Thank you. Your response has been recorded.');
  form.setAllowResponseEdits(true);

  FORM_DEF.sections.forEach(function(section, sectionIndex) {
    if (sectionIndex === 0) {
      form.addSectionHeaderItem().setTitle(section.title);
    } else {
      form.addPageBreakItem().setTitle(section.title);
    }
    section.questions.forEach(function(q) {
      addQuestion(form, q);
    });
  });

  Logger.log('Edit URL: ' + form.getEditUrl());
  Logger.log('Responder URL: ' + form.getPublishedUrl());
  return { editUrl: form.getEditUrl(), responderUrl: form.getPublishedUrl() };
}

function addQuestion(form, q) {
  let item;
  switch (q.type) {
    case 'MULTIPLE_CHOICE':
      item = form.addMultipleChoiceItem();
      item.setChoiceValues(q.choices || []);
      if ((q.choices || []).indexOf('Other / not listed') === -1) item.showOtherOption(true);
      break;
    case 'CHECKBOX':
      item = form.addCheckboxItem();
      item.setChoiceValues(q.choices || []);
      item.showOtherOption(true);
      break;
    case 'GRID':
      item = form.addGridItem();
      item.setRows(q.rows || []);
      item.setColumns(q.columns || []);
      break;
    case 'CHECKBOX_GRID':
      item = form.addCheckboxGridItem();
      item.setRows(q.rows || []);
      item.setColumns(q.columns || []);
      break;
    case 'SHORT_TEXT':
      item = form.addTextItem();
      break;
    case 'PARAGRAPH':
    default:
      item = form.addParagraphTextItem();
      break;
  }
  item.setTitle(q.no + ' ' + q.question);
  if (q.help) item.setHelpText(q.help);
  item.setRequired(false);
}

function myFunction() {
  return createABLProposalFactVerificationForm();
}
