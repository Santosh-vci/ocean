import { useCallback, useMemo, useState } from "react";

import { SvgIcon } from "../components/SvgIcon";
import { formatGridDateLabel } from "../lib/gridDate";
import { shortOperationalLabel } from "../lib/operations";
import type {
  ConfirmedOperationalEventRecord,
  DeviceEndpointRecord,
  GeofenceZoneRecord,
  LatestAssetStateRecord,
  LiveEtaProjectionRecord,
  MovementEventRecord,
  OperationalEventCandidateRecord,
  SchedulingOverview,
  TelemetryReplayRunRecord,
  TrackingAlertRecord,
} from "../types";

type LiveResourceMapPageProps = {
  canRunReplay: boolean;
  etaProjections: LiveEtaProjectionRecord[];
  geofenceZones: GeofenceZoneRecord[];
  isActionRunning: boolean;
  latestAssetStates: LatestAssetStateRecord[];
  movementEvents: MovementEventRecord[];
  operationCandidates?: OperationalEventCandidateRecord[];
  confirmedOperationalEvents?: ConfirmedOperationalEventRecord[];
  operationDevices?: DeviceEndpointRecord[];
  overview: SchedulingOverview | null;
  canRunSimulation: boolean;
  onNavigate: (path: string) => void;
  onStartReplay: (replayId: string) => Promise<void>;
  replayRuns: TelemetryReplayRunRecord[];
  trackingAlerts: TrackingAlertRecord[];
};

const EMPTY_ASSIGNMENTS: NonNullable<SchedulingOverview["assignments"]> = [];
const EMPTY_CONFLICTS: NonNullable<SchedulingOverview["conflicts"]> = [];
const EMPTY_CANDIDATES: OperationalEventCandidateRecord[] = [];
const EMPTY_CONFIRMED_EVENTS: ConfirmedOperationalEventRecord[] = [];
const EMPTY_DEVICES: DeviceEndpointRecord[] = [];

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

function alertTone(alert: TrackingAlertRecord | undefined) {
  if (!alert) return "ok";
  if (alert.severity === "critical") return "critical";
  if (alert.severity === "warning") return "pending";
  return "info";
}

function projectionTone(projection: LiveEtaProjectionRecord | undefined) {
  if (!projection) return "info";
  if (projection.status === "delayed") return "critical";
  if (projection.status === "watch" || projection.status === "unknown") return "pending";
  return "ok";
}

function varianceLabel(projection: LiveEtaProjectionRecord | undefined) {
  if (!projection || projection.variance_minutes === null) return "No ETA";
  const sign = projection.variance_minutes > 0 ? "+" : "";
  return `${sign}${projection.variance_minutes}m`;
}

function replayTone(status: string | undefined) {
  if (status === "failed" || status === "canceled") return "critical";
  if (status === "running") return "pending";
  if (status === "completed") return "ok";
  return "info";
}

function coordinateNumber(value: string | null | undefined) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function operationalEventTone(status: string | null | undefined) {
  if (status === "confirmed" || status === "auto_confirmed") return "ok";
  if (status === "rejected" || status === "critical") return "critical";
  return "pending";
}

