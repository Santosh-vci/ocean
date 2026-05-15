# Frontend UI/UX Visual Thesis Addendum

**Document:** 05 Frontend UI/UX Visual Thesis Addendum  
**Project:** Berau Coal × ABL Scheduling Simulation and Live Planning Platform  
**Audience:** Frontend build team, product owner, UX designer, backend/API team  
**Generated:** 2026-05-15  
**Status:** Handoff draft for implementation alignment

---

## 1. Purpose of this document

This addendum defines the visual thesis, user experience principles, interface density rules, navigation model, screen composition, component behavior, and implementation expectations for the frontend of the Berau Coal × ABL scheduling simulation and live planning platform.

The frontend must not look like a marketing portal, a generic logistics dashboard, or a vessel-tracking map alone. It must feel like an **industrial operations control tower** used by dispatchers, planners, jetty coordinators, CTS operators, commercial viewers, maintenance teams, and customer-facing users who need fast operational clarity.

The product is a **dense, dark, decision-support workspace** for planning, simulation, live monitoring, exception handling, approvals, and operational coordination.

---

## 2. Core visual thesis

The frontend should express the following design thesis:

> A compact, dark, operational cockpit that combines scheduling boards, live fleet state, exception pressure, simulation comparison, and role-specific work queues into one disciplined planning interface.

The product must prioritize:

- speed of scanning
- high information density
- low visual noise
- operational seriousness
- minimal padding
- compact grids
- clear hierarchy
- collapsible navigation
- color used for status and risk, not decoration
- planner actionability over presentation beauty

The interface should feel closer to:

- marine operations control room
- dispatch command center
- rail/port/terminal planning system
- industrial SCADA-adjacent dashboard
- trading-desk-style information workspace

It should not feel like:

- SaaS marketing landing page
- consumer app
- large hero-card dashboard
- decorative analytics showcase
- PowerPoint-style BI portal

---

## 3. User experience principles

### 3.1 Dense first, not spacious first

This product will be used by operational users managing many simultaneous objects: OGVs, barges, tugs, CTS assets, jetties, tide windows, bridge windows, coal grades, loading tasks, delays, and exceptions.

The UI must therefore be compact by default.

Rules:

- Avoid large empty header areas.
- Avoid oversized page titles.
- Avoid hero panels.
- Avoid card-only layouts when a grid/table would be clearer.
- Use compact row heights in all grids.
- Keep vertical padding minimal.
- Show more decision data above the fold.
- Make filters compact and horizontally aligned where possible.

Recommended density:

| UI element | Preferred behavior |
|---|---|
| Grid rows | Compact, approximately 28–36 px height |
| KPI cards | Small, functional, no oversized numbers unless critical |
| Page header | Thin, utility-focused, not decorative |
| Tabs | Compact, inline, low-height |
| Filters | Collapsible or single-line filter bar |
| Action buttons | Small/medium, icon + short text |
| Side navigation | Collapsible, hierarchical |
| Details panels | Slide-over or right drawer, not full page unless needed |

### 3.2 Dark theme as default operating mode

The primary theme should be a rich dark theme. This supports control-room use, continuous monitoring, and better status-color contrast.

Preferred visual direction:

- dark graphite / charcoal background
- slightly elevated dark panels
- subtle borders
- muted text hierarchy
- reserved use of accent colors
- status colors only for operational meaning
- avoid neon-heavy styling
- avoid bright gradients except for tiny state indicators

Suggested color intent:

| Purpose | Visual treatment |
|---|---|
| Base background | Dark charcoal / graphite |
| Surface panels | Slightly lighter dark grey |
| Borders | Low-contrast grey line |
| Primary text | Soft white / light grey |
| Secondary text | Muted grey |
| Critical risk | Red / crimson |
| Warning | Amber |
| Healthy/on-time | Green |
| Information | Blue/cyan |
| Disabled | Low-contrast grey |

Important rule: **color must mean something operational.** Do not use decorative color blocks without meaning.

### 3.3 Planning board before dashboard decoration

The primary UI should be centered around planning and execution boards, not generic charts.

Charts are useful, but they are secondary to:

- schedule grid
- assignment board
- exception queue
- asset state board
- simulation comparison
- plan version history
- live position variance
- approval state

