import { useMemo, useState } from "react";

import { Abbr } from "../components/Abbreviation";
import { GridDate } from "../components/GridDate";
import { SvgIcon } from "../components/SvgIcon";
import {
  DisabledReasonTooltip,
  RecommendationCard,
  type AssistantRecommendationSurfaceProps,
} from "../components/assistant";
import { cargoLayerChainStatusLabel } from "../lib/cargoLayer";
import { activePlanConflicts, activeTrackingAlerts, primaryConflict } from "../lib/planStatus";
import type {
  CargoLayerStepRecord,
  ConflictRecord,
  OGVVoyageRecord,
  PlanningOverview,
  SchedulingOverview,
  TrackingAlertRecord,
} from "../types";

type OgvDemandPageProps = AssistantRecommendationSurfaceProps & {
  overview: PlanningOverview | null;
  schedulingOverview?: SchedulingOverview | null;
  canEdit: boolean;
  canExport: boolean;
  isActionRunning: boolean;
  onExportBoard: () => void;
  onImportDemand: () => void;
};

function mt(value: number) {
  return `${Math.round(value).toLocaleString()} MT`;
}

function riskTone(voyage: OGVVoyageRecord) {
  if (voyage.risk_status === "demurrage") return "critical";
  if (voyage.risk_status === "high") return "critical";
  if (voyage.risk_status === "medium") return "pending";
  return "ok";
}

function baseRiskLabel(voyage: OGVVoyageRecord) {
  if (voyage.risk_status === "demurrage") return "high";
  return voyage.risk_status.replace("_", " ");
}

function conflictReason(conflict: ConflictRecord) {
  if (conflict.message) return conflict.message;
  if (conflict.code === "TIDE_WINDOW_MISSED") return "Tide window needs recovery.";
  if (conflict.code === "BRIDGE_WINDOW_MISSED") return "Bridge window needs recovery.";
  if (conflict.code === "LAYER_SEQUENCE_VIOLATION") return "Coal grade sequence needs review.";
  return "Plan exception needs review.";
}

function alertReason(alert: TrackingAlertRecord) {
  if (alert.message) return alert.message;
  if (alert.alert_type === "delay") return "Live tracking delay needs review.";
  if (alert.alert_type === "eta_risk") return "Live ETA variance needs review.";
  return "Live tracking alert needs review.";
}

function effectiveRisk(
  voyage: OGVVoyageRecord,
  conflicts: ConflictRecord[] = [],
  alerts: TrackingAlertRecord[] = [],
) {
  const conflict = primaryConflict(conflicts);
  const alert = alerts.find((item) => item.severity === "critical") ?? alerts[0];
  if (conflict?.is_blocking || conflict?.severity === "critical") {
    return { label: "high", tone: "critical", reason: conflictReason(conflict) };
  }
  if (alert?.severity === "critical") {
    return { label: "high", tone: "critical", reason: alertReason(alert) };
  }
  if (conflict) {
    return { label: "medium", tone: "pending", reason: conflictReason(conflict) };
  }
  if (alert) {
    return { label: "medium", tone: "pending", reason: alertReason(alert) };
  }
  return {
    label: baseRiskLabel(voyage),
    tone: riskTone(voyage),
    reason: voyage.next_blocking_constraint || "Clear",
  };
}

function stageLabel(step: CargoLayerStepRecord) {
  return `H${step.hatch_no}/L${step.layer_no} ${step.coal_grade.code}`;
}

