import { Fragment, useEffect, useMemo, useState } from "react";

import { GridDate } from "../components/GridDate";
import { SvgIcon } from "../components/SvgIcon";
import { formatGridDateLabel } from "../lib/gridDate";
import type {
  ApprovalRequestRecord,
  ConflictRecord,
  ImpactChainAssessmentRecord,
  ImpactChainNodeRecord,
  OverrideRequestRecord,
  ScenarioAssumptionRecord,
  ScenarioConstraintEvaluationRecord,
  ScenarioOgvProjectionRecord,
  ScenarioResourceUtilizationRecord,
  ScenarioRunRecord,
  ScenarioTripProjectionRecord,
  OperationsHealthRiskRecord,
  SchedulingOverview,
  SimulationScenarioRecord,
  TrackingAlertRecord,
  TripRecord,
} from "../types";

export type ScenarioSourceInput = {
  kind: "manual" | "conflict" | "override" | "tracking_alert";
  id?: number | null;
  name?: string;
};

export type ScenarioAssumptionDraft = {
  kind: string;
  scope_type: string;
  scope_id: number | null;
  payload: Record<string, unknown>;
  effective_from?: string | null;
  effective_to?: string | null;
};

type RecoveryPageProps = {
  overview: SchedulingOverview | null;
  canEdit?: boolean;
  isActionRunning?: boolean;
  onApprove?: () => void;
  onCreateAssumption?: (scenarioId: number, assumption: ScenarioAssumptionDraft) => void;
  onCreateScenario?: (source: ScenarioSourceInput) => void;
  onPublish?: () => void;
  onReject?: () => void;
  onRunSimulation?: (scenarioId?: number) => void;
  onSubmitApproval?: () => void;
  onPromoteScenario?: (scenarioId?: number, runId?: number) => void;
  onPublishTriage?: () => void;
  canPublish?: boolean;
};

type QueueSelection = {
  id: number;
  kind: "conflict" | "override" | "tracking" | "health";
};

const EMPTY_CONFLICTS: ConflictRecord[] = [];
const EMPTY_TRIPS: TripRecord[] = [];
const EMPTY_APPROVALS: ApprovalRequestRecord[] = [];
const EMPTY_OVERRIDES: OverrideRequestRecord[] = [];
const EMPTY_SCENARIOS: SimulationScenarioRecord[] = [];
const EMPTY_TRACKING_ALERTS: TrackingAlertRecord[] = [];
const EMPTY_HEALTH_RISKS: OperationsHealthRiskRecord[] = [];
const EMPTY_ASSUMPTIONS: ScenarioAssumptionRecord[] = [];
const EMPTY_CONSTRAINT_EVALUATIONS: ScenarioConstraintEvaluationRecord[] = [];
const EMPTY_OGV_PROJECTIONS: ScenarioOgvProjectionRecord[] = [];
const EMPTY_RESOURCE_UTILIZATIONS: ScenarioResourceUtilizationRecord[] = [];
const EMPTY_IMPACT_ASSESSMENTS: ImpactChainAssessmentRecord[] = [];

const ASSUMPTION_OPTIONS = [
  { value: "trip_delay", label: "Trip delay", scopeType: "trip" },
  { value: "asset_outage", label: "Asset outage", scopeType: "asset" },
  { value: "rate_change", label: "Rate change", scopeType: "asset" },
  { value: "window_change", label: "Window change", scopeType: "window" },
  { value: "ogv_eta_change", label: "OGV ETA change", scopeType: "ogv" },
  { value: "manual_reassignment", label: "Manual reassignment", scopeType: "assignment" },
] as const;

const OVERRIDE_STATE_KEYS: Record<string, string> = {
  next_action: "nextAction",
  next_constraint: "nextConstraint",
  planned_arrival: "plannedArrival",
  planned_departure: "plannedDeparture",
};

function statusTone(status: string | undefined, blocking = false) {
  if (blocking || status === "critical" || status === "blocked" || status === "rejected") {
    return "critical";
  }
  if (status === "warning" || status === "pending" || status === "proposed") return "pending";
  return "ok";
}

function short(value: string | null | undefined) {
  return value ? value.replaceAll("_", " ").toUpperCase() : "—";
}

function dt(value: string | null | undefined) {
  return formatGridDateLabel(value, "-");
}

function num(value: unknown, fallback = 0) {
  return typeof value === "number" ? value : fallback;
}

function valueNum(value: unknown, fallback = 0) {
  if (typeof value === "number") return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  return fallback;
}

function money(value: unknown) {
  return valueNum(value, 0).toLocaleString(undefined, {
    maximumFractionDigits: 0,
    style: "currency",
    currency: "USD",
  });
}

function signedMinutes(value: unknown) {
  const minutes = valueNum(value, 0);
  return `${minutes > 0 ? "+" : ""}${minutes}m`;
}

function runSummaryNum(run: ScenarioRunRecord | undefined, group: string, key: string) {
  const groupValue = run?.summary[group];
  if (!groupValue || typeof groupValue !== "object") return 0;
  return valueNum((groupValue as Record<string, unknown>)[key], 0);
}

function constraintTone(severity?: string) {
  if (severity === "critical") return "critical";
  if (severity === "warning") return "pending";
  return "ok";
}

function projectionChanged(projection?: ScenarioTripProjectionRecord) {
  return Boolean(
    projection
    && (
      projection.delay_minutes
      || projection.projected_start !== projection.baseline_start
      || projection.projected_end !== projection.baseline_end
      || projection.assignment_delta.resourceChanged
    ),
  );
}

function assignmentChain(
  projection: ScenarioTripProjectionRecord | undefined,
  trip: TripRecord,
  variant: "baseline" | "projected",
) {
  const resources = projection?.assignment_delta[
    variant === "baseline" ? "baselineResources" : "projectedResources"
  ];
  if (resources && typeof resources === "object") {
    const values = resources as Record<string, string>;
    return [values.tug, values.barge, values.cts].filter(Boolean).join(" / ");
  }
  return [
    trip.assignment?.tug?.code ?? "NONE",
    trip.assignment?.barge?.code ?? "NONE",
    trip.assignment?.cts?.code ?? "NONE",
  ].join(" / ");
}

function sourceAssumptionText(item?: ScenarioConstraintEvaluationRecord) {
  return item?.source_assumption_ids.length
    ? item.source_assumption_ids.join(", ")
    : "Derived from projected schedule";
}

function stateValue(state: Record<string, unknown>, key: string) {
  const value = state[OVERRIDE_STATE_KEYS[key] ?? key];
  if (value === null || value === undefined || value === "") return "none";
  return String(value).replaceAll("_", " ");
}

function overrideDelta(override: OverrideRequestRecord) {
  const changedKeys = Object.keys(override.requested_change);
  if (!changedKeys.length) return { before: "none", after: "none" };
  const before = changedKeys.map((key) => `${key}: ${stateValue(override.before_state, key)}`).join(" | ");
  const after = changedKeys.map((key) => `${key}: ${stateValue(override.after_state, key)}`).join(" | ");
  return { before, after };
}

function impactSummary(override: OverrideRequestRecord) {
  const assessment = override.impact_assessment;
  if (!assessment) return "Impact not calculated";
  const windowNodes = assessment.nodes.filter((node) => node.type.includes("window"));
  const riskNode = windowNodes.find((node) => node.status === "critical")
    ?? windowNodes.find((node) => node.status === "warning")
    ?? windowNodes.find((node) => node.type === "tide_window")
    ?? windowNodes[0];
  const riskLabel = riskNode ? ` | ${riskNode.label} ${riskNode.value}` : "";
  return `+${assessment.delay_minutes}m${riskLabel}`;
}

function impactNodesFor(
  selectedConflict: ConflictRecord | undefined,
  selectedOverride: OverrideRequestRecord | undefined,
): ImpactChainNodeRecord[] {
  if (selectedOverride) {
    return selectedOverride.impact_assessment?.nodes ?? [];
  }
  if (!selectedConflict) return [];
  return [
    {
      id: "source",
      type: "source_event",
      label: selectedConflict.code,
      value: selectedConflict.severity.toUpperCase(),
      status: statusTone(selectedConflict.severity, selectedConflict.is_blocking),
      detail: selectedConflict.message,
    },
    {
      id: "target",
      type: "final_risk_target",
      label: "FINAL RISK TARGET",
      value: selectedConflict.vessel_name ?? "Network",
      status: statusTone(selectedConflict.severity, selectedConflict.is_blocking),
      detail: selectedConflict.trip_ref ?? "Network",
    },
  ];
}

