import { useMemo } from "react";

import { SvgIcon } from "../components/SvgIcon";
import type {
  BridgeWindowRecord,
  NavigationConstraintCheckRecord,
  PlanningOverview,
  TideWindowRecord,
} from "../types";

type TideBridgePageProps = {
  overview: PlanningOverview | null;
};

const EMPTY_CHECKS: NavigationConstraintCheckRecord[] = [];

function dt(value: string) {
  return new Date(value).toLocaleString(undefined, {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
  });
}

function statusTone(status: string) {
  if (status === "missed" || status === "closed") return "critical";
  if (status === "marginal" || status === "waiting" || status === "restricted" || status === "tight") {
    return "pending";
  }
  return "ok";
}

function windowLabel(window: TideWindowRecord | BridgeWindowRecord) {
  if ("risk_level" in window) return `${window.code} · ${window.risk_level.toUpperCase()}`;
  return `${window.code} · ${window.status.toUpperCase()}`;
}

function timelineStyle(index: number, total: number) {
  const width = Math.max(22, Math.floor(72 / Math.max(total, 1)));
  const left = Math.min(72, index * Math.max(8, Math.floor(62 / Math.max(total, 1))));
  return { marginLeft: `${left}%`, width: `${width}%` };
}

function bestRecovery(checks: NavigationConstraintCheckRecord[]) {
  return checks.find((check) => check.status === "missed") ?? checks.find((check) => check.status === "marginal");
}

export function TideBridgePage({ overview }: TideBridgePageProps) {
  const tideWindows = overview?.tideWindows ?? [];
  const bridgeWindows = overview?.bridgeWindows ?? [];
  const checks = overview?.constraintChecks ?? EMPTY_CHECKS;
  const recovery = useMemo(() => bestRecovery(checks), [checks]);
  const openCount = tideWindows.filter((item) => item.risk_level !== "closed").length
    + bridgeWindows.filter((item) => item.status === "open").length;
  const missedCount = overview?.validation.missedWindows ?? 0;

  return (
    <section className="workspace-page planning-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Constraints / Tide & Bridge Window Board</p>
          <h1>Tide & Bridge Window</h1>
        </div>
        <div className="window-legend">
          <span><i className="legend-dot ok" />Can cross</span>
          <span><i className="legend-dot critical" />Missed</span>
          <span><i className="legend-dot pending" />Marginal</span>
          <span><i className="legend-dot waiting" />Waiting</span>
        </div>
      </header>

      <div className="metric-strip four-up planning-kpis">
        <div>
          <span>Open windows</span>
          <strong className="success-text">{openCount}</strong>
        </div>
        <div>
          <span>Tide slots</span>
          <strong>{tideWindows.length}</strong>
        </div>
        <div>
          <span>Bridge slots</span>
          <strong>{bridgeWindows.length}</strong>
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
            <span>Open/closed windows and ETA markers by navigational gate</span>
          </div>
          <div className="timeline-board">
            {tideWindows.map((window, index) => (
              <div className="timeline-row" key={window.id}>
                <div>
                  <strong>{window.code}</strong>
                  <span>{window.location.name}</span>
                </div>
                <div className="timeline-track">
                  <span
                    className={`timeline-bar ${statusTone(window.risk_level)}`}
                    style={timelineStyle(index, tideWindows.length + bridgeWindows.length)}
                  >
                    {dt(window.window_start)} → {dt(window.window_end)}
                  </span>
                </div>
              </div>
            ))}
            {bridgeWindows.map((window, index) => (
              <div className="timeline-row" key={window.id}>
                <div>
                  <strong>{window.code}</strong>
                  <span>{window.location.name}</span>
                </div>
                <div className="timeline-track">
                  <span
                    className={`timeline-bar ${statusTone(window.status)}`}
                    style={timelineStyle(index + tideWindows.length, tideWindows.length + bridgeWindows.length)}
                  >
                    {dt(window.window_start)} → {dt(window.window_end)}
                  </span>
                </div>
              </div>
            ))}
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
              <h2>{recovery.vessel_name} · {recovery.asset_code}</h2>
              <p>{recovery.recovery_hint}</p>
              <dl>
                <div>
                  <dt>Segment</dt>
                  <dd>{recovery.route_segment?.from_location} → {recovery.route_segment?.to_location}</dd>
                </div>
                <div>
                  <dt>ETA gate</dt>
                  <dd>{dt(recovery.eta_gate)}</dd>
                </div>
                <div>
                  <dt>Window</dt>
                  <dd>{dt(recovery.window_start)} → {dt(recovery.window_end)}</dd>
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

      <section className="board-surface planning-grid-panel affected-trips-panel">
        <div className="grid-header">
          <div>
            <SvgIcon name="fleet" />
            <strong>Affected trips matrix</strong>
          </div>
          <span>{[...tideWindows, ...bridgeWindows].map(windowLabel).join("  ·  ")}</span>
        </div>
        <div className="grid-scroll">
          <table className="planning-table affected-table">
            <thead>
              <tr>
                <th>Asset</th>
                <th>OGV</th>
                <th>Segment</th>
                <th>Draft</th>
                <th>ETA Gate</th>
                <th>Type</th>
                <th>Window Start</th>
                <th>Window End</th>
                <th>Margin</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {checks.map((check) => (
                <tr key={check.id}>
                  <td><strong>{check.asset_code}</strong></td>
                  <td>{check.vessel_name}</td>
                  <td>{check.route_segment?.from_location} → {check.route_segment?.to_location}</td>
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