The home/control page should answer:

1. Which OGVs are at risk?
2. Which tug/barge/CTS assets are occupied, delayed, or available?
3. Which loading, sailing, bridge, tide, and discharge events are next?
4. Which exceptions require action?
5. Which plan version is currently approved/live?
6. What changed since the last published plan?

---

## 4. Navigation thesis

### 4.1 Collapsible hierarchical sidebar

The application should use a left-side collapsible sidebar with module/submodule hierarchy.

Requirements:

- Sidebar supports expanded and collapsed states.
- Expanded state shows module names and nested submodules.
- Collapsed state shows icons only with tooltip on hover.
- Active module and active submodule must be clearly visible.
- User role should determine which modules appear.
- Sidebar must not reload full page when expanding/collapsing groups.
- Submodules should support nested expansion where needed, but avoid excessive depth.

Preferred hierarchy:

```text
Control Tower
  - Network Situation
  - Today’s Execution
  - Exception Center
  - Live Map

Planning
  - OGV Demand Plan
  - Schedule Board
  - Tug/Barge Assignment
  - CTS Assignment
  - Jetty Loading Plan
  - Tide & Bridge Windows

Simulation
  - Scenario Builder
  - Plan Comparison
  - Impact Analysis
  - Recovery Recommendations

Fleet
  - Tug Fleet
  - Barge Fleet
  - CTS / Floating Cranes
  - Maintenance Status
  - Device Health

Coal & Loading
  - Coal Grades
  - Stockpile Readiness
  - Jetty Capacity
  - Loading Events

Live Tracking
  - GPS/AIS Feed
  - Geofences
  - Route Progress
  - Signal Gaps

Approvals
  - Plan Review
  - Overrides
  - Published Plans
  - Audit Trail

Reports
  - Operational KPIs
  - Delay Analysis
  - Utilization
  - Customer ETA Reports

Admin
  - Users
  - Roles & Permissions
  - Organizations
  - Master Data
  - Integrations
```

### 4.2 Top bar

The top bar should be thin and utility-focused.

It should include:

- current plan version
- environment/date/time indicator
- global search
- alert count
- user role/org switcher, if allowed
- compact action menu
- connectivity/feed health indicator

Avoid large branding areas. Branding should be present but restrained.

### 4.3 Breadcrumbs and context chips

Because users will move between OGV, barge, tug, jetty, CTS, and simulation records, use compact breadcrumbs and context chips.

Example:

```text
Planning / Schedule Board / OGV MV Ocean-12 / Version V14 Live
```

Context chips:

```text
Live Plan | Approved | Tide Risk: Medium | Berau + ABL Shared | Updated 14:32
```

---

## 5. Layout system

### 5.1 Default screen structure

Preferred page layout:

```text
┌─────────────────────────────────────────────────────────────┐
│ Thin Top Bar                                                │
├──────────────┬──────────────────────────────────────────────┤
│ Sidebar      │ Page Header / Filter Strip                   │
│              ├──────────────────────────────────────────────┤
│              │ KPI Strip / Situation Strip                  │
│              ├──────────────────────────────────────────────┤
│              │ Main Board / Grid / Timeline / Map           │
│              ├──────────────────────────────────────────────┤
│              │ Drawer / Bottom Detail Panel / Audit Context │
└──────────────┴──────────────────────────────────────────────┘
```

### 5.2 Page header

The page header should be compact and functional.

It should include:

- page title
- current operational context
- key action buttons
- status chips
- last refresh time

It should not include:

- large hero image
- marketing copy
- oversized title block
- large welcome message

### 5.3 Filter strip

Every operational board should have a compact filter strip.

Common filters:

- date/time window
- OGV
- coal grade
- jetty
- tug
- barge
- CTS
- status
- risk level
- organization
- plan version
- exception type

Rules:

- Filters should fit in one line where possible.
- Secondary filters can collapse into an “Advanced” popover.
- Active filters should be visible as chips.
- Clearing filters should be one click.

---

## 6. Core screen specifications

## 6.1 Control Tower — Network Situation

Purpose: Provide the operational command-center view.

Primary users:

- joint control tower manager
- Berau planner
- ABL dispatcher
- operations manager
- executive viewer

Screen sections:

