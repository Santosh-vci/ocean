import { useMemo } from "react";

import { Abbr } from "../components/Abbreviation";
import { GridDate } from "../components/GridDate";
import { SvgIcon } from "../components/SvgIcon";
import {
  RecommendationCard,
  type AssistantRecommendationSurfaceProps,
} from "../components/assistant";
import {
  BRIDGE_EVENT_KINDS,
  latestCandidate,
  latestConfirmedEvent,
  operationalVarianceLabel,
  operationalVarianceMinutes,
  shortOperationalLabel,
  TIDE_EVENT_KINDS,
} from "../lib/operations";
import type {
  BridgeWindowRecord,
  ConfirmedOperationalEventRecord,
  DeviceEndpointRecord,
  NavigationConstraintCheckRecord,
  OperationalEventCandidateRecord,
  PlanningOverview,
  TideWindowRecord,
} from "../types";

type TideBridgePageProps = AssistantRecommendationSurfaceProps & {
  overview: PlanningOverview | null;
  canEdit: boolean;
  isActionRunning: boolean;
  onEnterOperatingWindows: () => void;
  operationCandidates?: OperationalEventCandidateRecord[];
  confirmedOperationalEvents?: ConfirmedOperationalEventRecord[];
  operationDevices?: DeviceEndpointRecord[];
};

const EMPTY_CHECKS: NavigationConstraintCheckRecord[] = [];
const EMPTY_TIDE_WINDOWS: TideWindowRecord[] = [];
const EMPTY_BRIDGE_WINDOWS: BridgeWindowRecord[] = [];
const EMPTY_CANDIDATES: OperationalEventCandidateRecord[] = [];
const EMPTY_CONFIRMED_EVENTS: ConfirmedOperationalEventRecord[] = [];
const EMPTY_DEVICES: DeviceEndpointRecord[] = [];

type WindowRecord = TideWindowRecord | BridgeWindowRecord;

function dt(value: string) {
  return <GridDate value={value} />;
}

