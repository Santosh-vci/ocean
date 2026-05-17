import { GridDate } from "../components/GridDate";
import { SvgIcon } from "../components/SvgIcon";
import { formatGridDateLabel } from "../lib/gridDate";
import type { AuditEvent, CurrentUser, DashboardKpi, DashboardReadModel } from "../types";

type DashboardPageProps = {
  auditEvents: AuditEvent[];
  currentUser: CurrentUser;
  dashboard: DashboardReadModel | null;
  onNavigate: (path: string) => void;
};

function toneClass(tone: string | undefined) {
  if (tone === "critical") return "critical";
  if (tone === "pending" || tone === "warning") return "pending";
  return "ok";
}

function formatKpiValue(kpi: DashboardKpi) {
  if (typeof kpi.value === "number") {
    return `${Math.round(kpi.value).toLocaleString()}${kpi.unit ? ` ${kpi.unit}` : ""}`;
  }
  return kpi.value;
}

function short(value: string | undefined | null) {
  return value ? value.replaceAll("_", " ").toUpperCase() : "?";
}

function timeLabel(value: string) {
  return formatGridDateLabel(value);
}

export function DashboardPage({
  auditEvents,
  currentUser,
  dashboard,
  onNavigate,
}: DashboardPageProps) {
  const role = dashboard?.roleShape;
  const planRisk = dashboard?.planRisk;
  const queue = dashboard?.queuePressure;
  const kpis = dashboard?.kpis ?? [];
  const recentAudit = auditEvents.slice(0, 5);

  return (
    <section className="workspace-page situation-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Control Tower / Network Situation</p>
          <h1>Network Situation</h1>
        </div>
        <div className="planning-actions">
          <span className={`phase-chip ${toneClass(planRisk?.tone)}`}>
            Live read model - {planRisk?.liveLabel ?? "No active read model"}
          </span>
          <button onClick={() => onNavigate("/schedule/published-plan")} type="button">
            Open plan
          </button>
          <button onClick={() => onNavigate("/exceptions/center")} type="button">
            Open exceptions
          </button>
        </div>
      </header>

      <div className="metric-strip six-up situation-kpis">
        {kpis.length ? (
          kpis.map((kpi) => (
            <button key={kpi.key} onClick={() => onNavigate(kpi.href)} type="button">
              <span>{kpi.label}</span>
              <strong className={`${toneClass(kpi.tone)}-text`}>{formatKpiValue(kpi)}</strong>
              <em>{kpi.detail}</em>
            </button>
          ))
        ) : (
          <div>
            <span>Read model</span>
            <strong>Loading</strong>
          </div>
        )}
      </div>

      <div className="situation-layout">
        <section className="board-surface exception-queue-panel">
          <div className="grid-header">
            <div>
              <SvgIcon name="rule" />
              <strong>Exception queue</strong>
            </div>
            <span>{planRisk?.blockingConflicts ?? 0} blockers active</span>
          </div>

          <div className="exception-cards">
            {(dashboard?.conflictAggregation ?? []).slice(0, 5).map((conflict) => (
              <button
                className={`exception-card ${toneClass(conflict.tone)}`}
                key={`${conflict.code}-${conflict.objectType}`}
                onClick={() => onNavigate(conflict.href)}
                type="button"
              >
                <span>Severity: {short(conflict.severity)}</span>
                <strong>{conflict.code}</strong>
                <em>
                  {conflict.blocking} blocking / {conflict.total} total ? {conflict.objectType}
                </em>
              </button>
            ))}
            {(dashboard?.conflictAggregation ?? []).length === 0 ? (
              <div className="exception-card ok">
                <span>Severity: Clear</span>
                <strong>No active conflicts</strong>
                <em>Current plan has no unresolved dashboard exceptions.</em>
              </div>
            ) : null}
          </div>

          <div className="priority-action-list">
            <h2>Priority actions</h2>
            {(dashboard?.priorityActions ?? []).map((action) => (
              <button key={`${action.label}-${action.sourceId ?? action.href}`} onClick={() => onNavigate(action.href)} type="button">
                <span className={`status-chip ${toneClass(action.severity)}`}>{short(action.severity)}</span>
                <strong>{action.label}</strong>
                <em>{action.detail}</em>
              </button>
            ))}
          </div>
        </section>

        <section className="board-surface control-timeline-panel">
          <div className="grid-header">
            <div>
              <SvgIcon name="account-tree" />
              <strong>Network resource timeline</strong>
            </div>
            <span>Read model ? OGV ? jetty ? tug/barge ? CTS</span>
          </div>
          <div className="timeline-timebar">
            <strong>Asset resource</strong>
            <span>08:00</span>
            <span>10:00</span>
            <span>12:00</span>
            <span>14:00</span>
            <span>16:00 now</span>
            <span>18:00</span>
          </div>
          <div className="control-timeline-grid">
            <i className="timeline-now" />
            {(dashboard?.resourceTimeline ?? []).map((group) => (
              <div className="timeline-group" key={group.category}>
                <h2>{group.category}</h2>
                {group.rows.slice(0, 6).map((row) => (
                  <div className="timeline-row" key={`${group.category}-${row.tripId}-${row.label}`}>
                    <strong>{row.label}</strong>
                    <div>
                      <button
                        className={`timeline-block ${toneClass(row.tone)}`}
                        onClick={() => onNavigate("/schedule/published-plan")}
                        style={{ left: `${row.offsetPct}%`, width: `${row.widthPct}%` }}
                        title={`${row.tripId}: ${timeLabel(row.start)} - ${timeLabel(row.end)}`}
                        type="button"
                      >
                        {row.tripId} ? {short(row.status)}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </section>

        <aside className="board-surface situation-action-rail">
          <div className="grid-header">
            <div>
              <SvgIcon name="dashboard" />
              <strong>Action rail</strong>
            </div>
            <span>{role?.profile.replaceAll("_", " ") ?? "loading"}</span>
          </div>

          <section className="situation-risk-card">
            <span className={`status-chip ${toneClass(planRisk?.tone)}`}>
              {planRisk?.riskScore ?? 0}% risk
            </span>
            <h2>{planRisk?.highestRiskOgv.vesselName ?? "No active OGV"}</h2>
            <p>{planRisk?.highestRiskOgv.detail ?? "Waiting for dashboard read model."}</p>
            <dl>
              <div>
                <dt>Constrained resource</dt>
                <dd>{planRisk?.mostConstrainedResource.label ?? "?"}</dd>
              </div>
              <div>
                <dt>First blocker</dt>
                <dd>{planRisk?.firstBlockingConstraint ?? "NONE"}</dd>
              </div>
              <div>
                <dt>Publish state</dt>
                <dd>{planRisk?.publishState ?? "Unknown"}</dd>
              </div>
            </dl>
          </section>

          <section className="queue-pressure-card">
            <h2>Queue pressure</h2>
            <dl>
              <div>
                <dt>Peak jetty</dt>
                <dd>{queue?.peakResource ?? "?"}</dd>
              </div>
              <div>
                <dt>Tug/barge pairs</dt>
                <dd>{queue?.fleet.tugBargePairs ?? 0}</dd>
              </div>
              <div>
                <dt>Bridge/tide risk</dt>
                <dd>{queue?.navigationRisk.label ?? "Low"}</dd>
              </div>
            </dl>
            <div className="queue-mini-list">
              {(queue?.jetties ?? []).slice(0, 4).map((jetty) => (
                <span key={jetty.code}>
                  {jetty.code}<strong>{jetty.queuedTrips}</strong>
                </span>
              ))}
            </div>
          </section>

          <section className="drilldown-card">
            <h2>Drill-downs</h2>
            {(dashboard?.drilldowns ?? []).map((item) => (
              <button key={item.href} onClick={() => onNavigate(item.href)} type="button">
                <strong>{item.label}</strong>
                <span>{item.detail}</span>
              </button>
            ))}
          </section>

          <section className="audit-mini-card">
            <h2>Recent audit</h2>
            {recentAudit.map((event) => (
              <p key={event.id}>
                <GridDate value={event.created_at} />
                <strong>{event.action}</strong>
              </p>
            ))}
            {recentAudit.length === 0 ? <p>No audit events visible for {currentUser.email}.</p> : null}
          </section>
        </aside>
      </div>
    </section>
  );
}