1. **Situation strip**
   - OGVs active
   - OGVs at risk
   - barges loaded/in transit/waiting
   - tugs available/assigned/breakdown
   - CTS available/busy/down
   - tide/bridge risks in next 12 hours

2. **Exception queue**
   - late departures
   - missed tide window
   - bridge conflict
   - coal grade sequencing risk
   - jetty delay
   - CTS queue overload
   - GPS/AIS signal stale

3. **Live execution board**
   - event timeline for next 24–48 hours
   - loading start/end
   - sailing ETA
   - bridge/tide crossing
   - discharge start/end
   - return availability

4. **Mini map panel**
   - not full-screen by default
   - show active vessels and risk markers
   - click opens live map screen

UX rules:

- Prioritize exceptions over decorative charts.
- Use compact KPI cards.
- Allow quick drilldown into OGV, vessel, jetty, or exception.
- Show plan variance: planned vs actual.

---

## 6.2 Schedule Board

Purpose: Main planning and execution board.

This should be one of the most important screens.

Recommended layout:

- left: OGV demand list
- center: schedule grid/timeline
- right: selected OGV or trip details drawer
- bottom: exception/audit strip if selected

Grid columns:

| Column | Description |
|---|---|
| OGV | Mother vessel / voyage |
| Coal grade | Required grade/product |
| Layer sequence | Loading sequence requirement |
| Required qty | Quantity required |
| Loaded qty | Completed quantity |
| Remaining qty | Balance quantity |
| Jetty | Assigned loading point |
| Barge | Assigned barge |
| Tug | Assigned tug |
| CTS | Assigned CTS/floating crane |
| Load start/end | Planned/actual |
| Depart | Planned/actual |
| Tide window | Relevant window |
| Bridge window | Relevant window |
| ETA CTS/OGV | Planned/actual |
| Discharge | Planned/actual |
| Risk | On-time, warning, critical |
| Actions | Simulate, reassign, approve, override |

Grid behavior:

- compact row height
- sticky header
- frozen key columns: OGV, status, risk
- inline status chips
- right-click/context menu for power users
- row expansion for trip-level details
- keyboard navigation desirable
- bulk actions only for allowed roles

---

## 6.3 Tug/Barge Assignment Board

Purpose: Assign and monitor fleet resources.

Required views:

1. **Resource grid**
   - tug/barge ID
   - current status
   - current location
   - assigned job
   - next available time
   - compatibility
   - maintenance/breakdown state

2. **Assignment timeline**
   - horizontal timeline by tug/barge
   - colored segments: loading, sailing, waiting, discharging, returning, idle
   - conflict markers

3. **Recommendation panel**
   - suggested assignments from simulation
   - reason codes
   - rejected options and why

Important UX pattern:

When the system recommends a tug/barge change, show:

```text
Recommended: Tug T-04 + Barge B-17
Reason: earliest feasible tide crossing and compatible with Jetty 2 draft limit.
Impact: OGV completion improves by 4h 20m.
Risk: CTS queue tight after 18:30.
```

---

## 6.4 Jetty Loading Board

Purpose: Manage source-side loading capacity.

Sections:

- jetty queue
- current loading task
- next planned barges
- coal grade readiness
- loading rate
- stockpile/CPP readiness indicator
- delay reason
- expected release time

Grid columns:

| Column | Description |
|---|---|
| Jetty | Loading point |
| Current barge | Active or waiting barge |
| Coal grade | Grade being loaded |
| Planned start | Scheduled start |
| Actual start | Actual start |
| Planned end | Scheduled completion |
| Actual/proj end | Actual/projected completion |
| Loading rate | Tons/hour or tons/day equivalent |
| Queue | Waiting barges |
| Constraint | Weather, equipment, stock, queue |
| Action | Confirm, pause, resume, delay reason |

---

## 6.5 Tide and Bridge Window Board

Purpose: Convert environmental constraints into visible planning windows.

Required visual style:

- compact timeline strip
- window bands
- current time marker
- planned crossing markers
- missed/at-risk markers

Views:

- next 12 hours
- next 24 hours
- next 72 hours
- by route/segment
- by bridge
- by tide zone

The board should clearly show:

- available movement windows
- vessels planned for each window
- vessels likely to miss a window
- next feasible alternative window
- operational impact if missed

