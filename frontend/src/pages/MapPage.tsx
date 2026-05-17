import { useMemo, useState } from "react";

import { SvgIcon } from "../components/SvgIcon";
import { formatGridDateLabel } from "../lib/gridDate";
import type { LatestAssetStateRecord, SchedulingOverview } from "../types";

type LiveResourceMapPageProps = {
  latestAssetStates: LatestAssetStateRecord[];
  overview: SchedulingOverview | null;
  canRunSimulation: boolean;
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

function toneForFreshness(status: string | undefined) {
  if (status === "fresh") return "ok";
  if (status === "aging") return "pending";
  return "critical";
}

function short(value: string | undefined | null) {
  return value ? value.replaceAll("_", " ").toUpperCase() : "?";
}

function stateAgeLabel(state: LatestAssetStateRecord | undefined) {
  if (!state?.last_seen_at) return "NO PING";
  if (typeof state.age_seconds === "number") {
    if (state.age_seconds < 60) return `${state.age_seconds}s`;
    if (state.age_seconds < 3600) return `${Math.floor(state.age_seconds / 60)}m`;
    return `${Math.floor(state.age_seconds / 3600)}h`;
  }
  return formatGridDateLabel(state.last_seen_at);
}

function coordinateLabel(state: LatestAssetStateRecord | undefined) {
  if (!state?.latitude || !state.longitude) return "Awaiting position";
  return `${Number(state.latitude).toFixed(4)}, ${Number(state.longitude).toFixed(4)}`;
}

export function LiveResourceMapPage({
  latestAssetStates,
  overview,
  canRunSimulation,
  onNavigate,
}: LiveResourceMapPageProps) {
  const assignments = overview?.assignments ?? EMPTY_ASSIGNMENTS;
  const conflicts = overview?.conflicts ?? EMPTY_CONFLICTS;
  const statesByAsset = useMemo(
    () => new Map(latestAssetStates.map((state) => [state.asset_code, state])),
    [latestAssetStates],
  );
  const [selectedId, setSelectedId] = useState<number | null>(assignments[0]?.id ?? null);
  const [mapMode, setMapMode] = useState<"manual" | "tide" | "exception">("manual");
  const selected = assignments.find((assignment) => assignment.id === selectedId) ?? assignments[0];
  const selectedConflict = conflicts.find((conflict) => conflict.trip === selected?.trip);
  const selectedState = selected
    ? statesByAsset.get(selected.tug?.code ?? "") ?? statesByAsset.get(selected.barge?.code ?? "")
    : undefined;
  const freshCount = latestAssetStates.filter((state) => state.freshness_status === "fresh").length;
  const agingCount = latestAssetStates.filter((state) => state.freshness_status === "aging").length;
  const staleCount = latestAssetStates.filter(
    (state) => state.freshness_status === "stale" || state.freshness_status === "missing",
  ).length;
  const syntheticCount = latestAssetStates.filter(
    (state) => state.source_type === "synthetic_gps" || state.source_type === "synthetic_ais",
  ).length;
  const avgConfidence = latestAssetStates.length
    ? Math.round(
      latestAssetStates.reduce(
        (sum, state) => sum + Number(state.confidence_score ?? 0),
        0,
      ) / latestAssetStates.length,
    )
    : null;
  const latestSeen = latestAssetStates
    .filter((state) => state.last_seen_at)
    .sort((left, right) => (
      new Date(right.last_seen_at ?? 0).getTime() - new Date(left.last_seen_at ?? 0).getTime()
    ))[0]?.last_seen_at;
  const stateCounts = latestAssetStates.reduce<Record<string, number>>((acc, state) => {
    acc[state.asset_type] = (acc[state.asset_type] ?? 0) + 1;
    return acc;
  }, {});
  const markers = useMemo(
    () => assignments.slice(0, 8).map((assignment, index) => ({
      assignment,
      left: 22 + ((index * 11) % 58),
      top: 24 + ((index * 17) % 46),
      conflict: conflicts.find((item) => item.trip === assignment.trip),
      signal: statesByAsset.get(assignment.tug?.code ?? "")
        ?? statesByAsset.get(assignment.barge?.code ?? ""),
    })),
    [assignments, conflicts, statesByAsset],
  );

  return (
    <section className="workspace-page live-map-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Map / Live Resource Map</p>
          <h1>Live Resource Map</h1>
        </div>
        <div className="planning-actions">
          <span className="phase-chip secure">
            {mapMode === "manual" ? "Live signal view" : mapMode === "tide" ? "Tide / bridge view" : "Exception view"}
          </span>
          <button onClick={() => onNavigate("/operations/tug-barge-assignment")} type="button">
            Open assignment board
          </button>
          <button onClick={() => onNavigate("/exceptions/center")} type="button">
            Open exceptions
          </button>
        </div>
      </header>

      <div className="metric-strip six-up map-kpis">
        <div><span>Assets tracked</span><strong>{latestAssetStates.length}</strong></div>
        <div><span>Fresh signals</span><strong className="ok-text">{freshCount}</strong></div>
        <div><span>Aging signals</span><strong className="pending-text">{agingCount}</strong></div>
        <div><span>Stale / missing</span><strong className="critical-text">{staleCount}</strong></div>
        <div><span>Synthetic feeds</span><strong>{syntheticCount}</strong></div>
        <div><span>Confidence</span><strong>{avgConfidence === null ? "?" : `${avgConfidence}%`}</strong></div>
      </div>

      <div className="live-map-layout">
        <aside className="board-surface map-filter-rail">
          <div className="grid-header"><div><SvgIcon name="map" /><strong>Map mode</strong></div></div>
          <button
            className={mapMode === "manual" ? "active" : ""}
            onClick={() => setMapMode("manual")}
            type="button"
          >
            Signal health
          </button>
          <button
            className={mapMode === "tide" ? "active" : ""}
            onClick={() => {
              setMapMode("tide");
              onNavigate("/constraints/tide-bridge");
            }}
            type="button"
          >
            Tide / bridge
          </button>
          <button
            className={mapMode === "exception" ? "active" : ""}
            onClick={() => {
              setMapMode("exception");
              onNavigate("/exceptions/center");
            }}
            type="button"
          >
            Exception overlay
          </button>
          <section>
            <h2>Asset layers</h2>
            <span>Tugs <strong>{stateCounts.tug ?? 0}</strong></span>
            <span>Barges <strong>{stateCounts.barge ?? 0}</strong></span>
            <span>CTS <strong>{stateCounts.cts ?? 0}</strong></span>
            <span>OGVs <strong>{stateCounts.ogv ?? 0}</strong></span>
          </section>
          <section className="signal-health-list">
            <h2>Signal health</h2>
            {latestAssetStates.slice(0, 8).map((state) => (
              <button
                className={toneForFreshness(state.freshness_status)}
                key={`${state.asset_type}-${state.asset_code}`}
                onClick={() => {
                  const assignment = assignments.find(
                    (item) => item.tug?.code === state.asset_code || item.barge?.code === state.asset_code,
                  );
                  if (assignment) setSelectedId(assignment.id);
                }}
                type="button"
              >
                <span>{state.asset_code}</span>
                <em>{short(state.freshness_status)}</em>
              </button>
            ))}
            {!latestAssetStates.length ? <span>No telemetry state</span> : null}
          </section>
        </aside>

        <section className="board-surface map-radar-panel">
          <div className="map-radar-surface">
            <div className="river-corridor" />
            <div className="bridge-zone">Bridge</div>
            <div className="cts-zone">CTS</div>
            <div className="anchorage-zone">Anchorage</div>
            {markers.map(({ assignment, left, top, conflict, signal }) => (
              <button
                className={`asset-marker ${
                  signal
                    ? toneForFreshness(signal.freshness_status)
                    : toneFor(assignment.status, conflict?.is_blocking)
                }`}
                key={assignment.id}
                onClick={() => setSelectedId(assignment.id)}
                style={{ left: `${left}%`, top: `${top}%` }}
                type="button"
              >
                <SvgIcon name="fleet" />
                <span>{assignment.tug?.code ?? assignment.barge?.code ?? assignment.trip_ref}</span>
                {signal ? <em>{stateAgeLabel(signal)}</em> : null}
              </button>
            ))}
          </div>
          <div className="map-movement-log">
            <strong>Signal ledger</strong>
            <span>Latest state read model from telemetry ingestion; schedule remains the planning baseline.</span>
            <em>{latestSeen ? formatGridDateLabel(latestSeen) : "No signal received"}</em>
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
                <div><dt>Signal</dt><dd>{short(selectedState?.freshness_status)}</dd></div>
                <div><dt>Source</dt><dd>{selectedState?.source_id ?? "No feed"}</dd></div>
                <div><dt>External ID</dt><dd>{selectedState?.external_id ?? "Unmapped"}</dd></div>
                <div><dt>Last seen</dt><dd>{selectedState ? stateAgeLabel(selectedState) : "No ping"}</dd></div>
                <div><dt>Position</dt><dd>{coordinateLabel(selectedState)}</dd></div>
                <div><dt>Heading</dt><dd>{selectedState?.heading_degrees ? `${selectedState.heading_degrees} deg` : "Unknown"}</dd></div>
                <div><dt>Paired asset</dt><dd>{selected.barge?.code ?? "No barge"}</dd></div>
                <div><dt>Jetty</dt><dd>{selected.jetty?.code ?? "Unassigned"}</dd></div>
                <div><dt>CTS</dt><dd>{selected.cts?.code ?? "Unassigned"}</dd></div>
                <div><dt>Exception</dt><dd>{selectedConflict?.code ?? "None"}</dd></div>
              </dl>
              <button onClick={() => onNavigate("/operations/tug-barge-assignment")} type="button">
                Open assignment board
              </button>
              <button
                disabled={!canRunSimulation}
                onClick={() => onNavigate("/simulation/workspace")}
                title={!canRunSimulation ? "Your role cannot run simulations." : undefined}
                type="button"
              >
                Open simulation workspace
              </button>
            </div>
          ) : null}
        </aside>
      </div>
    </section>
  );
}