function trackingImpactNodes(alert: TrackingAlertRecord | undefined): ImpactChainNodeRecord[] {
  if (!alert) return [];
  const variance = valueNum(alert.evidence.varianceMinutes, 0);
  return [
    {
      id: "tracking-source",
      type: "observed_signal",
      label: "OBSERVED SIGNAL",
      value: alert.source_ping_ref ?? short(alert.source_kind),
      status: alert.severity,
      detail: `${alert.source_id} evidence linked to ${alert.asset_code}.`,
    },
    {
      id: "eta-projection",
      type: "eta_projection",
      label: "ETA VARIANCE",
      value: variance ? `${variance > 0 ? "+" : ""}${variance}m` : "NO VARIANCE",
      status: alert.severity,
      detail: `${short(alert.schedule_event_type)} planned vs observed ETA.`,
      plannedAt: alert.schedule_event_planned_at,
      projectedAt: String(alert.evidence.observedEta ?? "") || null,
      marginMinutes: variance,
    },
    {
      id: "tracking-alert",
      type: "tracking_alert",
      label: short(alert.alert_type),
      value: short(alert.severity),
      status: alert.severity,
      detail: alert.message,
    },
  ];
}

function healthImpactNodes(risk: OperationsHealthRiskRecord | undefined): ImpactChainNodeRecord[] {
  if (!risk) return [];
  return [
    {
      id: "health-source",
      type: "device_health",
      label: "DEVICE HEALTH",
      value: short(risk.healthStatus ?? risk.reason),
      status: risk.severity,
      detail: `${risk.feedId} / ${risk.deviceId ?? risk.assetCode}`,
      projectedAt: risk.observedAt,
    },
    {
      id: "feed-trust",
      type: "feed_trust",
      label: "FEED TRUST",
      value: short(risk.deviceStatus ?? "review"),
      status: risk.severity,
      detail: "Auto-confirm is blocked until the device or feed recovers.",
    },
    {
      id: "ops-risk",
      type: "operations_risk",
      label: "OPERATIONS RISK",
      value: risk.assetCode || risk.candidateId,
      status: risk.severity,
      detail: risk.message,
    },
  ];
}

function nodeValue(node: ImpactChainNodeRecord) {
  if (node.type === "source_event" && node.projectedAt) return dt(node.projectedAt);
  return node.value;
}

function nodeDetail(node: ImpactChainNodeRecord) {
  if (node.type === "source_event" && node.plannedAt) {
    return `Effective start against planned ${dt(node.plannedAt)}.`;
  }
  return node.detail;
}

function selectedConflictFor(conflicts: ConflictRecord[], selectedId: number | null) {
  return conflicts.find((conflict) => conflict.id === selectedId) ?? conflicts[0];
}

function approvalCoverage(request: ApprovalRequestRecord | undefined) {
  if (!request) return { approved: 0, required: 0 };
  return {
    approved: request.decisions.filter((decision) => decision.decision === "approve").length,
    required: request.required_authorities.length,
  };
}

function assumptionSummary(assumption: ScenarioAssumptionRecord) {
  switch (assumption.kind) {
    case "trip_delay":
      return `+${num(assumption.payload.delay_minutes, 0)}m`;
    case "asset_outage":
      return String(assumption.payload.asset_code ?? "asset outage");
    case "rate_change":
      return `${String(assumption.payload.rate_tph ?? "?")} TPH`;
    case "window_change":
      return String(assumption.payload.window_code ?? "window change");
    case "ogv_eta_change":
      return dt(String(assumption.payload.eta ?? ""));
    case "manual_reassignment":
      return `Assignment ${String(assumption.payload.assignment_id ?? "?")}`;
    default:
      return "Configured";
  }
}

