import { useMemo, useState } from "react";

import { SvgIcon } from "../components/SvgIcon";
import type {
  AssignmentRecord,
  ConflictRecord,
  SchedulingOverview,
  TripRecord,
} from "../types";

type LogisticsPageProps = {
  overview: SchedulingOverview | null;
  canEdit?: boolean;
};

const EMPTY_ASSIGNMENTS: AssignmentRecord[] = [];
const EMPTY_TRIPS: TripRecord[] = [];
const EMPTY_CONFLICTS: ConflictRecord[] = [];

function mt(value: number) {
  return `${Math.round(value).toLocaleString()} MT`;
}

function dt(value: string | null | undefined) {
  if (!value) return "-";
  return new Date(value).toLocaleString(undefined, {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
  });
}

function statusTone(status: string | undefined, blocking = false) {
  if (blocking || status === "blocked" || status === "maintenance") return "critical";
  if (
    status === "waiting_tide"
    || status === "waiting_bridge"
    || status === "warning"
    || status === "delayed"
  ) {
    return "pending";
  }
  return "ok";
}

function shortStatus(status: string) {
  return status.replaceAll("_", " ").toUpperCase();
}

function progressFor(trip: TripRecord) {
  if (!trip.planned_quantity_mt) return 0;
  return Math.min(100, Math.round((trip.loaded_quantity_mt / trip.planned_quantity_mt) * 100));
}

function conflictForTrip(conflicts: ConflictRecord[], tripId: number | null | undefined) {
  return conflicts.find((conflict) => conflict.trip === tripId && conflict.is_blocking)
    ?? conflicts.find((conflict) => conflict.trip === tripId);
}

function selectedTripFor(
  trips: TripRecord[],
  assignments: AssignmentRecord[],
  selectedAssignmentId: number | null,
) {
  const selectedAssignment = assignments.find((assignment) => assignment.id === selectedAssignmentId)
    ?? assignments[0];
  return trips.find((trip) => trip.id === selectedAssignment?.trip) ?? trips[0];
}

