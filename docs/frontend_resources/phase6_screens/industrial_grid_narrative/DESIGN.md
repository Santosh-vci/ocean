---
name: Industrial Grid Narrative
colors:
  surface: '#0b1326'
  surface-dim: '#0b1326'
  surface-bright: '#31394d'
  surface-container-lowest: '#060e20'
  surface-container-low: '#131b2e'
  surface-container: '#171f33'
  surface-container-high: '#222a3d'
  surface-container-highest: '#2d3449'
  on-surface: '#dae2fd'
  on-surface-variant: '#bec8d2'
  inverse-surface: '#dae2fd'
  inverse-on-surface: '#283044'
  outline: '#88929b'
  outline-variant: '#3e4850'
  surface-tint: '#89ceff'
  primary: '#89ceff'
  on-primary: '#00344d'
  primary-container: '#0ea5e9'
  on-primary-container: '#003751'
  inverse-primary: '#006591'
  secondary: '#c0c1ff'
  on-secondary: '#1000a9'
  secondary-container: '#3131c0'
  on-secondary-container: '#b0b2ff'
  tertiary: '#ffb86e'
  on-tertiary: '#492900'
  tertiary-container: '#de8712'
  on-tertiary-container: '#4d2b00'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#c9e6ff'
  primary-fixed-dim: '#89ceff'
  on-primary-fixed: '#001e2f'
  on-primary-fixed-variant: '#004c6e'
  secondary-fixed: '#e1e0ff'
  secondary-fixed-dim: '#c0c1ff'
  on-secondary-fixed: '#07006c'
  on-secondary-fixed-variant: '#2f2ebe'
  tertiary-fixed: '#ffdcbd'
  tertiary-fixed-dim: '#ffb86e'
  on-tertiary-fixed: '#2c1600'
  on-tertiary-fixed-variant: '#693c00'
  background: '#0b1326'
  on-background: '#dae2fd'
  surface-variant: '#2d3449'
  status-success: '#10B981'
  status-warning: '#F59E0B'
  status-critical: '#EF4444'
  status-info: '#0EA5E9'
  surface-graphite: '#1E293B'
  surface-charcoal: '#0F172A'
  border-subtle: '#334155'
  coal-ebony: '#2D2D2D'
  coal-mahoni: '#4B3D33'
  coal-agathis: '#C5A16F'
  planned-stroke: '#94A3B8'
  live-indicator: '#F0F9FF'
typography:
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  data-tabular:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: -0.02em
  label-caps:
    fontFamily: Inter
    fontSize: 10px
    fontWeight: '700'
    lineHeight: 12px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 8px
  margin-page: 16px
  row-height-compact: 28px
  row-height-standard: 36px
  sidebar-width-collapsed: 56px
  sidebar-width-expanded: 240px
---

## Brand & Style

This design system is engineered for the high-stakes, high-density environment of coal transshipment scheduling. It adopts an **Industrial Minimalism** aesthetic—a style that prioritizes extreme data density, visual precision, and "trust through transparency." The brand personality is authoritative, technical, and risk-averse, reflecting the mission-critical nature of maritime and mining logistics.

### Design Principles
- **Density Over Aesthetics:** White space is treated as a premium resource. The layout is compact to minimize eye travel across large-scale monitoring dashboards.
- **Truth via Layering:** The UI distinguishes between three types of reality: *Planned* (Intent), *Live* (Evidence), and *Inferred* (Algorithmic Projection).
- **Status-First Communication:** Color is never decorative. It is used exclusively as a semantic signal for operational health, constraint violations, and logistical risks.
- **Low Visual Noise:** Borders and tonal shifts are used instead of heavy shadows or gradients to maintain a "cockpit" feel that reduces cognitive load during long shifts.

## Colors

The palette is anchored in a **Deep Dark Theme** (Charcoal and Graphite) to reduce eye strain in control room environments. 