export function ExceptionCenterPage({
  overview,
  canEdit = false,
  isActionRunning = false,
  onCreateScenario,
  onPublishTriage,
}: RecoveryPageProps) {
  const conflicts = overview?.conflicts ?? EMPTY_CONFLICTS;
  const trips = overview?.trips ?? EMPTY_TRIPS;
  const overrides = overview?.overrideRequests ?? EMPTY_OVERRIDES;
  const trackingAlerts = overview?.trackingAlerts ?? EMPTY_TRACKING_ALERTS;
  const healthRisks = overview?.operationsHealthSummary?.risks ?? EMPTY_HEALTH_RISKS;
  const openTrackingAlerts = trackingAlerts.filter((alert) => (
    alert.status === "open" || alert.status === "acknowledged"
  ));
  const [selectedQueueItem, setSelectedQueueItem] = useState<QueueSelection | null>(
    conflicts[0]
      ? { id: conflicts[0].id, kind: "conflict" }
      : openTrackingAlerts[0]
        ? { id: openTrackingAlerts[0].id, kind: "tracking" }
        : healthRisks[0]
          ? { id: healthRisks[0].id, kind: "health" }
          : overrides[0]
            ? { id: overrides[0].id, kind: "override" }
            : null,
  );
  const selectedConflict = selectedQueueItem?.kind === "conflict"
    ? selectedConflictFor(conflicts, selectedQueueItem.id)
    : selectedQueueItem
      ? undefined
      : conflicts[0];
  const selectedTrackingAlert = selectedQueueItem?.kind === "tracking"
    ? openTrackingAlerts.find((alert) => alert.id === selectedQueueItem.id) ?? openTrackingAlerts[0]
    : !selectedConflict && !selectedQueueItem
      ? openTrackingAlerts[0]
      : undefined;
  const selectedHealthRisk = selectedQueueItem?.kind === "health"
    ? healthRisks.find((risk) => risk.id === selectedQueueItem.id) ?? healthRisks[0]
    : !selectedConflict && !selectedTrackingAlert && !selectedQueueItem
      ? healthRisks[0]
      : undefined;
  const selectedOverride = selectedQueueItem?.kind === "override"
    ? overrides.find((override) => override.id === selectedQueueItem.id) ?? (!selectedConflict ? overrides[0] : undefined)
    : !selectedConflict && !selectedTrackingAlert && !selectedHealthRisk ? overrides[0] : undefined;
  const selectedOverrideDelta = selectedOverride ? overrideDelta(selectedOverride) : null;
  const selectedImpactAssessment = selectedOverride?.impact_assessment;
  const impactNodes = selectedTrackingAlert
    ? trackingImpactNodes(selectedTrackingAlert)
    : selectedHealthRisk
      ? healthImpactNodes(selectedHealthRisk)
      : impactNodesFor(selectedConflict, selectedOverride);
  const selectedTrip = trips.find((trip) => (
    trip.id === selectedConflict?.trip || trip.id === selectedTrackingAlert?.trip
  ));
  const critical = conflicts.filter((conflict) => conflict.severity === "critical").length;
  const warning = conflicts.filter((conflict) => conflict.severity === "warning").length;
  const pending = conflicts.filter((conflict) => conflict.is_blocking).length;
  const trackingCritical = openTrackingAlerts.filter((alert) => alert.severity === "critical").length;
  const trackingWarning = openTrackingAlerts.filter((alert) => alert.severity === "warning").length;
  const healthCritical = healthRisks.filter((risk) => risk.severity === "critical").length;
  const healthWarning = healthRisks.filter((risk) => risk.severity === "warning").length;
  const activeQueueCount = conflicts.length + overrides.length + openTrackingAlerts.length + healthRisks.length;

  return (
    <section className="workspace-page recovery-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Recovery Loop / Exception Center</p>
          <h1>Exception Center</h1>
        </div>
        <div className="planning-actions">
          <span className="phase-chip">Active triage</span>
          <button
            disabled={!canEdit || !onCreateScenario || isActionRunning || Boolean(selectedTrackingAlert)}
            onClick={() => onCreateScenario?.(
              selectedConflict
                ? { kind: "conflict", id: selectedConflict.id }
                : selectedOverride
                  ? { kind: "override", id: selectedOverride.id }
                  : { kind: "manual" },
            )}
            title={selectedTrackingAlert
              ? "Use the observed alert detail to create a scenario."
              : !canEdit
                ? "Your role cannot convert exceptions to scenarios."
                : undefined}
            type="button"
          >
            Convert to scenario
          </button>
          <button
            disabled={!onPublishTriage || isActionRunning}
            onClick={onPublishTriage}
            type="button"
          >
            Publish triage view
          </button>
        </div>
      </header>

      <div className="metric-strip seven-up recovery-kpis">
        <div><span>Active</span><strong>{activeQueueCount}</strong></div>
        <div><span>Critical</span><strong className="critical-text">{critical + trackingCritical + healthCritical}</strong></div>
        <div><span>Warning</span><strong className="warning-text">{warning + trackingWarning + healthWarning}</strong></div>
        <div><span>Observed</span><strong className={openTrackingAlerts.length ? "warning-text" : ""}>{openTrackingAlerts.length}</strong></div>
        <div><span>Pending</span><strong>{pending}</strong></div>
        <div><span>Overrides</span><strong className="warning-text">{overrides.length}</strong></div>
        <div><span>Health</span><strong className={healthRisks.length ? "critical-text" : "success-text"}>{healthRisks.length}</strong></div>
      </div>

      <div className="exception-layout">
        <aside className="board-surface recovery-filter-rail">
          <div className="grid-header">
            <div><SvgIcon name="rule" /><strong>Triage filters</strong></div>
          </div>
          <section>
            <h2>Severity</h2>
            <span>Critical ({critical + trackingCritical + healthCritical})</span>
            <span>Warning ({warning + trackingWarning + healthWarning})</span>
            <span>Blocking ({pending})</span>
            <span>Observed ({openTrackingAlerts.length})</span>
            <span>Health ({healthRisks.length})</span>
          </section>
          <section>
            <h2>OGV focus</h2>
            {trips.slice(0, 4).map((trip) => (
              <button
                disabled={!conflicts.some((conflict) => conflict.trip === trip.id)}
                key={trip.id}
                onClick={() => {
                  const conflict = conflicts.find((item) => item.trip === trip.id);
                  if (conflict) setSelectedQueueItem({ id: conflict.id, kind: "conflict" });
                }}
                type="button"
              >
                {trip.voyage.vessel_name}
              </button>
            ))}
          </section>
        </aside>

        <section className="board-surface recovery-grid-panel">
          <div className="grid-header">
            <div><SvgIcon name="schedule" /><strong>Active exception queue</strong></div>
            <span>Severity · source · owner · impact · next governed action</span>
          </div>
          <div className="grid-scroll">
            <table className="planning-table logistics-table">
              <thead>
                <tr>
                  <th>Severity</th><th>Raised</th><th>ID</th><th>Type</th>
                  <th>Affected OGV</th><th>Resource</th><th>Impact</th><th>Status</th><th>Next</th>
                </tr>
              </thead>
              <tbody>
                {openTrackingAlerts.map((alert) => (
                  <tr
                    className={selectedTrackingAlert?.id === alert.id ? "selected-row" : ""}
                    key={`tracking-${alert.id}`}
                    onClick={() => setSelectedQueueItem({ id: alert.id, kind: "tracking" })}
                  >
                    <td><span className={`status-chip ${statusTone(alert.severity)}`}>{short(alert.severity)}</span></td>
                    <td><GridDate value={alert.opened_at} /></td>
                    <td>{alert.alert_id}</td>
                    <td>{short(alert.alert_type)}</td>
                    <td>{alert.vessel_name ?? "Observed asset"}</td>
                    <td>{alert.asset_code}</td>
                    <td>
                      {typeof alert.evidence.varianceMinutes === "number"
                        ? `${alert.evidence.varianceMinutes > 0 ? "+" : ""}${alert.evidence.varianceMinutes}m ETA`
                        : "Observed candidate"}
                    </td>
                    <td>{short(alert.status)}</td>
                    <td>WATCH</td>
                  </tr>
                ))}
                {healthRisks.map((risk) => (
                  <tr
                    className={selectedHealthRisk?.id === risk.id ? "selected-row" : ""}
                    key={`health-${risk.id}`}
                    onClick={() => setSelectedQueueItem({ id: risk.id, kind: "health" })}
                  >
                    <td><span className={`status-chip ${statusTone(risk.severity)}`}>{short(risk.severity)}</span></td>
                    <td><GridDate value={risk.observedAt} /></td>
                    <td>{risk.candidateId}</td>
                    <td>DEVICE HEALTH</td>
                    <td>{risk.feedId}</td>
                    <td>{risk.deviceId ?? risk.assetCode}</td>
                    <td>{short(risk.healthStatus ?? risk.reason)}</td>
                    <td>{short(risk.status)}</td>
                    <td>REVIEW</td>
                  </tr>
                ))}
                {conflicts.map((conflict) => (
                  <tr
                    className={selectedConflict?.id === conflict.id ? "selected-row" : ""}
                    key={conflict.id}
                    onClick={() => setSelectedQueueItem({ id: conflict.id, kind: "conflict" })}
                  >
                    <td><span className={`status-chip ${statusTone(conflict.severity, conflict.is_blocking)}`}>{short(conflict.severity)}</span></td>
                    <td><GridDate value={conflict.created_at} /></td>
                    <td>EX-{String(conflict.id).padStart(4, "0")}</td>
                    <td>{conflict.code}</td>
                    <td>{conflict.vessel_name ?? "Network"}</td>
                    <td>{conflict.object_id || conflict.object_type || "N/A"}</td>
                    <td>{conflict.is_blocking ? "+5h delay risk" : "Watch"}</td>
                    <td>{conflict.resolved_at ? "RESOLVED" : "ACTIVE"}</td>
                    <td>{conflict.is_blocking ? "SIM" : "MONITOR"}</td>
                  </tr>
                ))}
                {overrides.map((override) => (
                  <tr
                    className={selectedOverride?.id === override.id ? "selected-row" : ""}
                    key={`override-${override.id}`}
                    onClick={() => setSelectedQueueItem({ id: override.id, kind: "override" })}
                  >
                    <td><span className="status-chip pending">OVERRIDE</span></td>
                    <td><GridDate value={override.created_at} /></td>
                    <td>OR-{String(override.id).padStart(4, "0")}</td>
                    <td>{short(override.reason_code)}</td>
                    <td>{override.vessel_name ?? "Network"}</td>
                    <td>{override.trip_ref ?? (override.assignment ? `Assignment ${override.assignment}` : "Assignment")}</td>
                    <td>{impactSummary(override)}</td>
                    <td><span className={`status-chip ${statusTone(override.status)}`}>{short(override.status)}</span></td>
                    <td>GOVERNED</td>
                  </tr>
                ))}
                {!conflicts.length && !overrides.length && !openTrackingAlerts.length && !healthRisks.length ? (
                  <tr>
                    <td colSpan={9}>No active exceptions, observed tracking alerts, device health risks, or governed overrides for the active plan.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="board-surface logistics-inspector recovery-inspector">
          <div className="grid-header">
            <div><SvgIcon name="account-tree" /><strong>Exception detail</strong></div>
            <span>
              {selectedConflict
                ? `EX-${selectedConflict.id}`
                : selectedTrackingAlert
                  ? selectedTrackingAlert.alert_id
                  : selectedHealthRisk
                    ? selectedHealthRisk.candidateId
                    : selectedOverride
                      ? `OR-${selectedOverride.id}`
                      : "No exception"}
            </span>
          </div>
          {selectedConflict ? (
            <div className="inspector-body">
              <span className={`status-chip ${statusTone(selectedConflict.severity, selectedConflict.is_blocking)}`}>
                {short(selectedConflict.severity)}
              </span>
              <h2>{selectedConflict.code}</h2>
              <p>{selectedConflict.message}</p>
              <dl>
                <div><dt>OGV delay</dt><dd>{selectedConflict.is_blocking ? "+5h 12m" : "0h"}</dd></div>
                <div><dt>Trip</dt><dd>{selectedTrip?.trip_id ?? "Network"}</dd></div>
                <div><dt>Owner</dt><dd>{selectedTrip?.assignment?.owner_organization?.name ?? "Control tower"}</dd></div>
              </dl>
              <section className="recovery-box">
                <strong>Recommended recovery</strong>
                <p>Run simulation before any plan mutation. Published plan remains untouched.</p>
              </section>
            </div>
          ) : selectedTrackingAlert ? (
            <div className="inspector-body">
              <span className={`status-chip ${statusTone(selectedTrackingAlert.severity)}`}>
                OBSERVED {short(selectedTrackingAlert.severity)}
              </span>
              <h2>{short(selectedTrackingAlert.alert_type)}</h2>
              <p>{selectedTrackingAlert.message}</p>
              <dl>
                <div><dt>Source</dt><dd>{selectedTrackingAlert.source_id}</dd></div>
                <div><dt>Candidate status</dt><dd>{short(selectedTrackingAlert.status)}</dd></div>
                <div><dt>Asset</dt><dd>{selectedTrackingAlert.asset_code}</dd></div>
                <div><dt>Trip</dt><dd>{selectedTrackingAlert.trip_ref ?? "Unlinked"}</dd></div>
                <div><dt>Planned event</dt><dd>{short(selectedTrackingAlert.schedule_event_type)}</dd></div>
                <div><dt>Planned at</dt><dd><GridDate value={selectedTrackingAlert.schedule_event_planned_at ?? ""} /></dd></div>
                <div><dt>Observed ETA</dt><dd>{dt(String(selectedTrackingAlert.evidence.observedEta ?? ""))}</dd></div>
                <div><dt>Variance</dt><dd>{valueNum(selectedTrackingAlert.evidence.varianceMinutes, 0)}m</dd></div>
                <div><dt>Source ping</dt><dd>{selectedTrackingAlert.source_ping_ref ?? "No ping"}</dd></div>
              </dl>
              <section className="recovery-box">
                <strong>Observed candidate</strong>
                <p>Tracking evidence is visible for triage, but it does not mutate the approved schedule.</p>
              </section>
              {selectedTrackingAlert.alert_type === "delay" ? (
                <button
                  disabled={!canEdit || !onCreateScenario || isActionRunning}
                  onClick={() => onCreateScenario?.({
                    kind: "tracking_alert",
                    id: selectedTrackingAlert.id,
                  })}
                  type="button"
                >
                  Create scenario
                </button>
              ) : null}
            </div>
          ) : selectedHealthRisk ? (
            <div className="inspector-body">
              <span className={`status-chip ${statusTone(selectedHealthRisk.severity)}`}>
                HEALTH {short(selectedHealthRisk.severity)}
              </span>
              <h2>{selectedHealthRisk.deviceId ?? selectedHealthRisk.assetCode}</h2>
              <p>{selectedHealthRisk.message}</p>
              <dl>
                <div><dt>Feed</dt><dd>{selectedHealthRisk.feedId}</dd></div>
                <div><dt>Candidate</dt><dd>{selectedHealthRisk.candidateId}</dd></div>
                <div><dt>Health</dt><dd>{short(selectedHealthRisk.healthStatus)}</dd></div>
                <div><dt>Device status</dt><dd>{short(selectedHealthRisk.deviceStatus)}</dd></div>
                <div><dt>Reason</dt><dd>{short(selectedHealthRisk.reason)}</dd></div>
                <div><dt>Observed</dt><dd><GridDate value={selectedHealthRisk.observedAt} /></dd></div>
              </dl>
              <section className="recovery-box">
                <strong>Trust gate</strong>
                <p>Device health risk blocks trusted auto-confirm until an operator reviews the feed or the device reports healthy again.</p>
              </section>
            </div>
          ) : selectedOverride && selectedOverrideDelta ? (
            <div className="inspector-body">
              <span className={`status-chip ${statusTone(selectedOverride.status)}`}>
                {short(selectedOverride.status)}
              </span>
              <h2>{short(selectedOverride.reason_code)}</h2>
              <p>{selectedOverride.description}</p>
              <dl>
                <div><dt>Actor</dt><dd>{selectedOverride.applied_by_email ?? selectedOverride.requested_by_email ?? "system"}</dd></div>
                <div><dt>Trip</dt><dd>{selectedOverride.trip_ref ?? selectedOverride.vessel_name ?? "Network"}</dd></div>
                <div><dt>Applied</dt><dd><GridDate value={selectedOverride.applied_at ?? selectedOverride.created_at} /></dd></div>
                <div><dt>Risk</dt><dd>{short(selectedImpactAssessment?.status ?? "not_calculated")}</dd></div>
                <div><dt>Delay</dt><dd>{selectedImpactAssessment ? `+${selectedImpactAssessment.delay_minutes}m` : "Impact not calculated"}</dd></div>
                <div><dt>Eff. start</dt><dd><GridDate value={String(selectedImpactAssessment?.metadata.actualStartAt ?? "")} /></dd></div>
                <div><dt>Before</dt><dd>{selectedOverrideDelta.before}</dd></div>
                <div><dt>After</dt><dd>{selectedOverrideDelta.after}</dd></div>
              </dl>
              <section className="recovery-box">
                <strong>Governed adjustment</strong>
                <p>Captured with reason code, actor, before/after state, and timestamp.</p>
              </section>
            </div>
          ) : null}
        </aside>
      </div>

      <section className="board-surface impact-chain">
        <div className="grid-header">
          <div><SvgIcon name="account-tree" /><strong>Impact chain propagation</strong></div>
          <span>Source event → logistics inferred → system projected → final risk target</span>
        </div>
        <div className="impact-chain-track">
          {impactNodes.length ? impactNodes.map((node, index) => (
            <Fragment key={node.id}>
              {index ? <span className="chain-line" /> : null}
              <span className={`chain-node ${node.status === "critical" ? "critical" : node.status === "warning" || node.status === "pending" ? "pending" : ""}`}>
                <strong>{node.label}</strong>
                <em>{nodeValue(node)}</em>
                <small>{nodeDetail(node)}</small>
              </span>
            </Fragment>
          )) : (
            <span className="chain-node">
              <strong>Impact not calculated</strong>
              <em>No assessment</em>
              <small>Select a governed override with a calculated impact chain.</small>
            </span>
          )}
        </div>
      </section>
    </section>
  );
}

export function SimulationWorkspacePage({
  overview,
  canEdit = false,
  isActionRunning = false,
  onCreateAssumption,
  onCreateScenario,
  onPromoteScenario,
  onRunSimulation,
  onSubmitApproval,
}: RecoveryPageProps) {
  const scenarios = overview?.simulationScenarios ?? EMPTY_SCENARIOS;
  const trips = overview?.trips ?? EMPTY_TRIPS;
  const [selectedScenarioId, setSelectedScenarioId] = useState<number | null>(null);
  const [manualScenarioName, setManualScenarioName] = useState("");
  const [assumptionKind, setAssumptionKind] = useState("trip_delay");
  const [tripId, setTripId] = useState("");
  const [delayMinutes, setDelayMinutes] = useState("120");
  const [assetCode, setAssetCode] = useState("");
  const [rateTph, setRateTph] = useState("1800");
  const [windowCode, setWindowCode] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [effectiveTo, setEffectiveTo] = useState("");
  const [ogvEta, setOgvEta] = useState("");
  const [assignmentId, setAssignmentId] = useState("");
  const [replacementTug, setReplacementTug] = useState("");
  const [replacementBarge, setReplacementBarge] = useState("");
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [selectedConstraintId, setSelectedConstraintId] = useState<number | null>(null);
  const [hydratedScenarioId, setHydratedScenarioId] = useState<number | null>(null);
  const scenario = useMemo(
    () => scenarios.find((item) => item.id === selectedScenarioId) ?? scenarios[0],
    [scenarios, selectedScenarioId],
  );
  const assumptions = scenario?.assumptions ?? EMPTY_ASSUMPTIONS;
  const latestRun = useMemo(
    () => scenario?.runs.find((item) => item.id === selectedRunId) ?? scenario?.runs[0],
    [scenario, selectedRunId],
  );
  const constraints = latestRun?.constraint_evaluations ?? EMPTY_CONSTRAINT_EVALUATIONS;
  const ogvProjections = latestRun?.ogv_projections ?? EMPTY_OGV_PROJECTIONS;
  const utilizationRows = latestRun?.resource_utilizations ?? EMPTY_RESOURCE_UTILIZATIONS;
  const selectedConstraint = useMemo(
    () => constraints.find((item) => item.id === selectedConstraintId) ?? constraints[0],
    [constraints, selectedConstraintId],
  );
  const impactAssessments = latestRun?.impact_assessments ?? EMPTY_IMPACT_ASSESSMENTS;
  const selectedAssessment = useMemo(
    () => impactAssessments.find((item) => item.trip === selectedConstraint?.trip)
      ?? impactAssessments[0],
    [impactAssessments, selectedConstraint],
  );
  const selectedImpactNodes = selectedAssessment?.nodes ?? [];
  const projectedTrips = useMemo(
    () => new Map(
      (latestRun?.trip_projections ?? []).map((projection) => [projection.trip, projection]),
    ),
    [latestRun],
  );
  const projectedTripsByRef = useMemo(
    () => new Map(
      (latestRun?.trip_projections ?? []).map((projection) => [projection.trip_ref, projection]),
    ),
    [latestRun],
  );
  const comparisonRows = useMemo(
    () => trips.map((trip) => ({
      trip,
      projection: projectedTrips.get(trip.id) ?? projectedTripsByRef.get(
        typeof trip.selection_reason.scenario_projection === "object"
          && trip.selection_reason.scenario_projection
          && "sourceTrip" in trip.selection_reason.scenario_projection
          ? String(trip.selection_reason.scenario_projection.sourceTrip)
          : typeof trip.selection_reason.cloned_from === "string"
            ? trip.selection_reason.cloned_from
            : trip.trip_id,
      ),
    })),
    [projectedTrips, projectedTripsByRef, trips],
  );
  const visibleComparisonRows = useMemo(() => {
    const changedRows = comparisonRows.filter((row) => projectionChanged(row.projection));
    return changedRows.length ? changedRows : comparisonRows.slice(0, 6);
  }, [comparisonRows]);
  const timelineRows = useMemo(() => visibleComparisonRows.slice(0, 8), [visibleComparisonRows]);
  const timelineTimes = useMemo(
    () => timelineRows.flatMap((row) => [
      new Date(row.projection?.baseline_start ?? row.trip.planned_start).getTime(),
      new Date(row.projection?.baseline_end ?? row.trip.planned_end).getTime(),
      new Date(row.projection?.projected_start ?? row.trip.planned_start).getTime(),
      new Date(row.projection?.projected_end ?? row.trip.planned_end).getTime(),
    ]).filter((value) => Number.isFinite(value)),
    [timelineRows],
  );
  const timelineStart = timelineTimes.length ? Math.min(...timelineTimes) : Date.now();
  const timelineEnd = timelineTimes.length ? Math.max(...timelineTimes) : timelineStart + 1;
  const timelineSpan = Math.max(timelineEnd - timelineStart, 1);
  const selectedAssumptionOption = ASSUMPTION_OPTIONS.find(
    (option) => option.value === assumptionKind,
  ) ?? ASSUMPTION_OPTIONS[0];
  const selectedTripId = tripId || String(trips[0]?.id ?? "");
  const selectedTrip = trips.find((trip) => trip.id === Number(selectedTripId));
  const selectedAssignmentId = assignmentId || String(
    trips.find((trip) => trip.assignment)?.assignment?.id ?? "",
  );
  const selectedAssignmentTrip = trips.find(
    (trip) => trip.assignment?.id === Number(selectedAssignmentId),
  );
  const remainingRisk = num(scenario?.delta_summary.remainingViolations, 0);
  const warningRisk = runSummaryNum(latestRun, "constraintSummary", "warning");
  const changedTripCount = runSummaryNum(latestRun, "projectionSummary", "changedTripCount");
  const maxDelay = runSummaryNum(latestRun, "projectionSummary", "maxDelayMinutes")
    || num(scenario?.delta_summary.delayDeltaMinutes, 0);
  const demurrageDelta = runSummaryNum(latestRun, "ogvSummary", "demurrageDeltaUsd")
    || valueNum(scenario?.delta_summary.demurrageDeltaUsd, 0);
  const utilizationDelta = runSummaryNum(
    latestRun,
    "utilizationSummary",
    "averageUtilizationDeltaPct",
  ) || valueNum(scenario?.delta_summary.fleetUtilizationPct, 0);
  const timelineStyle = (startValue: string, endValue: string) => {
    const start = new Date(startValue).getTime();
    const end = new Date(endValue).getTime();
    const left = Math.max(0, ((start - timelineStart) / timelineSpan) * 100);
    const width = Math.max(3, ((end - start) / timelineSpan) * 100);
    return { marginLeft: `${left}%`, width: `${Math.min(width, 100 - left)}%` };
  };
  const sourceLabel = scenario?.source_kind === "conflict"
    ? scenario.source_conflict_code ?? "Conflict"
    : scenario?.source_kind === "override"
      ? short(scenario.source_override_reason_code)
      : scenario?.source_kind === "tracking_alert"
        ? String(
          (scenario.metadata.source as Record<string, unknown> | undefined)?.trackingAlertRef
            ?? "Tracking alert",
        )
        : "Manual";
  const scenarioLocked = scenario?.status === "proposed" || scenario?.status === "canceled";

  useEffect(() => {
    if (!scenario || scenario.id === hydratedScenarioId) return;
    const seededAssumption = scenario.assumptions[0];
    setHydratedScenarioId(scenario.id);
    if (!seededAssumption) return;

    setAssumptionKind(seededAssumption.kind);
    if (seededAssumption.kind === "trip_delay") {
      setTripId(String(seededAssumption.scope_id ?? ""));
      setDelayMinutes(String(valueNum(seededAssumption.payload.delay_minutes, 0)));
    }
  }, [hydratedScenarioId, scenario]);

  function createAssumption() {
    if (!scenario || !onCreateAssumption) return;
    let draft: ScenarioAssumptionDraft;

    switch (assumptionKind) {
      case "asset_outage":
        draft = {
          kind: assumptionKind,
          scope_type: selectedAssumptionOption.scopeType,
          scope_id: null,
          payload: { asset_code: assetCode.trim() },
          effective_from: effectiveFrom ? new Date(effectiveFrom).toISOString() : null,
          effective_to: effectiveTo ? new Date(effectiveTo).toISOString() : null,
        };
        break;
      case "rate_change":
        draft = {
          kind: assumptionKind,
          scope_type: selectedAssumptionOption.scopeType,
          scope_id: null,
          payload: {
            asset_code: assetCode.trim(),
            rate_tph: Number(rateTph),
          },
          effective_from: effectiveFrom ? new Date(effectiveFrom).toISOString() : null,
          effective_to: effectiveTo ? new Date(effectiveTo).toISOString() : null,
        };
        break;
      case "window_change":
        draft = {
          kind: assumptionKind,
          scope_type: selectedAssumptionOption.scopeType,
          scope_id: null,
          payload: { window_code: windowCode.trim() },
          effective_from: effectiveFrom ? new Date(effectiveFrom).toISOString() : null,
          effective_to: effectiveTo ? new Date(effectiveTo).toISOString() : null,
        };
        break;
      case "ogv_eta_change":
        draft = {
          kind: assumptionKind,
          scope_type: selectedAssumptionOption.scopeType,
          scope_id: selectedTrip?.voyage.id ?? null,
          payload: { eta: ogvEta ? new Date(ogvEta).toISOString() : "" },
        };
        break;
      case "manual_reassignment":
        draft = {
          kind: assumptionKind,
          scope_type: selectedAssumptionOption.scopeType,
          scope_id: Number(selectedAssignmentId) || null,
          payload: {
            assignment_id: Number(selectedAssignmentId) || null,
            tug_code: replacementTug.trim(),
            barge_code: replacementBarge.trim(),
          },
        };
        break;
      case "trip_delay":
      default:
        draft = {
          kind: "trip_delay",
          scope_type: "trip",
          scope_id: Number(selectedTripId) || null,
          payload: { delay_minutes: Number(delayMinutes) },
        };
        break;
    }

    onCreateAssumption(scenario.id, draft);
  }

  return (
    <section className="workspace-page recovery-board simulation-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Recovery Loop / Simulation Workspace</p>
          <h1>Simulation Workspace</h1>
        </div>
        <div className="planning-actions">
          <span className="phase-chip">Scenario delta</span>
          <button
            disabled={!canEdit || !scenario || scenarioLocked || !onRunSimulation || isActionRunning}
            onClick={() => onRunSimulation?.(scenario?.id)}
            title={!canEdit ? "Your role cannot run simulations." : undefined}
            type="button"
          >
            Run simulation
          </button>
          <button
            disabled={
              !canEdit
              || !scenario
              || scenarioLocked
              || !latestRun
              || latestRun.status !== "succeeded"
              || !onPromoteScenario
              || isActionRunning
            }
            onClick={() => onPromoteScenario?.(scenario?.id, latestRun?.id)}
            title={!canEdit ? "Your role cannot promote scenarios." : undefined}
            type="button"
          >
            Promote to proposed
          </button>
        </div>
      </header>

      <div className="metric-strip five-up recovery-kpis">
        <div><span>Active scenario</span><strong>{scenario?.scenario_id ?? "NONE"}</strong></div>
        <div><span>Selected run</span><strong>{latestRun?.run_id ?? "NO RUN"}</strong></div>
        <div><span>Changed trips</span><strong className={changedTripCount ? "warning-text" : "success-text"}>{changedTripCount}</strong></div>
        <div><span>Max delay</span><strong className={maxDelay ? "warning-text" : "success-text"}>{signedMinutes(maxDelay)}</strong></div>
        <div><span>Risk flags</span><strong className={remainingRisk ? "critical-text" : warningRisk ? "warning-text" : "success-text"}>{remainingRisk}/{warningRisk}</strong></div>
      </div>

      <div className="simulation-layout">
        <aside className="board-surface scenario-config">
          <div className="grid-header">
            <div><SvgIcon name="settings" /><strong>Scenario configuration</strong></div>
          </div>
          <section className="scenario-create-panel">
            <label>
              New scenario
              <input
                onChange={(event) => setManualScenarioName(event.target.value)}
                placeholder="Manual what-if name"
                value={manualScenarioName}
              />
            </label>
            <button
              disabled={!canEdit || !onCreateScenario || isActionRunning}
              onClick={() => onCreateScenario?.({
                kind: "manual",
                name: manualScenarioName.trim() || undefined,
              })}
              type="button"
            >
              Create manual
            </button>
          </section>

          <section className="scenario-list-panel">
            <h2>Scenarios</h2>
            {scenarios.length ? scenarios.map((item) => (
              <button
                className={scenario?.id === item.id ? "active" : ""}
                key={item.id}
                onClick={() => {
                  setSelectedScenarioId(item.id);
                  setSelectedRunId(null);
                  setSelectedConstraintId(null);
                }}
                type="button"
              >
                <strong>{item.scenario_id}</strong>
                <span>{short(item.source_kind)} / {short(item.status)}</span>
              </button>
            )) : <span>No scenarios yet</span>}
          </section>

          <dl>
            <div><dt>Scenario name</dt><dd>{scenario?.name ?? "No scenario"}</dd></div>
            <div><dt>Scenario type</dt><dd>{short(scenario?.scenario_type)}</dd></div>
            <div><dt>Source</dt><dd>{sourceLabel}</dd></div>
            <div><dt>Status</dt><dd>{short(scenario?.status)}</dd></div>
          </dl>

          <section className="scenario-assumption-panel">
            <h2>Assumption editor</h2>
            <label>
              Kind
              <select
                onChange={(event) => setAssumptionKind(event.target.value)}
                value={assumptionKind}
              >
                {ASSUMPTION_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>

            {assumptionKind === "trip_delay" ? (
              <>
                <label>
                  Trip
                  <select onChange={(event) => setTripId(event.target.value)} value={selectedTripId}>
                    {trips.map((trip) => (
                      <option key={trip.id} value={trip.id}>{trip.trip_id}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Delay minutes
                  <input
                    min="0"
                    onChange={(event) => setDelayMinutes(event.target.value)}
                    type="number"
                    value={delayMinutes}
                  />
                </label>
              </>
            ) : null}

            {assumptionKind === "asset_outage" || assumptionKind === "rate_change" ? (
              <label>
                Asset code
                <input
                  onChange={(event) => setAssetCode(event.target.value)}
                  placeholder="BER-TUG-08"
                  value={assetCode}
                />
              </label>
            ) : null}

            {assumptionKind === "rate_change" ? (
              <label>
                Rate TPH
                <input
                  min="1"
                  onChange={(event) => setRateTph(event.target.value)}
                  type="number"
                  value={rateTph}
                />
              </label>
            ) : null}

            {assumptionKind === "window_change" ? (
              <label>
                Window code
                <input
                  onChange={(event) => setWindowCode(event.target.value)}
                  placeholder="TIDE-OPERATING-01"
                  value={windowCode}
                />
              </label>
            ) : null}

            {["asset_outage", "rate_change", "window_change"].includes(assumptionKind) ? (
              <>
                <label>
                  Effective from
                  <input
                    onChange={(event) => setEffectiveFrom(event.target.value)}
                    type="datetime-local"
                    value={effectiveFrom}
                  />
                </label>
                <label>
                  Effective to
                  <input
                    onChange={(event) => setEffectiveTo(event.target.value)}
                    type="datetime-local"
                    value={effectiveTo}
                  />
                </label>
              </>
            ) : null}

            {assumptionKind === "ogv_eta_change" ? (
              <>
                <label>
                  OGV
                  <select onChange={(event) => setTripId(event.target.value)} value={selectedTripId}>
                    {trips.map((trip) => (
                      <option key={trip.id} value={trip.id}>{trip.voyage.vessel_name}</option>
                    ))}
                  </select>
                </label>
                <label>
                  New ETA
                  <input
                    onChange={(event) => setOgvEta(event.target.value)}
                    type="datetime-local"
                    value={ogvEta}
                  />
                </label>
              </>
            ) : null}

            {assumptionKind === "manual_reassignment" ? (
              <>
                <label>
                  Assignment
                  <select
                    onChange={(event) => setAssignmentId(event.target.value)}
                    value={selectedAssignmentId}
                  >
                    {trips.filter((trip) => trip.assignment).map((trip) => (
                      <option key={trip.assignment?.id} value={trip.assignment?.id}>
                        {trip.trip_id}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Tug code
                  <input
                    onChange={(event) => setReplacementTug(event.target.value)}
                    placeholder={selectedAssignmentTrip?.assignment?.tug?.code ?? "BER-TUG-08"}
                    value={replacementTug}
                  />
                </label>
                <label>
                  Barge code
                  <input
                    onChange={(event) => setReplacementBarge(event.target.value)}
                    placeholder={selectedAssignmentTrip?.assignment?.barge?.code ?? "BRG-VAL-08"}
                    value={replacementBarge}
                  />
                </label>
              </>
            ) : null}

            <button
              disabled={
                !canEdit
                || !scenario
                || scenarioLocked
                || !onCreateAssumption
                || isActionRunning
              }
              onClick={createAssumption}
              type="button"
            >
              Add assumption
            </button>
          </section>

          <section className="scenario-assumption-list">
            <h2>Assumptions</h2>
            {assumptions.length ? assumptions.map((assumption) => (
              <span key={assumption.id}>
                <strong>{short(assumption.kind)}</strong>
                <em>{assumptionSummary(assumption)}</em>
              </span>
            )) : <span>No assumptions configured</span>}
          </section>
        </aside>

        <section className="board-surface simulation-main">
          <div className="grid-header">
            <div><SvgIcon name="schedule" /><strong>Baseline vs scenario output</strong></div>
            <span>{latestRun ? "Selected run projection" : "Run a scenario to calculate projections"}</span>
          </div>
          <section className="scenario-summary-strip">
            <span><strong>{money(demurrageDelta)}</strong><em>Demurrage delta</em></span>
            <span><strong>{signedMinutes(maxDelay)}</strong><em>Max trip delta</em></span>
            <span><strong>{utilizationDelta.toFixed(2)}%</strong><em>Avg utilization delta</em></span>
            <span><strong>{constraints.length}</strong><em>Constraint evaluations</em></span>
          </section>
          <div className="grid-scroll scenario-comparison-grid">
            <table className="planning-table logistics-table">
              <thead>
                <tr>
                  <th>#</th><th>OGV / Grade-Hatch</th><th>Chain</th>
                  <th>Baseline Start</th><th>Sim Start</th><th>Baseline Completion</th>
                  <th>Sim Completion</th><th>Delta</th>
                </tr>
              </thead>
              <tbody>
                {visibleComparisonRows.map(({ trip, projection }) => (
                  <tr key={trip.id}>
                    <td>{String(trip.sequence).padStart(2, "0")}</td>
                    <td><strong>{trip.voyage.vessel_name}</strong><br />{trip.cargo_layer_step?.coal_grade.code ?? "-"}</td>
                    <td>
                      {trip.origin_jetty?.code ?? "UNASSIGNED"}<br />
                      {assignmentChain(projection, trip, "baseline")}
                      {projection?.assignment_delta.resourceChanged ? (
                        <>
                          <br />
                          <span className="warning-text">
                            {"-> "}{assignmentChain(projection, trip, "projected")}
                          </span>
                        </>
                      ) : null}
                    </td>
                    <td><GridDate value={projection?.baseline_start ?? trip.planned_start} /></td>
                    <td className={projectionChanged(projection) ? "warning-text" : "success-text"}>
                      <GridDate value={projection?.projected_start ?? trip.planned_start} />
                    </td>
                    <td><GridDate value={projection?.baseline_end ?? trip.planned_end} /></td>
                    <td className={projectionChanged(projection) ? "warning-text" : "success-text"}>
                      <GridDate value={projection?.projected_end ?? trip.planned_end} />
                    </td>
                    <td className={projection?.delay_minutes ? "warning-text" : "success-text"}>
                      {signedMinutes(projection?.delay_minutes ?? 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <section className="scenario-timeline computed">
            <div className="grid-header">
              <div><SvgIcon name="account-tree" /><strong>Projected event timeline</strong></div>
              <span>Baseline lane above scenario lane</span>
            </div>
            {timelineRows.length ? timelineRows.map(({ trip, projection }) => (
              <div className="scenario-row computed" key={trip.id}>
                <strong>{trip.trip_id}</strong>
                <div className="scenario-lanes">
                  <span
                    className="scenario-bar baseline"
                    style={timelineStyle(
                      projection?.baseline_start ?? trip.planned_start,
                      projection?.baseline_end ?? trip.planned_end,
                    )}
                  >
                    BASE
                  </span>
                  <span
                    className={`scenario-bar ${projectionChanged(projection) ? "pending" : "ok"}`}
                    style={timelineStyle(
                      projection?.projected_start ?? trip.planned_start,
                      projection?.projected_end ?? trip.planned_end,
                    )}
                  >
                    {projectionChanged(projection) ? signedMinutes(projection?.delay_minutes ?? 0) : "NO DELTA"}
                  </span>
                </div>
              </div>
            )) : (
              <div className="scenario-empty">No projected timeline yet</div>
            )}
          </section>

          <section className="scenario-result-grid">
            <div className="scenario-result-panel">
              <div className="grid-header">
                <div><SvgIcon name="rule" /><strong>Constraint evaluations</strong></div>
                <span>Cause, target, margin</span>
              </div>
              <div className="grid-scroll compact">
                <table className="planning-table logistics-table">
                  <thead>
                    <tr><th>Severity</th><th>Code</th><th>Target</th><th>Margin</th></tr>
                  </thead>
                  <tbody>
                    {constraints.slice(0, 8).map((item) => (
                      <tr
                        className={selectedConstraint?.id === item.id ? "selected-row" : ""}
                        key={item.id}
                        onClick={() => setSelectedConstraintId(item.id)}
                      >
                        <td><span className={`status-chip ${constraintTone(item.severity)}`}>{short(item.severity)}</span></td>
                        <td>{item.code}</td>
                        <td>{item.affected_object_id || item.trip_ref || item.affected_object_type}</td>
                        <td>{item.margin_minutes === null ? "-" : signedMinutes(item.margin_minutes)}</td>
                      </tr>
                    ))}
                    {!constraints.length ? (
                      <tr><td colSpan={4}>No constraint evaluations yet</td></tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="scenario-result-panel">
              <div className="grid-header">
                <div><SvgIcon name="schedule" /><strong>OGV completion & demurrage</strong></div>
                <span>Completion risk by voyage</span>
              </div>
              <div className="scenario-mini-list">
                {ogvProjections.slice(0, 5).map((item) => (
                  <span key={item.id}>
                    <strong>{item.vessel_name}</strong>
                    <em>{signedMinutes(item.completion_delta_minutes)} / {money(item.demurrage_delta_usd)}</em>
                    <small className={`${constraintTone(item.risk_status)}-text`}>{short(item.risk_status)}</small>
                  </span>
                ))}
                {!ogvProjections.length ? <span>No OGV projections yet</span> : null}
              </div>
            </div>

            <div className="scenario-result-panel">
              <div className="grid-header">
                <div><SvgIcon name="settings" /><strong>Asset utilization</strong></div>
                <span>Occupied, waiting, idle delta</span>
              </div>
              <div className="scenario-mini-list">
                {utilizationRows.slice(0, 6).map((item) => (
                  <span key={item.id}>
                    <strong>{short(item.resource_type)} / {item.resource_code}</strong>
                    <em>{valueNum(item.utilization_delta_pct).toFixed(2)}% util delta</em>
                    <small>{item.waiting_minutes}m waiting</small>
                  </span>
                ))}
                {!utilizationRows.length ? <span>No utilization results yet</span> : null}
              </div>
            </div>
          </section>
        </section>

        <aside className="board-surface logistics-inspector">
          <div className="grid-header">
            <div><SvgIcon name="audit" /><strong>Run drill-down</strong></div>
          </div>
          <div className="inspector-body">
            <section className="scenario-run-list">
              <strong>Run queue</strong>
              {scenario?.runs.length ? scenario.runs.slice(0, 4).map((run) => (
                <button
                  className={latestRun?.id === run.id ? "active" : ""}
                  key={run.id}
                  onClick={() => {
                    setSelectedRunId(run.id);
                    setSelectedConstraintId(null);
                  }}
                  type="button"
                >
                  <em className={`status-chip ${statusTone(run.status)}`}>{short(run.status)}</em>
                  <b>{run.run_id}</b>
                  <small>{run.completed_at ? dt(run.completed_at) : dt(run.created_at)}</small>
                </button>
              )) : <p>No scenario runs yet.</p>}
            </section>
            <section className="scenario-detail-block">
              <strong>Selected constraint</strong>
              {selectedConstraint ? (
                <>
                  <span className={`status-chip ${constraintTone(selectedConstraint.severity)}`}>
                    {short(selectedConstraint.severity)}
                  </span>
                  <h2>{selectedConstraint.code}</h2>
                  <p>{selectedConstraint.message}</p>
                  <dl>
                    <div>
                      <dt>Target</dt>
                      <dd>
                        {selectedConstraint.affected_object_id
                          || selectedConstraint.trip_ref
                          || selectedConstraint.affected_object_type}
                      </dd>
                    </div>
                    <div>
                      <dt>Margin</dt>
                      <dd>
                        {selectedConstraint.margin_minutes === null
                          ? "No margin"
                          : signedMinutes(selectedConstraint.margin_minutes)}
                      </dd>
                    </div>
                    <div>
                      <dt>Source</dt>
                      <dd>{sourceAssumptionText(selectedConstraint)}</dd>
                    </div>
                  </dl>
                </>
              ) : (
                <p>No constraint selected.</p>
              )}
            </section>
            <section className="scenario-detail-block">
              <strong>Calculated impact chain</strong>
              {selectedImpactNodes.length ? (
                <div className="impact-chain-track compact">
                  {selectedImpactNodes.map((node, index) => (
                    <Fragment key={node.id}>
                      <span className={`chain-node ${constraintTone(node.status)}`}>
                        <strong>{node.label}</strong>
                        <em>{node.value}</em>
                        <small>{node.detail}</small>
                      </span>
                      {index < selectedImpactNodes.length - 1 ? <i className="chain-line" /> : null}
                    </Fragment>
                  ))}
                </div>
              ) : (
                <p>Impact not calculated for this run.</p>
              )}
            </section>
            <section className="scenario-detail-block">
              <strong>Recovery actions</strong>
              <ul className="validation-list">
                {(scenario?.recovery_actions ?? []).map((action) => <li key={action}>{action}</li>)}
                {!scenario?.recovery_actions.length ? <li>No recovery actions proposed.</li> : null}
              </ul>
            </section>
            <section className="recovery-box">
              <strong>Next step</strong>
              <p>
                {remainingRisk
                  ? "Resolve projected critical constraints before promotion."
                  : "Promote to proposed plan, then request dual-party approval."}
              </p>
            </section>
            <button
              disabled={!canEdit || !overview?.activePlanVersion || !onSubmitApproval || isActionRunning}
              onClick={onSubmitApproval}
              type="button"
            >
              Submit approval request
            </button>
            {latestRun ? (
              <p className="scenario-run-note">
                Latest run {latestRun.run_id} used input hash {latestRun.input_hash.slice(0, 12)}.
              </p>
            ) : null}
          </div>
        </aside>
      </div>
    </section>
  );
}

export function ApprovalsPublishingPage({
  overview,
  canEdit = false,
  isActionRunning = false,
  onApprove,
  onPublish,
  onReject,
  canPublish = false,
}: RecoveryPageProps) {
  const requests = overview?.approvalRequests ?? EMPTY_APPROVALS;
  const snapshots = overview?.publishedSnapshots ?? [];
  const conflicts = overview?.conflicts ?? EMPTY_CONFLICTS;
  const request = requests[0];
  const readyToPublish =
    request?.status === "approved" && (overview?.validation.blockingConflictCount ?? 0) === 0;

  return (
    <section className="workspace-page recovery-board approvals-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Schedule / Plan Approvals</p>
          <h1>Plan Approvals & Publishing</h1>
        </div>
        <div className="planning-actions">
          <span className={`phase-chip ${readyToPublish ? "secure" : ""}`}>
            {readyToPublish ? "Ready to publish" : "Publish blocked"}
          </span>
          <button
            disabled={!canPublish || !readyToPublish || !onPublish || isActionRunning}
            onClick={onPublish}
            type="button"
          >
            Publish plan
          </button>
        </div>
      </header>

        <div className="metric-strip seven-up recovery-kpis">
        <div><span>Pending approvals</span><strong>{requests.filter((item) => item.status === "pending").length}</strong></div>
        <div><span>Critical</span><strong className="critical-text">{overview?.validation.criticalConflictCount ?? 0}</strong></div>
        <div><span>Overrides</span><strong className="warning-text">{overview?.validation.overrideCount ?? 0}</strong></div>
        <div><span>Simulation promos</span><strong>{overview?.validation.scenarioCount ?? 0}</strong></div>
        <div><span>Ready to publish</span><strong className={readyToPublish ? "success-text" : "critical-text"}>{readyToPublish ? "YES" : "BLOCKED"}</strong></div>
        <div><span>Published version</span><strong>{snapshots[0]?.snapshot_id ?? "NONE"}</strong></div>
        <div><span>Plan state</span><strong>{short(overview?.activePlanVersion?.status)}</strong></div>
      </div>

      <div className="approval-layout">
        <section className="board-surface recovery-grid-panel">
          <div className="grid-header">
            <div><SvgIcon name="audit" /><strong>Pending approval queue</strong></div>
            <span>Request · source · affected plan · impact · required authority</span>
          </div>
          <div className="grid-scroll">
            <table className="planning-table logistics-table">
              <thead>
                <tr>
                  <th>Status</th><th>Raised</th><th>ID</th><th>Source</th>
                  <th>Requested change</th><th>Impact</th><th>Req. approvals</th>
                </tr>
              </thead>
              <tbody>
                {requests.map((item) => {
                  const itemCoverage = approvalCoverage(item);
                  return (
                    <tr className={request?.id === item.id ? "selected-row" : ""} key={item.id}>
                      <td><span className={`status-chip ${statusTone(item.status)}`}>{short(item.status)}</span></td>
                      <td><GridDate value={item.created_at} /></td>
                      <td>{item.request_id}</td>
                      <td>{item.scenario_lineage?.scenarioId ?? item.plan_version_ref}</td>
                      <td>{item.reason}</td>
                      <td>{overview?.validation.blockingConflictCount ? "Blocking conflicts remain" : "Validation clear"}</td>
                      <td>{itemCoverage.approved}/{itemCoverage.required}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="board-surface logistics-inspector approval-inspector">
          <div className="grid-header">
            <div><SvgIcon name="rule" /><strong>Approval detail</strong></div>
            <span>{request?.request_id ?? "No request"}</span>
          </div>
          {request ? (
            <div className="inspector-body">
              <span className={`status-chip ${statusTone(request.status)}`}>{short(request.status)}</span>
              <h2>{request.request_id}</h2>
              <p>{request.reason}</p>
              {request.scenario_lineage ? (
                <section className="recovery-box scenario-lineage-box">
                  <strong>Scenario source</strong>
                  <dl>
                    <div><dt>Scenario</dt><dd>{request.scenario_lineage.scenarioId}</dd></div>
                    <div><dt>Run</dt><dd>{request.scenario_lineage.selectedRunRef}</dd></div>
                    <div><dt>Baseline</dt><dd>{request.scenario_lineage.baselineVersionRef}</dd></div>
                    <div><dt>Assumptions</dt><dd>{request.scenario_lineage.assumptionIds.length}</dd></div>
                    <div><dt>Changed trips</dt><dd>{request.scenario_diff_summary?.changedTripCount ?? 0}</dd></div>
                    <div><dt>Aggregate delay</dt><dd>{signedMinutes(request.scenario_diff_summary?.delayDeltaMinutes ?? 0)}</dd></div>
                  </dl>
                </section>
              ) : null}
              <section className="recovery-box">
                <strong>Constraint checklist</strong>
                <ul className="validation-list">
                  <li>{conflicts.some((conflict) => conflict.code.includes("TIDE")) ? "!" : "✓"} Tide window compatibility</li>
                  <li>{conflicts.some((conflict) => conflict.code.includes("BRIDGE")) ? "!" : "✓"} Bridge clearance slot</li>
                  <li>{overview?.validation.blockingConflictCount ? "!" : "✓"} No blocking conflicts</li>
                </ul>
              </section>
              <section className="approval-chain">
                <strong>Approval chain</strong>
                {request.required_authorities.map((authority) => {
                  const decision = request.decisions.find((item) => item.authority_role === authority);
                  return (
                    <span className={decision ? "complete" : ""} key={authority}>
                      <i />{short(authority)}<em>{decision ? short(decision.decision) : "AWAITING ACTION"}</em>
                    </span>
                  );
                })}
              </section>
              <div className="approval-actions">
                <button
                  disabled={!canEdit || request.status !== "pending" || !onApprove || isActionRunning}
                  onClick={onApprove}
                  type="button"
                >
                  Approve
                </button>
                <button
                  disabled={!canEdit || request.status !== "pending" || !onReject || isActionRunning}
                  onClick={onReject}
                  type="button"
                >
                  Reject
                </button>
                <button
                  disabled={!canPublish || !readyToPublish || !onPublish || isActionRunning}
                  onClick={onPublish}
                  type="button"
                >
                  Publish
                </button>
              </div>
            </div>
          ) : null}
        </aside>
      </div>
    </section>
  );
}