export function TugBargeAssignmentPage({ overview, canEdit = false }: LogisticsPageProps) {
  const assignments = overview?.assignments ?? EMPTY_ASSIGNMENTS;
  const trips = overview?.trips ?? EMPTY_TRIPS;
  const conflicts = overview?.conflicts ?? EMPTY_CONFLICTS;
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<number | null>(
    assignments[0]?.id ?? null,
  );
  const selectedTrip = selectedTripFor(trips, assignments, selectedAssignmentId);
  const selectedConflict = conflictForTrip(conflicts, selectedTrip?.id);
  const operationalCount = assignments.filter((item) => statusTone(item.status) === "ok").length;
  const delayedCount = assignments.filter((item) => statusTone(item.status) === "pending").length;
  const blockedCount = assignments.filter((item) => statusTone(item.status) === "critical").length;

  return (
    <section className="workspace-page logistics-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Operations / Tug-Barge Assignment</p>
          <h1>Tug/Barge Assignment</h1>
        </div>
        <div className="planning-actions">
          <span className="phase-chip">Chunk 4 · Fleet feasibility</span>
          <button disabled={!canEdit} type="button">Regenerate plan</button>
          <button type="button">Export chain</button>
        </div>
      </header>

      <div className="metric-strip four-up planning-kpis">
        <div><span>Operational</span><strong className="success-text">{operationalCount}</strong></div>
        <div><span>Delayed</span><strong className={delayedCount ? "warning-text" : ""}>{delayedCount}</strong></div>
        <div><span>Blocked</span><strong className={blockedCount ? "critical-text" : ""}>{blockedCount}</strong></div>
        <div><span>Plan version</span><strong>{overview?.activePlanVersion?.plan_code ?? "—"}</strong></div>
      </div>

      <div className="logistics-split">
        <section className="board-surface planning-grid-panel">
          <div className="grid-header">
            <div><SvgIcon name="fleet" /><strong>Fleet assignment console</strong></div>
            <span>Status · tug unit · barge unit · assigned OGV · next availability</span>
          </div>
          <div className="grid-scroll">
            <table className="planning-table logistics-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Tug Unit</th>
                  <th>Barge Unit</th>
                  <th>Location</th>
                  <th>Assigned OGV</th>
                  <th>Next Avail PLN</th>
                  <th>Next Avail PRD</th>
                  <th>Delay Reason</th>
                </tr>
              </thead>
              <tbody>
                {assignments.map((assignment) => {
                  const trip = trips.find((item) => item.id === assignment.trip);
                  const conflict = conflictForTrip(conflicts, assignment.trip);
                  return (
                    <tr
                      className={selectedAssignmentId === assignment.id ? "selected-row" : ""}
                      key={assignment.id}
                      onClick={() => setSelectedAssignmentId(assignment.id)}
                    >
                      <td><span className={`status-chip ${statusTone(assignment.status, conflict?.is_blocking)}`}>{shortStatus(assignment.status)}</span></td>
                      <td><strong>{assignment.tug?.name ?? "UNASSIGNED"}</strong></td>
                      <td>{assignment.barge?.code ?? "NONE"}</td>
                      <td>{assignment.route_segment ? `SEG-${assignment.route_segment}` : assignment.jetty?.code ?? "-"}</td>
                      <td>{assignment.vessel_name}</td>
                      <td>{dt(assignment.planned_arrival)}</td>
                      <td>{dt(trip?.planned_end)}</td>
                      <td>{conflict?.message || assignment.next_constraint || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="board-surface logistics-inspector">
          <div className="grid-header">
            <div><SvgIcon name="account-tree" /><strong>Selected chain</strong></div>
            <span>{selectedTrip?.trip_id ?? "No trip"}</span>
          </div>
          {selectedTrip ? (
            <div className="inspector-body">
              <span className={`status-chip ${statusTone(selectedTrip.status, selectedConflict?.is_blocking)}`}>
                {shortStatus(selectedTrip.status)}
              </span>
              <h2>{selectedTrip.voyage.vessel_name}</h2>
              <p>{selectedConflict?.message ?? selectedTrip.assignment?.next_action ?? "No blocker recorded."}</p>
              <dl>
                <div><dt>Tug</dt><dd>{selectedTrip.assignment?.tug?.code ?? "Unassigned"}</dd></div>
                <div><dt>Barge</dt><dd>{selectedTrip.assignment?.barge?.code ?? "Unassigned"}</dd></div>
                <div><dt>Jetty</dt><dd>{selectedTrip.assignment?.jetty?.code ?? "Unassigned"}</dd></div>
                <div><dt>CTS</dt><dd>{selectedTrip.assignment?.cts?.code ?? "Unassigned"}</dd></div>
              </dl>
            </div>
          ) : null}
        </aside>
      </div>

      <section className="board-surface mini-gantt-panel">
        <div className="grid-header">
          <div><SvgIcon name="schedule" /><strong>Assignment timeline</strong></div>
          <span>Planned chain view, resource-linked to trip IDs</span>
        </div>
        <div className="mini-gantt">
          {trips.map((trip, index) => (
            <div className="mini-gantt-row" key={trip.id}>
              <strong>{trip.assignment?.tug?.code ?? trip.trip_id}</strong>
              <div>
                <span
                  className={`gantt-pill ${statusTone(trip.status, conflictForTrip(conflicts, trip.id)?.is_blocking)}`}
                  style={{ marginLeft: `${(index % 5) * 8}%`, width: `${24 + progressFor(trip) / 3}%` }}
                >
                  {trip.trip_id} · {trip.voyage.vessel_name}
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </section>
  );
}

export function JettyLoadingPage({ overview, canEdit = false }: LogisticsPageProps) {
  const assignments = overview?.assignments ?? EMPTY_ASSIGNMENTS;
  const trips = overview?.trips ?? EMPTY_TRIPS;
  const conflicts = overview?.conflicts ?? EMPTY_CONFLICTS;
  const byJetty = useMemo(() => {
    const groups = new Map<string, AssignmentRecord[]>();
    assignments.forEach((assignment) => {
      const key = assignment.jetty?.code ?? "UNASSIGNED";
      groups.set(key, [...(groups.get(key) ?? []), assignment]);
    });
    return [...groups.entries()];
  }, [assignments]);

  return (
    <section className="workspace-page logistics-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Operations / Jetty Loading Plan</p>
          <h1>Jetty Loading</h1>
        </div>
        <div className="planning-actions">
          <span className="phase-chip">Chunk 4 · Source-side queue</span>
          <button disabled={!canEdit} type="button">Force start jetty</button>
          <button type="button">Export loading plan</button>
        </div>
      </header>

      <div className="jetty-layout">
        <section className="board-surface jetty-plan-panel">
          <div className="grid-header">
            <div><SvgIcon name="locations" /><strong>Jetty execution queue</strong></div>
            <span>OGV, grade, hatch/layer, tonnage, start/end, readiness, next constraint</span>
          </div>
          <div className="jetty-sections">
            {byJetty.map(([jettyCode, rows]) => (
              <section className="jetty-section" key={jettyCode}>
                <h2>{jettyCode}<span>{rows[0]?.jetty?.status?.toUpperCase() ?? "PLANNED"}</span></h2>
                <div className="jetty-row jetty-row-header">
                  <span>OGV</span><span>Grade</span><span>Hatch</span><span>Load MT</span>
                  <span>Progress</span><span>Start / End</span><span>Readiness</span><span>Next</span>
                </div>
                {rows.map((assignment) => {
                  const trip = trips.find((item) => item.id === assignment.trip);
                  const conflict = conflictForTrip(conflicts, assignment.trip);
                  return (
                    <div className="jetty-row" key={assignment.id}>
                      <strong>{assignment.vessel_name}</strong>
                      <span>{trip?.cargo_layer_step?.coal_grade.code ?? "-"}</span>
                      <span>H{trip?.cargo_layer_step?.hatch_no ?? "-"}-L{trip?.cargo_layer_step?.layer_no ?? "-"}</span>
                      <span>{mt(assignment.planned_quantity_mt)}</span>
                      <span><i style={{ width: `${trip ? progressFor(trip) : 0}%` }} /></span>
                      <span>{dt(trip?.planned_start)} / {dt(trip?.planned_end)}</span>
                      <span className={statusTone(assignment.status, conflict?.is_blocking)}>{trip ? `${progressFor(trip)}%` : "0%"}</span>
                      <span>{conflict?.code ?? assignment.next_action}</span>
                    </div>
                  );
                })}
              </section>
            ))}
          </div>
        </section>

        <aside className="board-surface logistics-inspector">
          <div className="grid-header">
            <div><SvgIcon name="rule" /><strong>Manual override panel</strong></div>
            <span>Reason capture lands in Chunk 5</span>
          </div>
          <div className="inspector-body">
            <span className="status-chip pending">Operator controlled</span>
            <h2>Jetty readiness</h2>
            <p>Loading queues are generated from trip assignments and current jetty availability windows.</p>
            <section className="recovery-box">
              <strong>Audit trail</strong>
              <p>Generated plan preserves source chain and conflict evidence for downstream approval.</p>
            </section>
          </div>
        </aside>
      </div>
    </section>
  );
}

export function CtsOperationsPage({ overview }: LogisticsPageProps) {
  const assignments = overview?.assignments ?? EMPTY_ASSIGNMENTS;
  const trips = overview?.trips ?? EMPTY_TRIPS;
  const conflicts = overview?.conflicts ?? EMPTY_CONFLICTS;
  const activeCts = new Set(assignments.map((assignment) => assignment.cts?.code).filter(Boolean)).size;
  const waitingQueue = assignments.filter((assignment) => assignment.status.includes("waiting")).length;
  const downtime = assignments.filter((assignment) => statusTone(assignment.status) === "critical").length;

  return (
    <section className="workspace-page logistics-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Operations / CTS Floating Crane</p>
          <h1>CTS / Floating Crane</h1>
        </div>
        <div className="planning-actions">
          <span className="phase-chip">Chunk 4 · Transshipment capacity</span>
          <button type="button">Export CTS queue</button>
        </div>
      </header>

      <div className="metric-strip four-up planning-kpis">
        <div><span>Active CTS</span><strong>{activeCts}</strong></div>
        <div><span>Avg discharge rate</span><strong>{Math.round((overview?.validation.loadedMt ?? 0) / Math.max(activeCts, 1)).toLocaleString()}</strong></div>
        <div><span>Barge queue</span><strong className={waitingQueue ? "warning-text" : ""}>{waitingQueue}</strong></div>
        <div><span>CTS downtime</span><strong className={downtime ? "critical-text" : ""}>{downtime}</strong></div>
      </div>

      <section className="board-surface planning-grid-panel cts-panel">
        <div className="grid-header">
          <div><SvgIcon name="operations" /><strong>CTS operations board</strong></div>
          <span>Current OGV, assigned barge, queue position, coal grade, hatch, release, rate, status</span>
        </div>
        <div className="grid-scroll">
          <table className="planning-table logistics-table">
            <thead>
              <tr>
                <th>CTS ID</th><th>Current OGV</th><th>Assigned Barge</th><th>Queue Pos</th>
                <th>Coal Grade</th><th>Hatch</th><th>Pred Release</th><th>Est Comp</th>
                <th>Rate</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {assignments.map((assignment, index) => {
                const trip = trips.find((item) => item.id === assignment.trip);
                const conflict = conflictForTrip(conflicts, assignment.trip);
                const rate = assignment.cts?.daily_capacity_mt
                  ? Math.round(assignment.cts.daily_capacity_mt / 18)
                  : 0;
                return (
                  <tr key={assignment.id}>
                    <td><strong>{assignment.cts?.code ?? "UNASSIGNED"}</strong></td>
                    <td>{assignment.vessel_name}</td>
                    <td>{assignment.barge?.code ?? "-"}</td>
                    <td>Q{index + 1}</td>
                    <td>{trip?.cargo_layer_step?.coal_grade.code ?? "-"}</td>
                    <td>H{trip?.cargo_layer_step?.hatch_no ?? "-"}/L{trip?.cargo_layer_step?.layer_no ?? "-"}</td>
                    <td>{dt(assignment.planned_arrival)}</td>
                    <td>{dt(trip?.planned_end)}</td>
                    <td>{rate.toLocaleString()} MT/H</td>
                    <td><span className={`status-chip ${statusTone(assignment.status, conflict?.is_blocking)}`}>{shortStatus(assignment.status)}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}

export function PublishedPlanPage({ overview }: LogisticsPageProps) {
  const trips = overview?.trips ?? EMPTY_TRIPS;
  const conflicts = overview?.conflicts ?? EMPTY_CONFLICTS;
  const activeVersion = overview?.activePlanVersion;
  const selectedTrip = trips.find((trip) => conflictForTrip(conflicts, trip.id)?.is_blocking) ?? trips[0];
  const selectedConflict = conflictForTrip(conflicts, selectedTrip?.id);

  return (
    <section className="workspace-page logistics-board published-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Schedule / Published Plan & Schedule</p>
          <h1>Published Plan & Schedule</h1>
        </div>
        <div className="planning-actions">
          <span className={`phase-chip ${activeVersion?.validation_status === "feasible" ? "secure" : ""}`}>
            {activeVersion?.plan_code ?? "No version"} · V{activeVersion?.version_no ?? "—"}
          </span>
          <button type="button">Create replan candidate</button>
        </div>
      </header>

      <div className="published-layout">
        <section className="board-surface schedule-gantt-panel">
          <div className="grid-header">
            <div><SvgIcon name="schedule" /><strong>Operating schedule gantt</strong></div>
            <span>Resource hierarchy · planned chain · blocking variance</span>
          </div>
          <div className="schedule-gantt">
            <aside>
              <strong>Resource hierarchy</strong>
              {trips.map((trip) => <span key={trip.id}>{trip.voyage.vessel_name}</span>)}
              <strong>Jetties</strong>
              {trips.map((trip) => <span key={`j-${trip.id}`}>{trip.origin_jetty?.code ?? "UNASSIGNED"}</span>)}
              <strong>Logistics</strong>
              {trips.map((trip) => <span key={`l-${trip.id}`}>{trip.assignment?.barge?.code ?? trip.trip_id}</span>)}
              <strong>Constraints</strong>
              <span>Tide Window</span>
              <span>Bridge Gate</span>
            </aside>
            <div className="gantt-canvas">
              <div className="gantt-time-header">
                <span>24 OCT 04:00</span><span>08:00</span><span>12:00</span>
                <span>16:00</span><span>20:00</span><span>25 OCT 00:00</span>
              </div>
              <div className="now-marker" />
              {trips.map((trip, index) => {
                const conflict = conflictForTrip(conflicts, trip.id);
                return (
                  <div className="gantt-resource-row" key={trip.id}>
                    <span
                      className={`gantt-block ${statusTone(trip.status, conflict?.is_blocking)}`}
                      style={{ left: `${10 + (index % 5) * 12}%`, width: `${18 + progressFor(trip) / 4}%` }}
                    >
                      {trip.trip_id}: {shortStatus(trip.status)}
                    </span>
                    {conflict ? <em>{conflict.code}</em> : null}
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <aside className="board-surface logistics-inspector">
          <div className="grid-header">
            <div><SvgIcon name="rule" /><strong>Plan item detail</strong></div>
            <span>{selectedTrip?.trip_id ?? "No item"}</span>
          </div>
          {selectedTrip ? (
            <div className="inspector-body">
              <span className={`status-chip ${statusTone(selectedTrip.status, selectedConflict?.is_blocking)}`}>
                {selectedConflict?.severity ?? selectedTrip.status}
              </span>
              <h2>{selectedTrip.trip_id}</h2>
              <p>{selectedTrip.voyage.vessel_name}</p>
              <dl>
                <div><dt>Jetty</dt><dd>{selectedTrip.origin_jetty?.code ?? "Unassigned"}</dd></div>
                <div><dt>Tug</dt><dd>{selectedTrip.assignment?.tug?.code ?? "Unassigned"}</dd></div>
                <div><dt>Barge</dt><dd>{selectedTrip.assignment?.barge?.code ?? "Unassigned"}</dd></div>
                <div><dt>CTS</dt><dd>{selectedTrip.assignment?.cts?.code ?? "Unassigned"}</dd></div>
              </dl>
              <section className="recovery-box">
                <strong>Conflict center MVP</strong>
                <p>{selectedConflict?.message ?? "No active conflict on this trip."}</p>
              </section>
            </div>
          ) : null}
        </aside>
      </div>
    </section>
  );
}