### Semantic Logic
- **Primary/Info (#0EA5E9):** Used for system navigation and informational data points.
- **Success (#10B981):** Indicates optimal productivity, on-schedule transshipment, and feasible plans.
- **Warning (#F59E0B):** Signals bridge/tide constraint risks, maintenance alerts, or "Manual Override" states.
- **Critical (#EF4444):** Reserved for OGV demurrage risk, breakdown states, or logic failures (e.g., bridge clashes).
- **Data Reliability:** Use `planned-stroke` for baseline schedules and `live-indicator` (high-contrast white/cyan) for real-time GPS/AIS telemetry.

## Typography

The typographic system is built for scanning. We utilize a dual-font approach: **Hanken Grotesk** for structural headers and **Inter** for standard UI elements.

### Tabular Data
A critical requirement is the use of **JetBrains Mono** for all numeric values, timestamps (ETA/ETB), and coordinates. This ensures that columns of numbers align perfectly in high-density grids, allowing dispatchers to compare values (like MT/day or Vessel LOA) at a glance.

### Hierarchy
- **Labels:** Use `label-caps` for metadata tags (e.g., "MMSI", "TIDE WINDOW").
- **Body:** `body-sm` is the default for table content to maximize information density.
- **Headings:** Kept relatively small (20px max) to prevent them from dominating the workspace.

## Layout & Spacing

This design system uses a **Fixed Grid Strategy** optimized for 1080p and 1440p control room monitors.

### Layout Philosophy
- **Dashboard/Board-Based:** The layout is divided into functional "cockpits" (e.g., OGV Risk Board, Gantt Timeline, Live Map).
- **Collapsible Navigation:** A thin sidebar (`56px` collapsed) maximizes horizontal real estate for the timeline-based planning boards.
- **Rhythm:** A strict **4px baseline** governs all spacing. Vertical margins between table rows are kept to a minimum (`4px` or `8px`) to allow for maximum data visibility without scrolling.

### Breakpoints
- **Desktop (1440px+):** Full multi-pane view with visible right-side Detail Drawers.
- **Tablet/Laptop (1024px):** Drawers become temporary overlays; sidebar auto-collapses.
- **Reflow:** Content does not reflow into card stacks; it maintains a horizontal grid with overflow scrolling to preserve the tabular relationship of data.

## Elevation & Depth

In a high-density industrial UI, traditional shadows cause visual "fuzziness" that hinders readability. Instead, we use **Tonal Layering** and **Low-Contrast Outlines**.

### Elevation Hierarchy
1.  **Base (Level 0):** `surface-charcoal` (#0F172A). The "canvas" of the application.
2.  **Surface (Level 1):** `surface-graphite` (#1E293B). Main panels, boards, and grid containers.
3.  **Elevated (Level 2):** Use a slightly lighter tint with a 1px `border-subtle` for interactive elements like tooltips, dropdown menus, and detail drawers.
4.  **Overlay:** Modal dialogs for "Scenario Approvals" use a 20% black backdrop tint and a crisp 2px border in the `primary` color to denote focus.

Depth is conveyed through **Z-Index Logic**: The Live Map acts as the background anchor, while Planning Boards and Exception Cockpits sit on top as functional layers.

## Shapes

The shape language is **Soft (0.25rem)**, leaning toward a technical, rectangular feel.

- **UI Elements:** Buttons, input fields, and chips use a `4px` radius. This provides just enough definition to distinguish elements without losing the industrial "grid" aesthetic.
- **Timeline Bars:** Gantt-style blocks for "Trip Timelines" are strictly rectangular with `0px` radius to allow them to sit flush against one another when representing sequential stages (Loading -> Sailing -> Discharging).
- **Map Assets:** Vessels and Infrastructure icons are contained within hexagonal or circular status containers to differentiate them from the rectangular UI.

## Components

### Buttons & Inputs
- **Primary Action:** Solid `primary` color, `data-tabular` font, compact padding (4px 12px).
- **System Inputs:** Use `surface-charcoal` backgrounds with a `border-subtle` stroke. On focus, the stroke shifts to `primary`.

### Data Grids (The Core Component)
- **Compact Rows:** Fixed height of `28px`. 
- **Cell Alignment:** Numeric data is always right-aligned using tabular fonts. Text labels are left-aligned.
- **State Indicators:** Use small 8px circles (Status-dots) or thin 2px left-border accents to indicate row status (e.g., "Waiting Tide").

### Status Chips
- Small, uppercase, bold capsules used for lifecycle states like `DRAFT`, `SIMULATED`, or `LIVE`. Backgrounds are low-opacity versions of the semantic colors (e.g., 15% Green for `APPROVED`).

### Planning Drawers
- Right-aligned slide-over panels for "Object Details." These contain the "Audit Trail" and "Who/What/When" logs, utilizing a vertical timeline component with monospaced timestamps.

### Map Markers
- **Vessels:** Directional "arrowhead" shapes for live movement; ghosted "outline" shapes for planned positions.
- **Geofences:** Polygonal zones with 10% opacity fills and 1px dashed borders in `status-info` or `status-warning`.