---

## 6.6 Live Map

Purpose: Provide spatial visibility, but not dominate the product.

Map layers:

- tugs
- barges
- CTS/floating cranes
- OGVs
- jetties
- bridge locations
- tide zones
- anchorage/transshipment zones
- routes
- geofences
- stale signal markers

Map behavior:

- clicking an asset opens right drawer
- hover shows compact tooltip
- color indicates operational status
- shape/icon indicates asset type
- allow filter by asset type/status/risk/assignment
- do not overload map with labels by default

Right drawer should show:

- asset ID
- current job
- planned vs actual status
- speed/heading
- last signal time
- assigned OGV
- ETA next milestone
- exceptions
- action buttons if user has permission

---

## 6.7 Simulation Scenario Builder

Purpose: Create what-if scenarios without corrupting the live approved plan.

Scenario inputs:

- OGV delay
- tug breakdown
- barge unavailable
- CTS outage
- jetty outage
- missed tide window
- bridge closure
- coal grade shortage
- weather stoppage
- manual priority change

UX rules:

- User must name or describe the scenario.
- Scenario must create a version separate from live plan.
- Show baseline vs scenario comparison.
- Show changed assignments clearly.
- Allow planner to promote scenario to proposed plan only with permission.

Comparison metrics:

| Metric | Meaning |
|---|---|
| OGV completion shift | Delay or improvement |
| Tug utilization | Resource impact |
| Barge idle time | Waiting impact |
| CTS queue impact | Bottleneck impact |
| Jetty idle/overload | Source-side impact |
| Missed windows | Tide/bridge impact |
| Changed assignments | Schedule stability impact |
| Demurrage risk | Commercial impact |

---

## 6.8 Approval and Override Screen

Purpose: Govern shared decisions between Berau and ABL.

Must support:

- proposed plan review
- schedule version comparison
- approval chain
- override request
- override reason
- audit history
- publish plan
- reject/return for revision

Override UX must require:

- selected object
- current value
- proposed value
- reason code
- free-text note
- impact preview
- approval, if needed

No silent override should be allowed for published operational plans.

---

## 6.9 Admin and RBAC Console

Purpose: Let authorized admins manage users, roles, permissions, organizations, and data scopes.

Views:

- users
- organizations
- roles
- permissions
- role assignment
- data scope assignment
- asset/location scope
- customer access rules
- integration users/API keys

UX rules:

- show effective permissions clearly
- show inherited vs direct permissions
- allow role simulation: “View app as this user” for admins if permitted
- audit every permission change

---

## 7. Component design rules

## 7.1 Tables and grids

Tables are central to this product.

Rules:

- compact row heights
- sticky headers
- sortable columns
- column resizing where practical
- persistent column preferences by user
- frozen important columns
- inline status chips
- row-level actions compactly grouped
- avoid excessive zebra striping
- support horizontal scroll for dense operational views
- preserve readability at 125% browser zoom

Grid density levels:

| Density | Use |
|---|---|
| Compact | Default for operations |
| Comfortable | Optional user preference |
| Expanded | Detail/review mode only |

Default must be compact.

## 7.2 KPI cards

KPI cards should be small and operational.

Good KPI cards:

- OGVs at risk
- delayed barges
- CTS utilization
- missed tide risk
- bridge conflict count
- jetty queue pressure
- GPS/AIS stale signals

Bad KPI cards:

- giant decorative revenue-style number
- oversized marketing metric
- empty chart card with no decision relevance

## 7.3 Status chips

Use chips for compact state visibility.

Examples:

```text
On Time
At Risk
Critical
Waiting Tide
Waiting Bridge
Loading
Sailing Loaded
Discharging
Returning
Signal Stale
Breakdown
Manual Override
Approved
Draft
Live
```

Chips should be visually distinct but not oversized.

## 7.4 Drawers and detail panels

Use right-side drawers for quick inspection.

Drawer content pattern:

1. entity header
2. current status
3. assignment context
4. planned vs actual milestones
5. risks/exceptions
6. actions
7. audit trail

Avoid navigating away from the main board unless the task requires deep editing.

## 7.5 Modals

Use modals sparingly.

Good modal use:

- confirmation of high-impact override
- approval/rejection note
- create scenario
- assign reason code

Avoid modals for:

- routine viewing
- large forms
- complex comparisons

Use side drawers or full pages for complex workflows.

---

## 8. Information hierarchy

Every page should follow this order:

1. What is the operational state?
2. What is at risk?
3. What requires action?
4. What is the recommended action?
5. What changed from the previous plan?
6. What is the audit/approval status?

Do not lead with decorative visuals.

---

## 9. Interaction patterns

### 9.1 Drilldown pattern

Users should be able to drill down from network to object.

Example:

```text
Network Situation
  → OGV at risk
    → assigned trips
      → tug/barge/jetty/CTS details
        → exception history
          → simulation recovery option
```

### 9.2 Exception-to-action pattern

Each exception should provide:

- what happened
- why it matters
- impacted OGV/customer
- impacted resource
- deadline/window at risk
- recommended action
- owner/team
- acknowledge/escalate/replan actions

### 9.3 Simulation-to-approval pattern

```text
Create scenario
  → run simulation
    → compare with live plan
      → review changed assignments
        → submit proposed plan
          → approve/reject
            → publish live version
```

### 9.4 Live tracking-to-schedule pattern

```text
GPS/AIS signal
  → geofence/milestone detection
    → actual event generated
      → ETA recalculated
        → schedule variance detected
          → alert/replan recommendation
```

---

## 10. RBAC-driven UX behavior

The UI must reflect user permissions.

Rules:

- Hide modules the user cannot access.
- Disable actions the user can view but cannot perform.
- Explain disabled actions with tooltip where useful.
- Do not rely only on frontend hiding; backend must enforce all permissions.
- Use role-aware landing pages.

Examples:

| Role | Default landing screen |
|---|---|
| Joint Control Tower Manager | Network Situation |
| Berau Demand Planner | OGV Demand Plan |
| ABL Dispatcher | Tug/Barge Assignment Board |
| Jetty Operator | Jetty Loading Board |
| CTS Coordinator | CTS Assignment / Queue |
| Maintenance User | Fleet Maintenance Status |
| Customer Viewer | Shipment ETA Portal |
| Admin | Admin Console |

---

## 11. Notification and alert design

Alerts should be operational and actionable.

Alert severity:

| Severity | Meaning |
|---|---|
| Critical | Immediate operational risk; OGV/demurrage/window failure likely |
| High | Requires action soon |
| Medium | Monitor; risk building |
| Low | Informational or early warning |

Alert card contents:

- severity
- object impacted
- summary
- cause
- time sensitivity
- recommended action
- owner/team
- acknowledge button
- simulate/replan button

Avoid generic alerts like “Something changed.” Always state the operational consequence.

---

## 12. Typography and spacing rules

Typography should support dense operational reading.

Recommended direction:

- use a clean sans-serif font
- compact font sizes
- clear numeric alignment
- tabular numbers where possible
- avoid oversized headings

Suggested scale:

| Use | Size guidance |
|---|---|
| Page title | 18–22 px |
| Section title | 14–16 px |
| Table text | 12–14 px |
| Secondary text | 11–12 px |
| KPI number | 20–28 px only where needed |

Spacing:

- use 4 px / 8 px rhythm
- default page padding should be small
- panels should have tight but readable padding
- avoid large 24–48 px gaps except major section separation

---

## 13. Frontend implementation guidance

Preferred stack:

- React or Next.js
- TypeScript
- Tailwind CSS or equivalent utility-based styling
- data grid library suitable for dense enterprise use
- map library suitable for vessel/route/geofence display
- chart/timeline library for operational timelines
- WebSocket/SSE for live updates

Recommended libraries to evaluate:

| Need | Candidate options |
|---|---|
| Data grid | AG Grid, TanStack Table, MUI Data Grid Pro, Handsontable-style grid if licensed |
| Maps | MapLibre GL, Mapbox GL, Leaflet for simpler needs |
| Charts/timeline | Apache ECharts, Recharts, vis-timeline, custom SVG timeline |
| State management | Zustand, Redux Toolkit, TanStack Query |
| Forms | React Hook Form + Zod |
| API fetching | TanStack Query |
| Styling | Tailwind CSS + design tokens |
| Icons | Lucide, Heroicons, custom maritime icons |

