import { useCallback, useMemo, useState } from "react";

import { SvgIcon } from "../components/SvgIcon";
import { formatGridDateLabel } from "../lib/gridDate";
import type {
  GeofenceZoneRecord,
  LatestAssetStateRecord,
  MovementEventRecord,
  SchedulingOverview,
} from "../types";

type LiveResourceMapPageProps = {
  geofenceZones: GeofenceZoneRecord[];
  latestAssetStates: LatestAssetStateRecord[];
  movementEvents: MovementEventRecord[];
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

function eventLabel(eventType: string | undefined | null) {
  if (!eventType) return "No movement event";
  return eventType.replaceAll("_", " ").toUpperCase();
}

function zoneTone(zoneType: string | undefined) {
  if (zoneType === "bridge" || zoneType === "tide_gate") return "pending";
  if (zoneType === "maintenance") return "critical";
  if (zoneType === "cts_zone" || zoneType === "transshipment") return "ok";
  return "info";
}

function coordinateNumber(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function LiveResourceMapPage({
  geofenceZones,
  latestAssetStates,
  movementEvents,
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
  const [selectedAssetCode, setSelectedAssetCode] = useState<string | null>(null);
  const [mapMode, setMapMode] = useState<"manual" | "tide" | "exception">("manual");
  const defaultSignalCode = latestAssetStates.find((state) => state.current_geofence_ref)?.asset_code
    ?? latestAssetStates.find((state) => state.freshness_status === "fresh")?.asset_code;
  const selectedCode = selectedAssetCode
    ?? defaultSignalCode
    ?? latestAssetStates[0]?.asset_code
    ?? assignments[0]?.tug?.code
    ?? assignments[0]?.barge?.code
    ?? null;
  const selected = assignments.find(
    (assignment) => assignment.tug?.code === selectedCode || assignment.barge?.code === selectedCode,
  ) ?? assignments[0];
  const selectedConflict = conflicts.find((conflict) => conflict.trip === selected?.trip);
  const selectedState = selectedCode ? statesByAsset.get(selectedCode) : undefined;
  const freshCount = latestAssetStates.filter((state) => state.freshness_status === "fresh").length;
  const agingCount = latestAssetStates.filter((state) => state.freshness_status === "aging").length;
  const staleCount = latestAssetStates.filter(
    (state) => state.freshness_status === "stale" || state.freshness_status === "missing",
  ).length;
  const activeGeofenceCount = geofenceZones.filter((zone) => zone.status === "active").length;
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
  const zoneCounts = geofenceZones.reduce<Record<string, number>>((acc, zone) => {
    acc[zone.zone_type] = (acc[zone.zone_type] ?? 0) + 1;
    return acc;
  }, {});
  const geoBounds = useMemo(() => {
    const points = [
      ...geofenceZones.map((zone) => ({
        lat: coordinateNumber(zone.latitude),
        lon: coordinateNumber(zone.longitude),
      })),
      ...latestAssetStates.map((state) => ({
        lat: coordinateNumber(state.latitude),
        lon: coordinateNumber(state.longitude),
      })),
    ].filter((point): point is { lat: number; lon: number } => (
      point.lat !== null && point.lon !== null
    ));
    if (!points.length) return null;
    const latValues = points.map((point) => point.lat);
    const lonValues = points.map((point) => point.lon);
    const minLat = Math.min(...latValues);
    const maxLat = Math.max(...latValues);
    const minLon = Math.min(...lonValues);
    const maxLon = Math.max(...lonValues);
    return {
      minLat,
      maxLat,
      minLon,
      maxLon,
      latSpan: Math.max(maxLat - minLat, 0.01),
      lonSpan: Math.max(maxLon - minLon, 0.01),
    };
  }, [geofenceZones, latestAssetStates]);
  const projectPoint = useCallback((latitude: string | null | undefined, longitude: string | null | undefined) => {
    const lat = coordinateNumber(latitude);
    const lon = coordinateNumber(longitude);
    if (!geoBounds || lat === null || lon === null) return null;
    return {
      left: 8 + ((lon - geoBounds.minLon) / geoBounds.lonSpan) * 84,
      top: 8 + ((geoBounds.maxLat - lat) / geoBounds.latSpan) * 84,
    };
  }, [geoBounds]);
  const markers = useMemo(
    () => latestAssetStates
      .filter((state) => state.latitude && state.longitude)
      .slice(0, 12)
      .map((signal, index) => {
        const assignment = assignments.find(
          (item) => item.tug?.code === signal.asset_code || item.barge?.code === signal.asset_code,
        );
        const projected = projectPoint(signal.latitude, signal.longitude);
        return {
          assignment,
          left: projected?.left ?? 22 + ((index * 11) % 58),
          top: projected?.top ?? 24 + ((index * 17) % 46),
          conflict: assignment ? conflicts.find((item) => item.trip === assignment.trip) : undefined,
          signal,
        };
      }),
    [assignments, conflicts, latestAssetStates, projectPoint],
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

      <div className="metric-strip seven-up map-kpis">
        <div><span>Assets tracked</span><strong>{latestAssetStates.length}</strong></div>
        <div><span>Fresh signals</span><strong className="ok-text">{freshCount}</strong></div>
        <div><span>Aging signals</span><strong className="pending-text">{agingCount}</strong></div>
        <div><span>Stale / missing</span><strong className="critical-text">{staleCount}</strong></div>
        <div><span>Geofences</span><strong>{activeGeofenceCount}</strong></div>
        <div><span>Movement events</span><strong>{movementEvents.length}</strong></div>
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
          <section>
            <h2>Geofence layers</h2>
            <span>Jetties <strong>{zoneCounts.jetty ?? 0}</strong></span>
            <span>Bridge gates <strong>{zoneCounts.bridge ?? 0}</strong></span>
            <span>Tide gates <strong>{zoneCounts.tide_gate ?? 0}</strong></span>
            <span>CTS zones <strong>{zoneCounts.cts_zone ?? 0}</strong></span>
          </section>
          <section className="signal-health-list">
            <h2>Signal health</h2>
            {latestAssetStates.slice(0, 8).map((state) => (
              <button
                className={toneForFreshness(state.freshness_status)}
                key={`${state.asset_type}-${state.asset_code}`}
                onClick={() => {
                  setSelectedAssetCode(state.asset_code);
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
            {geofenceZones.slice(0, 12).map((zone) => {
              const projected = projectPoint(zone.latitude, zone.longitude);
              const size = Math.max(3.2, Math.min(8.5, zone.radius_m / 260));
              return projected ? (
                <div
                  className={`geofence-zone ${zoneTone(zone.zone_type)}`}
                  key={zone.zone_id}
                  style={{
                    left: `${projected.left}%`,
                    top: `${projected.top}%`,
                    width: `${size}rem`,
                    height: `${size}rem`,
                  }}
                >
                  <strong>{short(zone.zone_type)}</strong>
                  <span>{zone.name}</span>
                </div>
              ) : null;
            })}
            {markers.map(({ assignment, left, top, conflict, signal }) => (
              <button
                className={`asset-marker ${
                  signal ? toneForFreshness(signal.freshness_status) : toneFor(assignment?.status, conflict?.is_blocking)
                }`}
                key={`${signal.asset_type}-${signal.asset_code}`}
                onClick={() => setSelectedAssetCode(signal.asset_code)}
                style={{ left: `${left}%`, top: `${top}%` }}
                type="button"
              >
                <SvgIcon name="fleet" />
                <span>{signal.asset_code ?? assignment?.trip_ref}</span>
                {signal ? <em>{stateAgeLabel(signal)}</em> : null}
              </button>
            ))}
          </div>
          <div className="map-movement-log">
            <div>
              <strong>Movement events</strong>
              <span>Derived from geofence transitions; schedule remains the planning baseline.</span>
            </div>
            <div className="movement-event-list">
              {movementEvents.slice(0, 4).map((event) => (
                <button
                  className={zoneTone(event.geofence_type)}
                  key={event.event_id}
                  onClick={() => setSelectedAssetCode(event.asset_code)}
                  type="button"
                >
                  <strong>{event.asset_code}</strong>
                  <span>{eventLabel(event.event_type)}</span>
                  <em>{event.geofence_name}</em>
                </button>
              ))}
              {!movementEvents.length ? <span>No movement events</span> : null}
            </div>
            <em>{latestSeen ? formatGridDateLabel(latestSeen) : "No signal received"}</em>
          </div>
        </section>

        <aside className="board-surface map-detail-rail">
          <div className="grid-header"><div><SvgIcon name="fleet" /><strong>Selected asset</strong></div></div>
          {selected || selectedState ? (
            <div className="map-selected-asset">
              <span className={`status-chip ${
                selected ? toneFor(selected.status, selectedConflict?.is_blocking) : toneForFreshness(selectedState?.freshness_status)
              }`}
              >
                {selected ? short(selected.status) : short(selectedState?.freshness_status)}
              </span>
              <h2>{selected?.tug?.name ?? selected?.barge?.name ?? selectedState?.asset_code ?? selected?.trip_ref}</h2>
              <p>{selected?.vessel_name ?? short(selectedState?.asset_type)}</p>
              <dl>
                <div><dt>Signal</dt><dd>{short(selectedState?.freshness_status)}</dd></div>
                <div><dt>Source</dt><dd>{selectedState?.source_id ?? "No feed"}</dd></div>
                <div><dt>External ID</dt><dd>{selectedState?.external_id ?? "Unmapped"}</dd></div>
                <div><dt>Last seen</dt><dd>{selectedState ? stateAgeLabel(selectedState) : "No ping"}</dd></div>
                <div><dt>Position</dt><dd>{coordinateLabel(selectedState)}</dd></div>
                <div><dt>Heading</dt><dd>{selectedState?.heading_degrees ? `${selectedState.heading_degrees} deg` : "Unknown"}</dd></div>
                <div><dt>Current zone</dt><dd>{selectedState?.current_geofence_name ?? "Outside geofence"}</dd></div>
                <div><dt>Last movement</dt><dd>{eventLabel(selectedState?.last_movement_event_type)}</dd></div>
                <div><dt>Paired asset</dt><dd>{selected?.barge?.code ?? "No barge"}</dd></div>
                <div><dt>Jetty</dt><dd>{selected?.jetty?.code ?? "Unassigned"}</dd></div>
                <div><dt>CTS</dt><dd>{selected?.cts?.code ?? "Unassigned"}</dd></div>
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