export function OgvDemandPage({
  assistantBlockedActions,
  assistantChecklist,
  assistantFlow,
  assistantPageActions,
  assistantRowActions,
  overview,
  schedulingOverview,
  canEdit,
  canExport,
  isActionRunning,
  onAssistantNavigate,
  onExportBoard,
  onImportDemand,
}: OgvDemandPageProps) {
  const voyages = overview?.voyages ?? [];
  const activeConflicts = useMemo(
    () => activePlanConflicts(schedulingOverview?.conflicts),
    [schedulingOverview?.conflicts],
  );
  const openTrackingAlerts = useMemo(
    () => activeTrackingAlerts(schedulingOverview?.trackingAlerts),
    [schedulingOverview?.trackingAlerts],
  );
  const tripsById = useMemo(
    () => new Map((schedulingOverview?.trips ?? []).map((trip) => [trip.id, trip])),
    [schedulingOverview?.trips],
  );
  const conflictsByVoyageId = useMemo(() => {
    const rows = new Map<number, ConflictRecord[]>();
    activeConflicts.forEach((conflict) => {
      const voyageId = conflict.trip ? tripsById.get(conflict.trip)?.voyage.id : undefined;
      if (!voyageId) return;
      rows.set(voyageId, [...(rows.get(voyageId) ?? []), conflict]);
    });
    return rows;
  }, [activeConflicts, tripsById]);
  const trackingAlertsByVoyageId = useMemo(() => {
    const rows = new Map<number, TrackingAlertRecord[]>();
    openTrackingAlerts.forEach((alert) => {
      const voyageId = alert.trip ? tripsById.get(alert.trip)?.voyage.id : undefined;
      if (!voyageId) return;
      rows.set(voyageId, [...(rows.get(voyageId) ?? []), alert]);
    });
    return rows;
  }, [openTrackingAlerts, tripsById]);
  const riskByVoyageId = useMemo(() => new Map(
    voyages.map((voyage) => [
      voyage.id,
      effectiveRisk(
        voyage,
        conflictsByVoyageId.get(voyage.id) ?? [],
        trackingAlertsByVoyageId.get(voyage.id) ?? [],
      ),
    ]),
  ), [conflictsByVoyageId, trackingAlertsByVoyageId, voyages]);
  const [selectedVoyageId, setSelectedVoyageId] = useState<number | null>(voyages[0]?.id ?? null);
  const selectedVoyage = voyages.find((voyage) => voyage.id === selectedVoyageId) ?? voyages[0];
  const selectedSteps = useMemo(
    () =>
      overview?.cargoLayerSteps
        .filter((step) => step.voyage === selectedVoyage?.id)
        .sort((left, right) => left.required_sequence_no - right.required_sequence_no) ?? [],
    [overview?.cargoLayerSteps, selectedVoyage?.id],
  );
  const selectedRequirements = useMemo(
    () => overview?.cargoRequirements.filter((item) => item.voyage === selectedVoyage?.id) ?? [],
    [overview?.cargoRequirements, selectedVoyage?.id],
  );
  const totalRequired = overview?.validation.activeDemandMt ?? 0;
  const totalRemaining = overview?.validation.remainingDemandMt ?? 0;
  const highRiskCount = voyages.filter((voyage) => (
    riskByVoyageId.get(voyage.id)?.tone === "critical"
  )).length;
  const readyCount = voyages.filter((voyage) => (
    riskByVoyageId.get(voyage.id)?.tone === "ok"
  )).length;
  const assistantActions = [
    ...(assistantRowActions ?? []),
    ...(assistantPageActions ?? []),
    ...(assistantBlockedActions ?? []),
  ];

  return (
    <section className="workspace-page planning-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Schedule / <Abbr term="OGV">OGV</Abbr> Demand Board</p>
          <h1><Abbr term="OGV">OGV</Abbr> Demand & Laycan</h1>
        </div>
        <div className="planning-actions">
          <span className="phase-chip">Demand intake</span>
          <DisabledReasonTooltip
            actionId="IMPORT_OGV_DEMAND"
            actions={assistantActions}
            fallback={!canEdit ? "Your role cannot import OGV demand." : ""}
          >
            <button disabled={!canEdit || isActionRunning} onClick={onImportDemand} type="button">
              Import demand
            </button>
          </DisabledReasonTooltip>
          <DisabledReasonTooltip
            actionId="GENERATE_EXPORT"
            actions={assistantActions}
            fallback={!canExport ? "Your role cannot generate exports." : ""}
          >
            <button disabled={!canExport || isActionRunning} onClick={onExportBoard} type="button">
              Export board
            </button>
          </DisabledReasonTooltip>
        </div>
      </header>
      <RecommendationCard
        assistantBlockedActions={assistantBlockedActions}
        assistantChecklist={assistantChecklist}
        assistantFlow={assistantFlow}
        assistantPageActions={assistantPageActions}
        assistantRowActions={assistantRowActions}
        onAssistantNavigate={onAssistantNavigate}
      />

      <div className="metric-strip six-up planning-kpis">
        <div>
          <span>Active voyages</span>
          <strong>{voyages.length.toString().padStart(2, "0")}</strong>
        </div>
        <div>
          <span>Demand</span>
          <strong>{mt(totalRequired)}</strong>
        </div>
        <div>
          <span>Remaining</span>
          <strong>{mt(totalRemaining)}</strong>
        </div>
        <div>
          <span>Ready</span>
          <strong className="success-text">{readyCount}</strong>
        </div>
        <div>
          <span>High risk</span>
          <strong className={highRiskCount ? "critical-text" : ""}>{highRiskCount}</strong>
        </div>
        <div>
          <span>Import jobs</span>
          <strong>{overview?.importJobs.length ?? 0}</strong>
        </div>
      </div>

      <div className="planning-demand-layout">
        <section className="board-surface planning-grid-panel">
          <div className="grid-header">
            <div>
              <SvgIcon name="schedule" />
              <strong>Laycan demand cockpit</strong>
            </div>
            <span>Excel replacement · structured voyage, quantity, grade, and blocker state</span>
          </div>
          <div className="filter-strip planning-filters">
            <span>All OGVs</span>
            <span>Laycan ± 7D</span>
            <span>Berau + ABL shared</span>
            <span>Risk-first sort</span>
          </div>
          <div className="grid-scroll">
            <table className="planning-table demand-table">
              <thead>
                <tr>
                  <th><Abbr term="OGV">OGV</Abbr> Name</th>
                  <th>Customer</th>
                  <th>Laycan Start</th>
                  <th>Laycan End</th>
                  <th><Abbr term="ETA">ETA</Abbr> / <Abbr term="ETB">ETB</Abbr> / <Abbr term="ETC">ETC</Abbr></th>
                  <th>Required</th>
                  <th>Loaded</th>
                  <th>In-Transit</th>
                  <th>Discharged</th>
                  <th>Remaining</th>
                  <th>Grade / Stage</th>
                  <th>Next Blocking Constraint</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody>
                {voyages.map((voyage) => {
                  const risk = riskByVoyageId.get(voyage.id) ?? effectiveRisk(voyage);
                  return (
                    <tr
                      className={selectedVoyage?.id === voyage.id ? "selected-row" : ""}
                      key={voyage.id}
                      onClick={() => setSelectedVoyageId(voyage.id)}
                    >
                      <td><strong>{voyage.vessel_name}</strong></td>
                      <td>{voyage.customer_name}</td>
                      <td><GridDate value={voyage.laycan_start} /></td>
                      <td><GridDate value={voyage.laycan_end} /></td>
                      <td>
                        <span className="grid-date-stack">
                          <GridDate value={voyage.eta} />
                          <span className="grid-date-separator">/</span>
                          <GridDate value={voyage.etb} />
                          <span className="grid-date-separator">/</span>
                          <GridDate value={voyage.etc_target} />
                        </span>
                      </td>
                      <td>{mt(voyage.required_mt)}</td>
                      <td>{mt(voyage.loaded_mt)}</td>
                      <td>{mt(voyage.in_transit_mt)}</td>
                      <td>{mt(voyage.discharged_mt)}</td>
                      <td>{mt(voyage.remaining_mt)}</td>
                      <td>{voyage.current_stage || "-"}</td>
                      <td>{risk.reason}</td>
                      <td>
                        <span className={`status-chip ${risk.tone}`}>
                          {risk.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="board-surface risk-engine-rail">
          <div className="grid-header">
            <div>
              <SvgIcon name="rule" />
              <strong>Real-time risk engine</strong>
            </div>
            <span>Manual rule checks until optimizer services arrive</span>
          </div>
          <ol className="risk-list">
            {voyages
              .filter((voyage) => riskByVoyageId.get(voyage.id)?.tone !== "ok")
              .map((voyage) => {
                const risk = riskByVoyageId.get(voyage.id) ?? effectiveRisk(voyage);
                return (
                  <li key={voyage.id}>
                    <span className={`dot ${risk.tone}`} />
                    <div>
                      <strong>{voyage.vessel_name}</strong>
                      <p>{risk.reason}</p>
                    </div>
                  </li>
                );
              })}
          </ol>
          <section className="import-review">
            <strong>Import validation</strong>
            {overview?.importJobs.slice(0, 3).map((job) => (
              <div key={job.id}>
                <span>{job.filename}</span>
                <em>{job.valid_rows}/{job.total_rows} valid</em>
              </div>
            ))}
          </section>
        </aside>
      </div>

      {selectedVoyage ? (
        <section className="board-surface voyage-detail-panel">
          <div className="grid-header">
            <div>
              <SvgIcon name="account-tree" />
              <strong>Vessel planning detail · {selectedVoyage.vessel_name}</strong>
            </div>
            <span>{selectedVoyage.voyage_id} · {selectedVoyage.status.toUpperCase()}</span>
          </div>
          <div className="voyage-detail-grid">
            <div>
              <h2>Cargo requirement split</h2>
              <ul className="compact-list">
                {selectedRequirements.map((requirement) => (
                  <li key={requirement.id}>
                    <strong>{requirement.coal_grade.code}</strong>
                    <span>{mt(requirement.required_mt)} required</span>
                    <em>{mt(requirement.remaining_mt)} remaining</em>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h2>Hatch / layer chain</h2>
              <ol className="hatch-sequence-strip">
                {selectedSteps.map((step) => (
                  <li
                    className={step.sequence_violation ? "violated" : step.status}
                    key={step.id}
                  >
                    <span>{step.required_sequence_no}</span>
                    <strong>{stageLabel(step)}</strong>
                    <em>{cargoLayerChainStatusLabel(step)}</em>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>
      ) : null}
    </section>
  );
}
