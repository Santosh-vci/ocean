import { useMemo, useState } from "react";

import { GridDate } from "../components/GridDate";
import { SvgIcon } from "../components/SvgIcon";
import type { CargoLayerStepRecord, PlanningOverview } from "../types";

type CoalGradeSequencePageProps = {
  overview: PlanningOverview | null;
  canEdit: boolean;
  canExport: boolean;
  isActionRunning: boolean;
  onExport: () => void;
};

const EMPTY_STEPS: CargoLayerStepRecord[] = [];

function mt(value: number) {
  return `${Math.round(value).toLocaleString()} MT`;
}

function time(value: string | null) {
  return <GridDate value={value} />;
}

function severity(step: CargoLayerStepRecord) {
  if (step.sequence_violation) return "critical";
  if (step.status === "blocked" || step.status === "qc_hold") return "pending";
  return "ok";
}

export function CoalGradeSequencePage({
  overview,
  canEdit,
  canExport,
  isActionRunning,
  onExport,
}: CoalGradeSequencePageProps) {
  const steps = overview?.cargoLayerSteps ?? EMPTY_STEPS;
  const [selectedStepId, setSelectedStepId] = useState<number | null>(steps[0]?.id ?? null);
  const selectedStep = steps.find((step) => step.id === selectedStepId) ?? steps[0];
  const selectedVoyageSteps = useMemo(
    () =>
      steps
        .filter((step) => step.voyage === selectedStep?.voyage)
        .sort((left, right) => left.required_sequence_no - right.required_sequence_no),
    [selectedStep?.voyage, steps],
  );
  const voyagesInSequence = new Set(steps.map((step) => step.voyage)).size;
  const gradeConflicts = steps.filter((step) => step.sequence_violation).length;
  const atRiskBarges = steps.filter((step) => step.status === "blocked").length;
  const reworkRisk = gradeConflicts + atRiskBarges;

  return (
    <section className="workspace-page planning-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Schedule / Coal Grade Sequence</p>
          <h1>Coal Grade Sequence</h1>
        </div>
        <div className="planning-actions">
          <span className="phase-chip">Grade layering</span>
          <button
            disabled
            title={canEdit
              ? "Direct sequence editing is locked for Phase 1 governed planning."
              : "Your role cannot edit coal grade sequence."}
            type="button"
          >
            Edit sequence locked
          </button>
          <button disabled={!canExport || isActionRunning} onClick={onExport} type="button">
            Export QC view
          </button>
        </div>
      </header>

      <div className="metric-strip six-up planning-kpis">
        <div>
          <span>OGVs in sequence</span>
          <strong>{voyagesInSequence}</strong>
        </div>
        <div>
          <span>Grade conflicts</span>
          <strong className={gradeConflicts ? "critical-text" : ""}>{gradeConflicts}</strong>
        </div>
        <div>
          <span>Layer violations</span>
          <strong className={gradeConflicts ? "critical-text" : ""}>{gradeConflicts}</strong>
        </div>
        <div>
          <span>At-risk barges</span>
          <strong className={atRiskBarges ? "warning-text" : ""}>{atRiskBarges}</strong>
        </div>
        <div>
          <span>Rework risk</span>
          <strong className={reworkRisk ? "warning-text" : ""}>{reworkRisk}</strong>
        </div>
        <div>
          <span>Plan state</span>
          <strong>DRAFT</strong>
        </div>
      </div>

      <div className="sequence-layout">
        <section className="board-surface planning-grid-panel">
          <div className="grid-header">
            <div>
              <SvgIcon name="coal" />
              <strong>Sequence queue</strong>
            </div>
            <span>Hatch, layer, jetty, CTS, and blocking reason in one operational grid</span>
          </div>
          <div className="grid-scroll">
            <table className="planning-table sequence-table">
              <thead>
                <tr>
                  <th>Sev</th>
                  <th>OGV</th>
                  <th>Hatch/L</th>
                  <th>Grade</th>
                  <th>Req MT</th>
                  <th>Remain</th>
                  <th>Blocking Reason</th>
                  <th>Jetty</th>
                  <th>CTS</th>
                  <th>Chain Status</th>
                  <th>Window</th>
                </tr>
              </thead>
              <tbody>
                {steps.map((step) => (
                  <tr
                    className={selectedStep?.id === step.id ? "selected-row" : ""}
                    key={step.id}
                    onClick={() => setSelectedStepId(step.id)}
                  >
                    <td><span className={`status-chip ${severity(step)}`}>{severity(step)}</span></td>
                    <td><strong>{step.vessel_name}</strong></td>
                    <td>H{step.hatch_no}/L{step.layer_no}</td>
                    <td>{step.coal_grade.code}</td>
                    <td>{mt(step.required_mt)}</td>
                    <td>{mt(step.remaining_mt)}</td>
                    <td>{step.blocking_reason || "Clear"}</td>
                    <td>{step.planned_jetty?.code ?? "-"}</td>
                    <td>{step.planned_cts?.code ?? "-"}</td>
                    <td>{step.chain_status || step.status.toUpperCase()}</td>
                    <td>
                      <span className="grid-date-pair">
                        {time(step.planned_start)}
                        <span className="grid-date-separator">→</span>
                        {time(step.planned_end)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="board-surface sequence-inspector">
          <div className="grid-header">
            <div>
              <SvgIcon name="rule" />
              <strong>Sequence violation</strong>
            </div>
            <span>Recommended recovery and approvals</span>
          </div>
          {selectedStep ? (
            <div className="inspector-body">
              <span className={`status-chip ${severity(selectedStep)}`}>
                {selectedStep.sequence_violation ? "Violation" : selectedStep.status}
              </span>
              <h2>{selectedStep.vessel_name} · H{selectedStep.hatch_no}/L{selectedStep.layer_no}</h2>
              <p>{selectedStep.blocking_reason || "No blocking reason recorded for this layer."}</p>
              <dl>
                <div>
                  <dt>Grade</dt>
                  <dd>{selectedStep.coal_grade.code}</dd>
                </div>
                <div>
                  <dt>Barge</dt>
                  <dd>{selectedStep.planned_barge?.code ?? "Unassigned"}</dd>
                </div>
                <div>
                  <dt>Jetty</dt>
                  <dd>{selectedStep.planned_jetty?.code ?? "Unassigned"}</dd>
                </div>
                <div>
                  <dt>CTS</dt>
                  <dd>{selectedStep.planned_cts?.code ?? "Unassigned"}</dd>
                </div>
              </dl>
              <section className="recovery-box">
                <strong>Recommended recovery</strong>
                <p>
                  Hold publication until the grade sequence is confirmed against hatch layering
                  and bridge/tide availability.
                </p>
              </section>
            </div>
          ) : null}
        </aside>
      </div>

      <section className="board-surface focus-sequence">
        <div className="grid-header">
          <div>
            <SvgIcon name="account-tree" />
            <strong>Focus view · {selectedStep?.vessel_name ?? "No OGV selected"}</strong>
          </div>
          <span>Sequence-strip parity with hardened frontend reference</span>
        </div>
        <ol className="sequence-strip">
          {selectedVoyageSteps.map((step) => (
            <li className={severity(step)} key={step.id}>
              <span>{step.required_sequence_no}</span>
              <strong>H{step.hatch_no}/L{step.layer_no}</strong>
              <em>{step.coal_grade.code}</em>
            </li>
          ))}
        </ol>
      </section>
    </section>
  );
}
