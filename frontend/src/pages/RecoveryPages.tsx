import { useState } from "react";

import { SvgIcon } from "../components/SvgIcon";
import type {
  ApprovalRequestRecord,
  ConflictRecord,
  SchedulingOverview,
  SimulationScenarioRecord,
  TripRecord,
} from "../types";

type RecoveryPageProps = {
  overview: SchedulingOverview | null;
  canEdit?: boolean;
  isActionRunning?: boolean;
  onApprove?: () => void;
  onPublish?: () => void;
  onReject?: () => void;
  canPublish?: boolean;
};

const EMPTY_CONFLICTS: ConflictRecord[] = [];
const EMPTY_TRIPS: TripRecord[] = [];
const EMPTY_APPROVALS: ApprovalRequestRecord[] = [];
const EMPTY_SCENARIOS: SimulationScenarioRecord[] = [];

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
  if (!value) return "—";
  return new Date(value).toLocaleString(undefined, {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
  });
}

function num(value: unknown, fallback = 0) {
  return typeof value === "number" ? value : fallback;
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

export function ExceptionCenterPage({ overview, canEdit = false }: RecoveryPageProps) {
  const conflicts = overview?.conflicts ?? EMPTY_CONFLICTS;
  const trips = overview?.trips ?? EMPTY_TRIPS;
  const scenarios = overview?.simulationScenarios ?? EMPTY_SCENARIOS;
  const [selectedId, setSelectedId] = useState<number | null>(conflicts[0]?.id ?? null);
  const selectedConflict = selectedConflictFor(conflicts, selectedId);
  const selectedTrip = trips.find((trip) => trip.id === selectedConflict?.trip);
  const critical = conflicts.filter((conflict) => conflict.severity === "critical").length;
  const warning = conflicts.filter((conflict) => conflict.severity === "warning").length;
  const pending = conflicts.filter((conflict) => conflict.is_blocking).length;
  const resolved = conflicts.filter((conflict) => conflict.resolved_at).length;

  return (
    <section className="workspace-page recovery-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Recovery Loop / Exception Center</p>
          <h1>Exception Center</h1>
        </div>
        <div className="planning-actions">
          <span className="phase-chip">Chunk 5 · Active triage</span>
          <button
            disabled
            title={canEdit
              ? "Scenario conversion is locked until governed adjustment capture."
              : "Your role cannot convert exceptions to scenarios."}
            type="button"
          >
            Scenario locked
          </button>
          <button disabled title="Triage publishing is outside Phase 1 action scope." type="button">
            Publish triage locked
          </button>
        </div>
      </header>

      <div className="metric-strip six-up recovery-kpis">
        <div><span>Active</span><strong>{conflicts.length}</strong></div>
        <div><span>Critical</span><strong className="critical-text">{critical}</strong></div>
        <div><span>Warning</span><strong className="warning-text">{warning}</strong></div>
        <div><span>Pending</span><strong>{pending}</strong></div>
        <div><span>Sim candidate</span><strong>{scenarios.length}</strong></div>
        <div><span>Resolved</span><strong className="success-text">{resolved}</strong></div>
      </div>

      <div className="exception-layout">
        <aside className="board-surface recovery-filter-rail">
          <div className="grid-header">
            <div><SvgIcon name="rule" /><strong>Triage filters</strong></div>
          </div>
          <section>
            <h2>Severity</h2>
            <span>Critical ({critical})</span>
            <span>Warning ({warning})</span>
            <span>Blocking ({pending})</span>
          </section>
          <section>
            <h2>OGV focus</h2>
            {trips.slice(0, 4).map((trip) => (
              <button key={trip.id} type="button">{trip.voyage.vessel_name}</button>
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
                {conflicts.map((conflict) => (
                  <tr
                    className={selectedConflict?.id === conflict.id ? "selected-row" : ""}
                    key={conflict.id}
                    onClick={() => setSelectedId(conflict.id)}
                  >
                    <td><span className={`status-chip ${statusTone(conflict.severity, conflict.is_blocking)}`}>{short(conflict.severity)}</span></td>
                    <td>{dt(conflict.created_at)}</td>
                    <td>EX-{String(conflict.id).padStart(4, "0")}</td>
                    <td>{conflict.code}</td>
                    <td>{conflict.vessel_name ?? "Network"}</td>
                    <td>{conflict.object_id || conflict.object_type || "N/A"}</td>
                    <td>{conflict.is_blocking ? "+5h delay risk" : "Watch"}</td>
                    <td>{conflict.resolved_at ? "RESOLVED" : "ACTIVE"}</td>
                    <td>{conflict.is_blocking ? "SIM" : "MONITOR"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="board-surface logistics-inspector recovery-inspector">
          <div className="grid-header">
            <div><SvgIcon name="account-tree" /><strong>Exception detail</strong></div>
            <span>{selectedConflict ? `EX-${selectedConflict.id}` : "No exception"}</span>
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
          ) : null}
        </aside>
      </div>

      <section className="board-surface impact-chain">
        <div className="grid-header">
          <div><SvgIcon name="account-tree" /><strong>Impact chain propagation</strong></div>
          <span>Source event → logistics inferred → system projected → final risk target</span>
        </div>
        <div>
          <span className="chain-node critical">Source event<br />{selectedConflict?.code ?? "None"}</span>
          <span className="chain-line" />
          <span className="chain-node pending">Logistics inferred<br />Barge delay (+2h)</span>
          <span className="chain-line" />
          <span className="chain-node pending">System projected<br />Tide window risk</span>
          <span className="chain-line" />
          <span className="chain-node">Final risk target<br />{selectedConflict?.vessel_name ?? "Network"}</span>
        </div>
      </section>
    </section>
  );
}

export function SimulationWorkspacePage({ overview, canEdit = false }: RecoveryPageProps) {
  const scenarios = overview?.simulationScenarios ?? EMPTY_SCENARIOS;
  const trips = overview?.trips ?? EMPTY_TRIPS;
  const scenario = scenarios[0];
  const remainingRisk = num(scenario?.delta_summary.remainingViolations, 0);

  return (
    <section className="workspace-page recovery-board simulation-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Recovery Loop / Simulation Workspace</p>
          <h1>Simulation Workspace</h1>
        </div>
        <div className="planning-actions">
          <span className="phase-chip">Chunk 5 · Scenario delta</span>
          <button
            disabled
            title={canEdit ? "Simulation execution is read-only in this Phase 1 cockpit." : "Your role cannot run simulations."}
            type="button"
          >
            Run simulation locked
          </button>
          <button
            disabled
            title={canEdit ? "Promotion is locked until governed adjustment capture." : "Your role cannot promote scenarios."}
            type="button"
          >
            Promote locked
          </button>
        </div>
      </header>

      <div className="metric-strip five-up recovery-kpis">
        <div><span>Active scenario</span><strong>{scenario?.scenario_id ?? "NONE"}</strong></div>
        <div><span>Feasibility</span><strong className="success-text">{num(scenario?.impact_summary.feasibilityPct, 0)}%</strong></div>
        <div><span>OGV delay</span><strong className="success-text">{num(scenario?.delta_summary.delayDeltaMinutes, 0)}m</strong></div>
        <div><span>Demurrage risk</span><strong>{num(scenario?.delta_summary.demurrageDeltaUsd, 0).toLocaleString()}</strong></div>
        <div><span>Violations</span><strong className={remainingRisk ? "warning-text" : "success-text"}>{remainingRisk}</strong></div>
      </div>

      <div className="simulation-layout">
        <aside className="board-surface scenario-config">
          <div className="grid-header">
            <div><SvgIcon name="settings" /><strong>Scenario configuration</strong></div>
          </div>
          <dl>
            <div><dt>Scenario name</dt><dd>{scenario?.name ?? "No scenario"}</dd></div>
            <div><dt>Scenario type</dt><dd>{short(scenario?.scenario_type)}</dd></div>
            <div><dt>Source conflict</dt><dd>{scenario?.source_conflict_code ?? "Manual"}</dd></div>
            <div><dt>Status</dt><dd>{short(scenario?.status)}</dd></div>
          </dl>
          <button
            disabled
            title={canEdit ? "Simulation execution is read-only in this Phase 1 cockpit." : "Your role cannot run simulations."}
            type="button"
          >
            Run simulation locked
          </button>
        </aside>

        <section className="board-surface simulation-main">
          <div className="grid-header">
            <div><SvgIcon name="schedule" /><strong>Baseline vs scenario output</strong></div>
            <span>Scenario output remains recommended state until approval promotion</span>
          </div>
          <div className="grid-scroll">
            <table className="planning-table logistics-table">
              <thead>
                <tr>
                  <th>#</th><th>OGV / Grade-Hatch</th><th>Jetty</th><th>Tug / Barge</th>
                  <th>CTS</th><th>Baseline Start</th><th>Sim Start</th><th>Baseline Completion</th><th>Sim Completion</th>
                </tr>
              </thead>
              <tbody>
                {trips.slice(0, 6).map((trip) => (
                  <tr key={trip.id}>
                    <td>{String(trip.sequence).padStart(2, "0")}</td>
                    <td><strong>{trip.voyage.vessel_name}</strong><br />{trip.cargo_layer_step?.coal_grade.code ?? "-"}</td>
                    <td>{trip.origin_jetty?.code ?? "UNASSIGNED"}</td>
                    <td>{trip.assignment?.tug?.code ?? "NONE"} / {trip.assignment?.barge?.code ?? "NONE"}</td>
                    <td>{trip.assignment?.cts?.code ?? "NONE"}</td>
                    <td>{dt(trip.planned_start)}</td>
                    <td className="success-text">{dt(trip.planned_start)}</td>
                    <td>{dt(trip.planned_end)}</td>
                    <td className={trip.status === "blocked" ? "critical-text" : "success-text"}>{dt(trip.planned_end)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <section className="scenario-timeline">
            <div className="grid-header">
              <div><SvgIcon name="account-tree" /><strong>Scenario impact timeline</strong></div>
              <span>Baseline, outage, reassignment, queue, CTS feed</span>
            </div>
            {["OGV", "TUG", "BARGE", "CTS", "TIDE WINDOW"].map((label, index) => (
              <div className="scenario-row" key={label}>
                <strong>{label}</strong>
                <span
                  className={`scenario-bar ${index === 1 ? "critical" : index === 4 ? "pending" : "ok"}`}
                  style={{ marginLeft: `${10 + index * 5}%`, width: `${34 + index * 5}%` }}
                >
                  {index === 1 ? "OUT OF SERVICE — UNAVAILABLE" : "RECOVERY WINDOW"}
                </span>
              </div>
            ))}
          </section>
        </section>

        <aside className="board-surface logistics-inspector">
          <div className="grid-header">
            <div><SvgIcon name="audit" /><strong>Approval workflow</strong></div>
          </div>
          <div className="inspector-body">
            <span className="status-chip pending">{short(scenario?.status)}</span>
            <h2>Recovery actions</h2>
            <ul className="validation-list">
              {(scenario?.recovery_actions ?? []).map((action) => <li key={action}>✓ {action}</li>)}
            </ul>
            <section className="recovery-box">
              <strong>Next step</strong>
              <p>Promote to proposed plan, then request dual-party approval.</p>
            </section>
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
                      <td>{dt(item.created_at)}</td>
                      <td>{item.request_id}</td>
                      <td>{item.plan_version_ref}</td>
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