Implementation rules:

- Build a reusable layout shell first.
- Build navigation and RBAC visibility early.
- Build compact grid components early.
- Build status chip system early.
- Build right-drawer pattern early.
- Avoid one-off page-specific components unless necessary.
- Maintain design tokens for colors, spacing, density, borders, and status.

---

## 14. Design token direction

Create explicit tokens for:

```text
background.app
background.surface
background.surfaceElevated
border.subtle
border.strong
text.primary
text.secondary
text.muted
status.critical
status.warning
status.ok
status.info
status.disabled
spacing.xs
spacing.sm
spacing.md
density.rowCompact
density.rowComfortable
sidebar.widthExpanded
sidebar.widthCollapsed
topbar.height
```

Do not scatter hardcoded colors and spacing across components.

---

## 15. Responsive behavior

This product is primarily desktop/control-room oriented, but tablet support is useful for jetty and field users.

Desktop:

- full sidebar
- dense grids
- map + board split views
- multi-panel layout

Tablet:

- collapsible sidebar by default
- larger touch targets for operator screens
- simplified grids
- drawer-based details

Mobile:

- not the primary planning surface
- useful for alerts, approvals, and status confirmation
- avoid trying to compress full scheduling board into mobile

Mobile screens should focus on:

- my tasks
- alerts
- approve/reject
- confirm loading event
- confirm breakdown/status
- view shipment ETA

---

## 16. Accessibility and usability

Even with a dark dense UI, the frontend must remain usable.

Rules:

- sufficient text contrast
- keyboard navigation for grids
- visible focus state
- do not rely on color alone for risk
- use icons/labels with color
- support tooltips for abbreviations
- provide empty states and loading states
- show stale-data warnings clearly

---

## 17. Anti-patterns to avoid

Avoid:

- large hero dashboards
- marketing copy in operations screens
- excessive padding
- oversized cards
- pastel/light SaaS theme as default
- hiding critical data behind too many clicks
- map-only control tower
- decorative charts without action
- table rows taller than needed
- too many modals
- uncontrolled color usage
- UI-only permission enforcement
- no audit visibility after override
- replacing planning boards with generic BI pages

---

## 18. First build sequence for frontend team

Recommended frontend build order:

### Phase 1: App shell and design system

- dark theme tokens
- collapsed/expanded sidebar
- top bar
- route layout
- status chips
- compact buttons
- compact cards
- drawer component
- modal component
- table/grid base component

### Phase 2: Core operational boards

- Network Situation
- Schedule Board
- Tug/Barge Assignment Board
- Jetty Loading Board
- Exception Center

### Phase 3: Live tracking UI

- Live Map
- asset drawer
- signal health
- geofence display
- planned vs actual movement

### Phase 4: Simulation and comparison

- Scenario Builder
- Plan Comparison
- Recovery Recommendation view
- Impact Analysis

### Phase 5: Approval, audit, and RBAC console

- approval workflow
- override workflow
- audit trail
- user/role/org admin
- effective permission viewer

### Phase 6: Reports and customer portal

- operational KPIs
- delay/utilization reports
- customer ETA portal
- export controls

---

## 19. Definition of frontend success

The frontend is successful if an operations user can answer the following within seconds:

1. What is the current live plan?
2. Which OGV is most at risk?
3. Which tug/barge/CTS/jetty is causing pressure?
4. Which tide or bridge window is likely to be missed?
5. What is the recommended recovery action?
6. Who needs to approve the change?
7. What changed from the previous approved plan?
8. Which assets have stale GPS/AIS signals?
9. Which customer shipment milestone is impacted?
10. What action do I need to take now?

If the UI cannot answer these questions quickly, it is too decorative or too shallow.

---

## 20. Final frontend mandate

Build the frontend as a **compact industrial planning cockpit**, not a general dashboard.

The product’s value is not in beautiful empty space. Its value is in **showing the right operational pressure, at the right density, with the right next action, under the right permission boundary.**

The default experience should be:

- dark
- dense
- compact
- hierarchical
- role-aware
- schedule-first
- exception-led
- simulation-ready
- audit-safe
- live-data-aware

This visual thesis should be treated as the frontend alignment baseline for the first build.
