import { useMemo, useState } from "react";

import { SvgIcon } from "../components/SvgIcon";
import type { DashboardReadModel, SchedulingOverview } from "../types";

type LiveResourceMapPageProps = {
  dashboard: DashboardReadModel | null;
  overview: SchedulingOverview | null;
  onNavigate: (path: string) => void;
};

const EMPTY_ASSIGNMENTS: NonNullable<SchedulingOverview["assignments"]> = [];
const EMPTY_CONFLICTS: NonNullable<SchedulingOverview["conflicts"]> = [];

function toneFor(status: string | undefined, blocked = false) {
  if (blocked || status === "blocked" || status === "maintenance") return "critical";
  if (status === "waiting_tide" || status === "waiting_bridge" || status === "delayed") {
    return "pending";
  }
  return "ok";
}

function short(value: string | undefined | null) {
  return value ? value.replaceAll("_", " ").toUpperCase() : "?";
}

export function LiveResourceMapPage({ dashboard, overview, onNavigate }: LiveResourceMapPageProps) {
  const assignments = overview?.assignments ?? EMPTY_ASSIGNMENTS;
  const conflicts = overview?.conflicts ?? EMPTY_CONFLICTS;
  const [selectedId, setSelectedId] = useState<number | null>(assignments[0]?.id ?? null);
  const selected = assignments.find((assignment) => assignment.id === selectedId) ?? assignments[0];
  const selectedConflict = conflicts.find((conflict) => conflict.trip === selected?.trip);
  const totals = dashboard?.queuePressure.fleet;
  const markers = useMemo(
    () => assignments.slice(0, 8).map((assignment, index) => ({
      assignment,
      left: 22 + ((index * 11) % 58),
      top: 24 + ((index * 17) % 46),
      conflict: conflicts.find((item) => item.trip === assignment.trip),
    })),
    [assignments, conflicts],
  );

  return (
    <section className="workspace-page live-map-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Map / Live Resource Map</p>
          <h1>Live Resource Map</h1>
        </div>
        <div className="planning-actions">
          <span className="phase-chip secure">Chunk 6 ? Manual state view</span>
          <button onClick={() => onNavigate("/operations/tug-barge-assignment")} type="button">
            Open assignment board
          </button>
          <button onClick={() => onNavigate("/exceptions/center")} type="button">
            Open exceptions
          </button>
        </div>
      </header>

      <div className="metric-strip six-up map-kpis">
        <div><span>Assets tracked</span><strong>{assignments.length}</strong></div>
        <div><span>Tugs active</span><strong className="ok-text">{totals?.activeTugs ?? 0}</strong></div>
        <div><span>Barges active</span><strong className="ok-text">{totals?.activeBarges ?? 0}</strong></div>
        <div><span>Map exceptions</span><strong className="critical-text">{dashboard?.planRisk.blockingConflicts ?? 0}</strong></div>
        <div><span>Route risk</span><strong className="pending-text">{dashboard?.queuePressure.navigationRisk.label ?? "Low"}</strong></div>
        <div><span>Confidence</span><strong>{dashboard ? "96%" : "?"}</strong></div>
      </div>

      <div className="live-map-layout">
        <aside className="board-surface map-filter-rail">
          <div className="grid-header"><div><SvgIcon name="map" /><strong>Map mode</strong></div></div>
          <button className="active" type="button">Manual live state</button>
          <button onClick={() => onNavigate("/constraints/tide-bridge")} type="button">Tide / bridge</button>
          <button onClick={() => onNavigate("/exceptions/center")} type="button">Exception overlay</button>
          <section>
            <h2>Asset layers</h2>
            <span>? Tugs</span>
            <span>? Barges</span>
            <span>? CTS</span>
            <span>? OGVs</span>
          </section>
        </aside>

        <section className="board-surface map-radar-panel">
          <div className="map-radar-surface">
            <div className="river-corridor" />
            <div className="bridge-zone">Bridge</div>
            <div className="cts-zone">CTS</div>
            <div className="anchorage-zone">Anchorage</div>
            {markers.map(({ assignment, left, top, conflict }) => (
              <button
                className={`asset-marker ${toneFor(assignment.status, conflict?.is_blocking)}`}
                key={assignment.id}
                onClick={() => setSelectedId(assignment.id)}
                style={{ left: `${left}%`, top: `${top}%` }}
                type="button"
              >
                <SvgIcon name="fleet" />
                <span>{assignment.tug?.code ?? assignment.barge?.code ?? assignment.trip_ref}</span>
              </button>
            ))}
          </div>
          <div className="map-movement-log">
            <strong>Movement log</strong>
            <span>Manual state derived from current schedule assignments; no AIS/GPS dependency in Phase 1.</span>
            <em>{dashboard?.generatedAt ? new Date(dashboard.generatedAt).toLocaleString() : "Waiting for read model"}</em>
          </div>
        </section>

        <aside className="board-surface map-detail-rail">
          <div className="grid-header"><div><SvgIcon name="fleet" /><strong>Selected asset</strong></div></div>
          {selected ? (
            <div className="map-selected-asset">
              <span className={`status-chip ${toneFor(selected.status, selectedConflict?.is_blocking)}`}>
                {short(selected.status)}
              </span>
              <h2>{selected.tug?.name ?? selected.barge?.name ?? selected.trip_ref}</h2>
              <p>{selected.vessel_name}</p>
              <dl>
                <div><dt>Paired asset</dt><dd>{selected.barge?.code ?? "No barge"}</dd></div>
                <div><dt>Jetty</dt><dd>{selected.jetty?.code ?? "Unassigned"}</dd></div>
                <div><dt>CTS</dt><dd>{selected.cts?.code ?? "Unassigned"}</dd></div>
                <div><dt>Exception</dt><dd>{selectedConflict?.code ?? "None"}</dd></div>
              </dl>
              <button onClick={() => onNavigate("/operations/tug-barge-assignment")} type="button">
                Open assignment board
              </button>
              <button onClick={() => onNavigate("/simulation/workspace")} type="button">
                Run simulation
              </button>
            </div>
          ) : null}
        </aside>
      </div>
    </section>
  );
}