function dayLabel(value: string) {
  return new Date(value).toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function timeLabel(value: string) {
  return new Date(value).toLocaleTimeString(undefined, {
    hour: "2-digit",
    hour12: false,
    minute: "2-digit",
  });
}

function durationLabel(window: WindowRecord) {
  const start = new Date(window.window_start).getTime();
  const end = new Date(window.window_end).getTime();
  const minutes = Math.max(0, Math.round((end - start) / 60000));
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  if (hours && remainder) return `${hours}h ${remainder}m`;
  if (hours) return `${hours}h`;
  return `${minutes}m`;
}

function statusTone(status: string) {
  if (status === "missed" || status === "closed") return "critical";
  if (status === "marginal" || status === "waiting" || status === "restricted" || status === "tight") {
    return "pending";
  }
  return "ok";
}

function windowLabel(window: TideWindowRecord | BridgeWindowRecord) {
  if ("risk_level" in window) return `${window.code} - ${window.risk_level.toUpperCase()}`;
  return `${window.code} - ${window.status.toUpperCase()}`;
}

function windowTimeLabel(window: WindowRecord) {
  const startDay = dayLabel(window.window_start);
  const endDay = dayLabel(window.window_end);
  const date = startDay === endDay ? startDay : `${startDay} to ${endDay}`;
  return `${date}, ${timeLabel(window.window_start)}-${timeLabel(window.window_end)}`;
}

function shortWindowTimeLabel(window: WindowRecord) {
  return `${timeLabel(window.window_start)}-${timeLabel(window.window_end)} ${durationLabel(window)}`;
}

function operationalDaySummary(windows: WindowRecord[]) {
  const days = Array.from(new Set(windows.map((window) => dayLabel(window.window_start))));
  if (!days.length) return "No active operating slots";
  if (days.length === 1) return `Operational day ${days[0]}`;
  return `Operational days ${days.join(", ")}`;
}

function isOperatorBridgeWindow(window: BridgeWindowRecord) {
  return window.code.startsWith("BRDG-UI-OPERATING-")
    || window.notes === "Entered from operator UI planning run.";
}

function isOperatorCheck(check: NavigationConstraintCheckRecord) {
  return check.recovery_hint === "Open operator-entered tide window."
    || check.recovery_hint === "Open operator-entered bridge window.";
}

function timelineRange(windows: WindowRecord[]) {
  const starts = windows.map((window) => new Date(window.window_start).getTime());
  const ends = windows.map((window) => new Date(window.window_end).getTime());
  const start = Math.min(...starts);
  const end = Math.max(...ends);
  const span = Math.max(end - start, 60 * 60 * 1000);
  const padding = span * 0.08;
  return { start: start - padding, end: end + padding };
}

function timelineStyle(window: WindowRecord, range: { start: number; end: number }) {
  const start = new Date(window.window_start).getTime();
  const end = new Date(window.window_end).getTime();
  const span = Math.max(range.end - range.start, 60 * 60 * 1000);
  const rawLeft = Math.max(0, Math.min(100, ((start - range.start) / span) * 100));
  const rawRight = Math.max(rawLeft, Math.min(100, ((end - range.start) / span) * 100));
  const width = Math.min(100, Math.max(16, rawRight - rawLeft));
  const left = Math.max(0, Math.min(100 - width, rawLeft));
  return { left: `${left}%`, width: `${width}%` };
}

function timelineAxisTicks(range: { start: number; end: number }) {
  const tickCount = 5;
  const span = Math.max(range.end - range.start, 60 * 60 * 1000);
  const halfHour = 30 * 60 * 1000;
  const ticks = Array.from({ length: tickCount }, (_, index) => {
    const rawValue = range.start + (span * index) / (tickCount - 1);
    const value = Math.max(
      range.start,
      Math.min(range.end, Math.round(rawValue / halfHour) * halfHour),
    );
    return {
      label: timeLabel(new Date(value).toISOString()),
      position: `${((value - range.start) / span) * 100}%`,
    };
  });
  return Array.from(new Map(ticks.map((tick) => [tick.position, tick])).values());
}

function bestRecovery(checks: NavigationConstraintCheckRecord[]) {
  return checks.find((check) => check.status === "missed") ?? checks.find((check) => check.status === "marginal");
}

function deviceFor(devices: DeviceEndpointRecord[], assetType: string) {
  return devices.find((device) => device.asset_type === assetType) ?? null;
}

function deviceHealth(device: DeviceEndpointRecord | null) {
  return shortOperationalLabel(device?.latest_health?.healthStatus ?? device?.status);
}

function operationalTone(status: string | null | undefined) {
  if (status === "confirmed" || status === "auto_confirmed" || status === "healthy" || status === "active") return "ok";
  if (status === "rejected" || status === "offline" || status === "critical") return "critical";
  return "pending";
}

function observedStateLabel(
  candidate: OperationalEventCandidateRecord | null,
  event: ConfirmedOperationalEventRecord | null,
) {
  if (candidate) return shortOperationalLabel(candidate.status);
  if (event) return "CONFIRMED";
  return "NO SIGNAL";
}

export function TideBridgePage({
  assistantBlockedActions,
  assistantChecklist,
  assistantPageActions,
  assistantRowActions,
  overview,
  canEdit,
  isActionRunning,
  onAssistantNavigate,
  onEnterOperatingWindows,
  operationCandidates = EMPTY_CANDIDATES,
  confirmedOperationalEvents = EMPTY_CONFIRMED_EVENTS,
  operationDevices = EMPTY_DEVICES,
}: TideBridgePageProps) {
  const tideWindows = overview?.tideWindows ?? EMPTY_TIDE_WINDOWS;
  const bridgeWindows = overview?.bridgeWindows ?? EMPTY_BRIDGE_WINDOWS;
  const checks = overview?.constraintChecks ?? EMPTY_CHECKS;
  const operatorTideWindows = useMemo(
    () => tideWindows.filter((window) => window.source === "operator-ui"),
    [tideWindows],
  );
  const operatorBridgeWindows = useMemo(
    () => bridgeWindows.filter(isOperatorBridgeWindow),
    [bridgeWindows],
  );
  const operatorChecks = useMemo(() => checks.filter(isOperatorCheck), [checks]);
  const timelineTideWindows = operatorTideWindows.length ? operatorTideWindows : tideWindows;
  const timelineBridgeWindows = operatorBridgeWindows.length ? operatorBridgeWindows : bridgeWindows;
  const visibleChecks = operatorChecks.length ? operatorChecks : checks;
  const timelineScope = operatorTideWindows.length || operatorBridgeWindows.length
    ? "Operator-entered windows"
    : "All active windows";
  const recovery = useMemo(() => bestRecovery(visibleChecks), [visibleChecks]);
  const windows = useMemo(
    () => [...timelineTideWindows, ...timelineBridgeWindows],
    [timelineBridgeWindows, timelineTideWindows],
  );
  const range = useMemo(() => windows.length ? timelineRange(windows) : null, [windows]);
  const axisTicks = useMemo(() => range ? timelineAxisTicks(range) : [], [range]);
  const daySummary = useMemo(() => operationalDaySummary(windows), [windows]);
  const openCount = timelineTideWindows.filter((item) => item.risk_level !== "closed").length
    + timelineBridgeWindows.filter((item) => item.status === "open").length;
  const missedCount = visibleChecks.filter((check) => check.status === "missed").length;
  const latestBridgeCandidate = latestCandidate(operationCandidates, (candidate) => (
    BRIDGE_EVENT_KINDS.includes(candidate.event_kind as (typeof BRIDGE_EVENT_KINDS)[number])
    && candidate.status === "pending"
  ));
  const latestTideCandidate = latestCandidate(operationCandidates, (candidate) => (
    TIDE_EVENT_KINDS.includes(candidate.event_kind as (typeof TIDE_EVENT_KINDS)[number])
    && candidate.status === "pending"
  ));
  const latestBridgeConfirmed = latestConfirmedEvent(confirmedOperationalEvents, (event) => (
    BRIDGE_EVENT_KINDS.includes(event.event_kind as (typeof BRIDGE_EVENT_KINDS)[number])
  ));
  const latestTideConfirmed = latestConfirmedEvent(confirmedOperationalEvents, (event) => (
    TIDE_EVENT_KINDS.includes(event.event_kind as (typeof TIDE_EVENT_KINDS)[number])
  ));
  const bridgeDevice = deviceFor(operationDevices, "bridge");
  const tideDevice = deviceFor(operationDevices, "tide_gate");

  return (
    <section className="workspace-page planning-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Constraints / Tide & Bridge Window Board</p>
          <h1>Tide & Bridge Window</h1>
        </div>
        <div className="planning-actions">
          <div className="window-legend">
            <span><i className="legend-dot ok" />Can cross</span>
            <span><i className="legend-dot critical" />Missed</span>
            <span><i className="legend-dot pending" />Marginal</span>
            <span><i className="legend-dot waiting" />Waiting</span>
          </div>
          <button
            disabled={!canEdit || isActionRunning}
            onClick={onEnterOperatingWindows}
            type="button"
          >
            Enter operating windows
          </button>
        </div>
      </header>
      <RecommendationCard
        assistantBlockedActions={assistantBlockedActions}
        assistantChecklist={assistantChecklist}
        assistantPageActions={assistantPageActions}
        assistantRowActions={assistantRowActions}
        onAssistantNavigate={onAssistantNavigate}
      />

      <div className="metric-strip four-up planning-kpis">
        <div>
          <span>Open windows</span>
          <strong className="success-text">{openCount}</strong>
        </div>
        <div>
          <span>Tide slots</span>
          <strong>{timelineTideWindows.length}</strong>
        </div>
        <div>
          <span>Bridge slots</span>
          <strong>{timelineBridgeWindows.length}</strong>
        </div>
        <div>
          <span>Missed gates</span>
          <strong className={missedCount ? "critical-text" : ""}>{missedCount}</strong>
        </div>
      </div>

      <div className="tide-bridge-layout">
        <section className="board-surface timeline-panel">
          <div className="grid-header">
            <div>
              <SvgIcon name="rule" />
              <strong>Window timeline</strong>
            </div>
            <span>{timelineScope} scaled by local gate time - {daySummary}</span>
          </div>
          <div className="timeline-board">
            {range ? (
              <div className="timeline-axis" aria-label="Window timeline time axis">
                <span>Time axis</span>
                <div>
                  {axisTicks.map((tick) => (
                    <i key={`${tick.label}-${tick.position}`} style={{ left: tick.position }}>
                      {tick.label}
                    </i>
                  ))}
                </div>
              </div>
            ) : null}
            {timelineTideWindows.map((window, index) => {
              const slot = `Tide slot ${index + 1}`;
              const label = `${slot}: ${windowTimeLabel(window)} (${durationLabel(window)})`;
              const shortLabel = shortWindowTimeLabel(window);
              return (
                <div className="window-timeline-row" key={window.id}>
                  <div>
                    <strong>{slot}</strong>
                    <span>{window.code} - {window.location.name}</span>
                  </div>
                  <div className="timeline-track">
                    <span
                      aria-label={label}
                      className={`timeline-bar ${statusTone(window.risk_level)}`}
                      style={range ? timelineStyle(window, range) : undefined}
                      title={label}
                    >
                      {shortLabel}
                    </span>
                  </div>
                </div>
              );
            })}
            {timelineBridgeWindows.map((window, index) => {
              const slot = `Bridge slot ${index + 1}`;
              const label = `${slot}: ${windowTimeLabel(window)} (${durationLabel(window)})`;
              const shortLabel = shortWindowTimeLabel(window);
              return (
                <div className="window-timeline-row" key={window.id}>
                  <div>
                    <strong>{slot}</strong>
                    <span>{window.code} - {window.location.name}</span>
                  </div>
                  <div className="timeline-track">
                    <span
                      aria-label={label}
                      className={`timeline-bar ${statusTone(window.status)}`}
                      style={range ? timelineStyle(window, range) : undefined}
                      title={label}
                    >
                      {shortLabel}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <aside className="board-surface recovery-panel">
          <div className="grid-header">
            <div>
              <SvgIcon name="sync" />
              <strong>Recovery panel</strong>
            </div>
            <span>Highest-impact missed or marginal gate</span>
          </div>
          {recovery ? (
            <div className="recovery-body">
              <span className={`status-chip ${statusTone(recovery.status)}`}>{recovery.status}</span>
              <h2>{recovery.vessel_name} - {recovery.asset_code}</h2>
              <p>{recovery.recovery_hint}</p>
              <dl>
                <div>
                  <dt>Segment</dt>
                  <dd>{recovery.route_segment?.from_location} to {recovery.route_segment?.to_location}</dd>
                </div>
                <div>
                  <dt><Abbr term="ETA">ETA</Abbr> gate</dt>
                  <dd>{dt(recovery.eta_gate)}</dd>
                </div>
                <div>
                  <dt>Window</dt>
                  <dd>{dt(recovery.window_start)} to {dt(recovery.window_end)}</dd>
                </div>
                <div>
                  <dt>Margin</dt>
                  <dd>{recovery.margin_minutes} min</dd>
                </div>
              </dl>
            </div>
          ) : null}
        </aside>
      </div>

      <section className="board-surface observed-gate-panel">
        <div className="grid-header">
          <div>
            <SvgIcon name="operations" />
            <strong>Observed gate state</strong>
          </div>
          <span>Live operational evidence shown beside planned windows</span>
        </div>
        <div className="observed-gate-grid">
          <article>
            <span className={`status-chip ${operationalTone(latestBridgeCandidate?.status ?? latestBridgeConfirmed?.confirmation_mode)}`}>
              {observedStateLabel(latestBridgeCandidate, latestBridgeConfirmed)}
            </span>
            <h2>Bridge gate</h2>
            <dl>
              <div><dt>Latest signal</dt><dd>{shortOperationalLabel(latestBridgeCandidate?.event_kind ?? latestBridgeConfirmed?.event_kind)}</dd></div>
              <div><dt>Actual at</dt><dd>{dt(latestBridgeCandidate?.event_at ?? latestBridgeConfirmed?.actual_at ?? "")}</dd></div>
              <div><dt>Variance</dt><dd>{operationalVarianceLabel(operationalVarianceMinutes(
                latestBridgeCandidate?.schedule_event_planned_at ?? latestBridgeConfirmed?.schedule_event_planned_at,
                latestBridgeCandidate?.event_at ?? latestBridgeConfirmed?.actual_at,
              ))}</dd></div>
              <div><dt>Feed health</dt><dd>{deviceHealth(bridgeDevice)}</dd></div>
            </dl>
          </article>
          <article>
            <span className={`status-chip ${operationalTone(latestTideCandidate?.status ?? latestTideConfirmed?.confirmation_mode)}`}>
              {observedStateLabel(latestTideCandidate, latestTideConfirmed)}
            </span>
            <h2>Tide gate</h2>
            <dl>
              <div><dt>Latest signal</dt><dd>{shortOperationalLabel(latestTideCandidate?.event_kind ?? latestTideConfirmed?.event_kind)}</dd></div>
              <div><dt>Actual at</dt><dd>{dt(latestTideCandidate?.event_at ?? latestTideConfirmed?.actual_at ?? "")}</dd></div>
              <div><dt>Variance</dt><dd>{operationalVarianceLabel(operationalVarianceMinutes(
                latestTideCandidate?.schedule_event_planned_at ?? latestTideConfirmed?.schedule_event_planned_at,
                latestTideCandidate?.event_at ?? latestTideConfirmed?.actual_at,
              ))}</dd></div>
              <div><dt>Feed health</dt><dd>{deviceHealth(tideDevice)}</dd></div>
            </dl>
          </article>
        </div>
      </section>

      <section className="board-surface planning-grid-panel affected-trips-panel">
        <div className="grid-header">
          <div>
            <SvgIcon name="fleet" />
            <strong>Affected trips matrix</strong>
          </div>
          <span>{windows.map(windowLabel).join("  |  ")}</span>
        </div>
        <div className="grid-scroll">
          <table className="planning-table affected-table">
            <thead>
              <tr>
                <th>Asset</th>
                <th><Abbr term="OGV">OGV</Abbr></th>
                <th>Segment</th>
                <th>Draft</th>
                <th><Abbr term="ETA">ETA</Abbr> Gate</th>
                <th>Type</th>
                <th>Window Start</th>
                <th>Window End</th>
                <th>Margin</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {visibleChecks.map((check) => (
                <tr key={check.id}>
                  <td><strong>{check.asset_code}</strong></td>
                  <td>{check.vessel_name}</td>
                  <td>{check.route_segment?.from_location} to {check.route_segment?.to_location}</td>
                  <td>{check.draft_m ?? "-"}m</td>
                  <td>{dt(check.eta_gate)}</td>
                  <td>{check.constraint_type.toUpperCase()}</td>
                  <td>{dt(check.window_start)}</td>
                  <td>{dt(check.window_end)}</td>
                  <td>{check.margin_minutes}m</td>
                  <td><span className={`status-chip ${statusTone(check.status)}`}>{check.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}