export function LiveResourceMapPage({
  canRunReplay,
  etaProjections,
  geofenceZones,
  isActionRunning,
  latestAssetStates,
  movementEvents,
  operationCandidates = EMPTY_CANDIDATES,
  confirmedOperationalEvents = EMPTY_CONFIRMED_EVENTS,
  operationDevices = EMPTY_DEVICES,
  overview,
  canRunSimulation,
  onNavigate,
  onStartReplay,
  replayRuns,
  trackingAlerts,
}: LiveResourceMapPageProps) {
  const assignments = overview?.assignments ?? EMPTY_ASSIGNMENTS;
  const conflicts = overview?.conflicts ?? EMPTY_CONFLICTS;
  const statesByAsset = useMemo(
    () => new Map(latestAssetStates.map((state) => [state.asset_code, state])),
    [latestAssetStates],
  );
  const latestProjectionByAsset = useMemo(() => {
    const rows = new Map<string, LiveEtaProjectionRecord>();
    etaProjections.forEach((projection) => {
      const current = rows.get(projection.asset_code);
      if (
        !current
        || new Date(projection.calculated_at).getTime() > new Date(current.calculated_at).getTime()
      ) {
        rows.set(projection.asset_code, projection);
      }
    });
    return rows;
  }, [etaProjections]);
  const openAlerts = trackingAlerts.filter((alert) => alert.status === "open");
  const alertsByAsset = useMemo(() => {
    const rows = new Map<string, TrackingAlertRecord[]>();
    openAlerts.forEach((alert) => {
      rows.set(alert.asset_code, [...(rows.get(alert.asset_code) ?? []), alert]);
    });
    return rows;
  }, [openAlerts]);
  const devicesByAsset = useMemo(
    () => new Map(operationDevices.map((device) => [device.asset_code, device])),
    [operationDevices],
  );
  const latestOperationalCandidateByAsset = useMemo(() => {
    const rows = new Map<string, OperationalEventCandidateRecord>();
    operationCandidates
      .filter((candidate) => candidate.status === "pending")
      .forEach((candidate) => {
        const current = rows.get(candidate.asset_code);
        if (!current || new Date(candidate.event_at).getTime() > new Date(current.event_at).getTime()) {
          rows.set(candidate.asset_code, candidate);
        }
      });
    return rows;
  }, [operationCandidates]);
  const latestOperationalConfirmedByAsset = useMemo(() => {
    const rows = new Map<string, ConfirmedOperationalEventRecord>();
    confirmedOperationalEvents.forEach((event) => {
      if (!event.asset_code) return;
      const current = rows.get(event.asset_code);
      if (!current || new Date(event.actual_at).getTime() > new Date(current.actual_at).getTime()) {
        rows.set(event.asset_code, event);
      }
    });
    return rows;
  }, [confirmedOperationalEvents]);
  const [selectedAssetCode, setSelectedAssetCode] = useState<string | null>(null);
  const [mapMode, setMapMode] = useState<"manual" | "tide" | "exception">("manual");
  const activeReplay = replayRuns.find((run) => run.status === "running")
    ?? replayRuns
      .filter((run) => run.completed_at)
      .sort((left, right) => (
        new Date(right.completed_at ?? 0).getTime() - new Date(left.completed_at ?? 0).getTime()
      ))[0]
    ?? replayRuns[0];
  const [selectedReplayId, setSelectedReplayId] = useState<string | null>(null);
  const selectedReplay = replayRuns.find(
    (run) => run.replay_id === (selectedReplayId ?? activeReplay?.replay_id),
  );
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
  const selectedProjection = selectedCode ? latestProjectionByAsset.get(selectedCode) : undefined;
  const selectedAlerts = selectedCode ? alertsByAsset.get(selectedCode) ?? [] : [];
  const selectedOperationalCandidate = selectedCode
    ? latestOperationalCandidateByAsset.get(selectedCode)
    : undefined;
  const selectedOperationalConfirmed = selectedCode
    ? latestOperationalConfirmedByAsset.get(selectedCode)
    : undefined;
  const freshCount = latestAssetStates.filter((state) => state.freshness_status === "fresh").length;
  const agingCount = latestAssetStates.filter((state) => state.freshness_status === "aging").length;
  const staleCount = latestAssetStates.filter(
    (state) => state.freshness_status === "stale" || state.freshness_status === "missing",
  ).length;
  const activeGeofenceCount = geofenceZones.filter((zone) => zone.status === "active").length;
  const highestVariance = etaProjections
    .filter((projection) => typeof projection.variance_minutes === "number")
    .sort((left, right) => (
      (right.variance_minutes ?? Number.NEGATIVE_INFINITY)
      - (left.variance_minutes ?? Number.NEGATIVE_INFINITY)
    ))[0];
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
          projection: latestProjectionByAsset.get(signal.asset_code),
          alerts: alertsByAsset.get(signal.asset_code) ?? [],
        };
      }),
    [alertsByAsset, assignments, conflicts, latestAssetStates, latestProjectionByAsset, projectPoint],
  );
  const operationalMarkers = useMemo(
    () => [...new Set([
      ...latestOperationalCandidateByAsset.keys(),
      ...latestOperationalConfirmedByAsset.keys(),
    ])]
      .map((assetCode) => {
        const device = devicesByAsset.get(assetCode);
        const zone = geofenceZones.find((item) => item.zone_id === device?.geofence_ref);
        const projected = zone ? projectPoint(zone.latitude, zone.longitude) : null;
        const candidate = latestOperationalCandidateByAsset.get(assetCode);
        const confirmedEvent = latestOperationalConfirmedByAsset.get(assetCode);
        if (!projected || (!candidate && !confirmedEvent)) return null;
        return {
          assetCode,
          left: projected.left,
          top: projected.top,
          candidate,
          confirmedEvent,
        };
      })
      .filter((item): item is {
        assetCode: string;
        left: number;
        top: number;
        candidate: OperationalEventCandidateRecord | undefined;
        confirmedEvent: ConfirmedOperationalEventRecord | undefined;
      } => item !== null),
    [
      devicesByAsset,
      geofenceZones,
      latestOperationalCandidateByAsset,
      latestOperationalConfirmedByAsset,
      projectPoint,
    ],
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
          {selectedReplay ? (
            <span className={`status-chip ${replayTone(selectedReplay.status)}`}>
              {selectedReplay.scenario_code}
            </span>
          ) : null}
          <button onClick={() => onNavigate("/operations/tug-barge-assignment")} type="button">
            Open assignment board
          </button>
          <button onClick={() => onNavigate("/exceptions/center")} type="button">
            Open exceptions
          </button>
        </div>
      </header>

      <div className="metric-strip nine-up map-kpis">
        <div><span>Assets tracked</span><strong>{latestAssetStates.length}</strong></div>
        <div><span>Fresh signals</span><strong className="ok-text">{freshCount}</strong></div>
        <div><span>Aging signals</span><strong className="pending-text">{agingCount}</strong></div>
        <div><span>Stale / missing</span><strong className="critical-text">{staleCount}</strong></div>
        <div><span>Geofences</span><strong>{activeGeofenceCount}</strong></div>
        <div><span>Movement events</span><strong>{movementEvents.length}</strong></div>
        <div><span>Open alerts</span><strong className={openAlerts.length ? "warning-text" : "ok-text"}>{openAlerts.length}</strong></div>
        <div><span>Operational overlays</span><strong className={operationalMarkers.length ? "warning-text" : ""}>{operationalMarkers.length}</strong></div>
        <div><span>Max ETA variance</span><strong className={`${projectionTone(highestVariance)}-text`}>{varianceLabel(highestVariance)}</strong></div>
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
          <section className="map-replay-control">
            <h2>Synthetic replay</h2>
            <select
              onChange={(event) => setSelectedReplayId(event.target.value)}
              value={selectedReplay?.replay_id ?? ""}
            >
              {replayRuns.map((run) => (
                <option key={run.replay_id} value={run.replay_id}>
                  {run.scenario_code}
                </option>
              ))}
            </select>
            <div>
              <span className={`status-chip ${replayTone(selectedReplay?.status)}`}>
                {short(selectedReplay?.status)}
              </span>
              <em>{selectedReplay ? `${selectedReplay.speed_multiplier}x` : "No replay"}</em>
            </div>
            <button
              disabled={!canRunReplay || !selectedReplay || isActionRunning}
              onClick={() => {
                if (selectedReplay) {
                  void onStartReplay(selectedReplay.replay_id);
                }
              }}
              title={!canRunReplay ? "Your role cannot start replay runs." : undefined}
              type="button"
            >
              Start replay
            </button>
            <p>
              {selectedReplay?.completed_at
                ? `Last completed ${formatGridDateLabel(selectedReplay.completed_at)}`
                : "Select a seeded replay family"}
            </p>
          </section>
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
            {markers.map(({ assignment, left, top, conflict, signal, projection, alerts }) => (
              <button
                className={`asset-marker ${
                  alerts[0]
                    ? alertTone(alerts[0])
                    : signal
                      ? toneForFreshness(signal.freshness_status)
                      : toneFor(assignment?.status, conflict?.is_blocking)
                }`}
                key={`${signal.asset_type}-${signal.asset_code}`}
                onClick={() => setSelectedAssetCode(signal.asset_code)}
                style={{ left: `${left}%`, top: `${top}%` }}
                type="button"
              >
                <SvgIcon name="fleet" />
                <span>{signal.asset_code ?? assignment?.trip_ref}</span>
                {projection ? <em>{varianceLabel(projection)}</em> : signal ? <em>{stateAgeLabel(signal)}</em> : null}
                {alerts.length ? <b>{alerts.length}</b> : null}
              </button>
            ))}
            {operationalMarkers.map(({ assetCode, left, top, candidate, confirmedEvent }) => (
              <button
                className={`operational-marker ${operationalEventTone(candidate?.status ?? confirmedEvent?.confirmation_mode)}`}
                key={`operational-${assetCode}`}
                onClick={() => setSelectedAssetCode(assetCode)}
                style={{ left: `${left}%`, top: `${top}%` }}
                type="button"
              >
                <strong>{assetCode}</strong>
                <span>{shortOperationalLabel(candidate?.event_kind ?? confirmedEvent?.event_kind)}</span>
              </button>
            ))}
          </div>
          <div className="map-movement-log">
            <div>
              <strong>Observed ETA & alerts</strong>
              <span>Projection compares live evidence to planned schedule events.</span>
            </div>
            <div className="movement-event-list">
              {openAlerts.slice(0, 2).map((alert) => (
                <button
                  className={alertTone(alert)}
                  key={alert.alert_id}
                  onClick={() => setSelectedAssetCode(alert.asset_code)}
                  type="button"
                >
                  <strong>{alert.asset_code}</strong>
                  <span>{short(alert.alert_type)}</span>
                  <em>{alert.message}</em>
                </button>
              ))}
              {!openAlerts.length ? movementEvents.slice(0, 4).map((event) => (
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
              )) : null}
              {!openAlerts.length && !movementEvents.length ? <span>No movement events</span> : null}
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
                <div><dt>Planned event</dt><dd>{short(selectedProjection?.schedule_event_type)}</dd></div>
                <div><dt>Observed ETA</dt><dd>{selectedProjection?.observed_eta ? formatGridDateLabel(selectedProjection.observed_eta) : "Not calculated"}</dd></div>
                <div><dt>ETA variance</dt><dd className={`${projectionTone(selectedProjection)}-text`}>{varianceLabel(selectedProjection)}</dd></div>
                <div><dt>Open alerts</dt><dd>{selectedAlerts.length ? selectedAlerts.map((alert) => short(alert.alert_type)).join(", ") : "None"}</dd></div>
                <div><dt>Ops event</dt><dd>{shortOperationalLabel(selectedOperationalCandidate?.event_kind ?? selectedOperationalConfirmed?.event_kind)}</dd></div>
                <div><dt>Ops state</dt><dd>{shortOperationalLabel(selectedOperationalCandidate?.status ?? selectedOperationalConfirmed?.confirmation_mode)}</dd></div>
                <div><dt>Ops actual</dt><dd>{selectedOperationalCandidate?.event_at
                  ? formatGridDateLabel(selectedOperationalCandidate.event_at)
                  : selectedOperationalConfirmed?.actual_at
                    ? formatGridDateLabel(selectedOperationalConfirmed.actual_at)
                    : "No event"}</dd></div>
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
              {selectedAlerts.length || selectedOperationalCandidate ? (
                <button onClick={() => onNavigate("/exceptions/center")} type="button">
                  Open exception center
                </button>
              ) : null}
            </div>
          ) : null}
        </aside>
      </div>
    </section>
  );
}
