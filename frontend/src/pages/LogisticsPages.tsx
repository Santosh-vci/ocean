import { FormEvent, useEffect, useMemo, useState } from "react";

import { Abbr, AbbrText } from "../components/Abbreviation";
import { GridDate } from "../components/GridDate";
import { SvgIcon } from "../components/SvgIcon";
import {
  DisabledReasonTooltip,
  RecommendationCard,
  RowActionHint,
  type ActionRecommendation,
  type AssistantRecommendationSurfaceProps,
} from "../components/assistant";
import { formatGridDateLabel } from "../lib/gridDate";
import {
  confirmedEventForCandidate,
  CTS_EVENT_KINDS,
  JETTY_EVENT_KINDS,
  latestCandidate,
  latestConfirmedEvent,
  operationalVarianceLabel,
  operationalVarianceMinutes,
  shortOperationalLabel,
} from "../lib/operations";
import { activeConflictForTrip, activePlanConflicts } from "../lib/planStatus";
import type {
  AssignmentRecord,
  ConfirmedOperationalEventRecord,
  ConflictRecord,
  DeviceEndpointRecord,
  OperationalEventCandidateRecord,
  SchedulingOverview,
  TripRecord,
} from "../types";

type LogisticsPageProps = AssistantRecommendationSurfaceProps & {
  overview: SchedulingOverview | null;
  canEdit?: boolean;
  canCreateDraft?: boolean;
  canExport?: boolean;
  isActionRunning?: boolean;
  onCreateDraft?: () => void;
  onExport?: () => void;
  onForceStartJetty?: (assignmentId: number, actualStartAt: string) => void | Promise<void>;
  onConfirmOperationalEvent?: (
    candidateId: number,
    actualAt: string,
    reasonCode: string,
  ) => void | Promise<void>;
  onRejectOperationalEvent?: (
    candidateId: number,
    reasonCode: string,
    notes: string,
  ) => void | Promise<void>;
  onRegenerate?: () => void;
  onSubmitApproval?: () => void;
  operationCandidates?: OperationalEventCandidateRecord[];
  confirmedOperationalEvents?: ConfirmedOperationalEventRecord[];
  operationDevices?: DeviceEndpointRecord[];
  canConfirmJetty?: boolean;
  canConfirmCts?: boolean;
};

const EMPTY_ASSIGNMENTS: AssignmentRecord[] = [];
const EMPTY_TRIPS: TripRecord[] = [];
const EMPTY_CONFLICTS: ConflictRecord[] = [];
const EMPTY_CANDIDATES: OperationalEventCandidateRecord[] = [];
const EMPTY_CONFIRMED_EVENTS: ConfirmedOperationalEventRecord[] = [];
const EMPTY_DEVICES: DeviceEndpointRecord[] = [];
const GANTT_TICK_COUNT = 6;

function mt(value: number) {
  return `${Math.round(value).toLocaleString()} MT`;
}

function dt(value: string | null | undefined) {
  return <GridDate value={value} />;
}

function dtText(value: string | null | undefined) {
  return formatGridDateLabel(value);
}

function datetimeLocalValue(value: string | null | undefined, offsetMinutes = 0) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  date.setMinutes(date.getMinutes() + offsetMinutes);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function toIsoFromLocal(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString();
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

function validTime(value: string) {
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? null : timestamp;
}

function ganttRange(trips: TripRecord[]) {
  const times = trips.flatMap((trip) => [
    validTime(trip.planned_start),
    validTime(trip.planned_end),
  ]).filter((value): value is number => value !== null);
  const start = times.length ? Math.min(...times) : Date.now();
  const end = Math.max(times.length ? Math.max(...times) : start + 60 * 60 * 1000, start + 60 * 60 * 1000);
  const span = end - start;
  const ticks = Array.from({ length: GANTT_TICK_COUNT }, (_, index) => (
    start + (span * index) / (GANTT_TICK_COUNT - 1)
  ));

  return { start, end, span, ticks };
}

function ganttTickLabel(timestamp: number, index: number, ticks: number[]) {
  const date = new Date(timestamp);
  const previous = index > 0 ? new Date(ticks[index - 1]) : null;
  const showDate = !previous
    || date.getDate() !== previous.getDate()
    || date.getMonth() !== previous.getMonth()
    || date.getFullYear() !== previous.getFullYear();
  const day = String(date.getDate()).padStart(2, "0");
  const month = date.toLocaleString("en-US", { month: "short" }).toUpperCase();
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");

  return showDate ? `${day} ${month} ${hour}:${minute}` : `${hour}:${minute}`;
}

function ganttPosition(timestamp: number, range: ReturnType<typeof ganttRange>) {
  return Math.max(0, Math.min(100, ((timestamp - range.start) / range.span) * 100));
}

function ganttBlockStyle(trip: TripRecord, range: ReturnType<typeof ganttRange>) {
  const start = validTime(trip.planned_start) ?? range.start;
  const end = validTime(trip.planned_end) ?? start;
  const left = ganttPosition(start, range);
  const width = Math.max(2, Math.min(100 - left, ((Math.max(end, start) - start) / range.span) * 100));

  return { left: `${left}%`, width: `${width}%` };
}

function conflictForTrip(conflicts: ConflictRecord[], tripId: number | null | undefined) {
  return activeConflictForTrip(conflicts, tripId);
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

function eventFor(trip: TripRecord | undefined, eventType: string) {
  return trip?.events.find((event) => event.event_type === eventType);
}

function deviceFor(devices: DeviceEndpointRecord[], assetCode: string | null | undefined) {
  return devices.find((device) => device.asset_code === assetCode) ?? null;
}

function deviceHealthLabel(device: DeviceEndpointRecord | null) {
  return shortOperationalLabel(device?.latest_health?.healthStatus ?? device?.status);
}

function operationalTone(status: string | null | undefined) {
  if (status === "confirmed" || status === "auto_confirmed" || status === "healthy" || status === "active") {
    return "ok";
  }
  if (status === "rejected" || status === "offline" || status === "critical") return "critical";
  return "pending";
}

function CandidateReviewPanel({
  assistantActions = [],
  candidate,
  confirmedEvent,
  canConfirm,
  isActionRunning,
  onAssistantNavigate,
  onConfirm,
  onReject,
}: {
  assistantActions?: ActionRecommendation[];
  candidate: OperationalEventCandidateRecord | null;
  confirmedEvent: ConfirmedOperationalEventRecord | null;
  canConfirm: boolean;
  isActionRunning: boolean;
  onAssistantNavigate?: LogisticsPageProps["onAssistantNavigate"];
  onConfirm?: LogisticsPageProps["onConfirmOperationalEvent"];
  onReject?: LogisticsPageProps["onRejectOperationalEvent"];
}) {
  const [confirmReason, setConfirmReason] = useState("operator_verified");
  const [rejectReason, setRejectReason] = useState("manual_reject");
  const [rejectNotes, setRejectNotes] = useState("");

  useEffect(() => {
    setConfirmReason("operator_verified");
    setRejectReason("manual_reject");
    setRejectNotes("");
  }, [candidate?.id]);

  if (!candidate) {
    return (
      <section className="recovery-box board-event-review">
        <strong>Confirmation panel</strong>
        <p>No event candidate is waiting on this selected chain.</p>
      </section>
    );
  }

  const variance = operationalVarianceMinutes(
    candidate.schedule_event_planned_at,
    candidate.event_at,
  );

  return (
    <section className="recovery-box board-event-review">
      <strong>Confirmation panel</strong>
      <span className={`status-chip ${operationalTone(candidate.status)}`}>
        {shortOperationalLabel(candidate.status)}
      </span>
      <p>{shortOperationalLabel(candidate.event_kind)} / {candidate.candidate_id}</p>
      <RowActionHint
        actions={assistantActions}
        objectId={candidate.id}
        objectType="operational_event_candidate"
        onNavigate={onAssistantNavigate}
      />
      <dl>
        <div><dt>Evidence</dt><dd>{candidate.feed_ref}</dd></div>
        <div><dt>Confidence</dt><dd>{Math.round(Number(candidate.confidence_score))}%</dd></div>
        <div><dt>Variance</dt><dd>{operationalVarianceLabel(variance)}</dd></div>
      </dl>
      {confirmedEvent ? (
        <em>Confirmed as {confirmedEvent.event_id}</em>
      ) : candidate.status === "pending" ? (
        <div className="board-event-actions">
          <label>
            Confirm reason
            <input
              onChange={(event) => setConfirmReason(event.target.value)}
              value={confirmReason}
            />
          </label>
          <DisabledReasonTooltip actionId="CONFIRM_EVENT" actions={assistantActions}>
            <button
              disabled={!canConfirm || !onConfirm || !confirmReason.trim() || isActionRunning}
              onClick={() => onConfirm?.(candidate.id, candidate.event_at, confirmReason.trim())}
              type="button"
            >
              Confirm
            </button>
          </DisabledReasonTooltip>
          <label>
            Reject reason
            <input
              onChange={(event) => setRejectReason(event.target.value)}
              value={rejectReason}
            />
          </label>
          <label>
            Notes
            <textarea
              onChange={(event) => setRejectNotes(event.target.value)}
              value={rejectNotes}
            />
          </label>
          <DisabledReasonTooltip actionId="REJECT_EVENT" actions={assistantActions}>
            <button
              disabled={!canConfirm || !onReject || !rejectReason.trim() || isActionRunning}
              onClick={() => onReject?.(candidate.id, rejectReason.trim(), rejectNotes.trim())}
              type="button"
            >
              Reject
            </button>
          </DisabledReasonTooltip>
        </div>
      ) : null}
    </section>
  );
}

export function TugBargeAssignmentPage({
  assistantBlockedActions,
  assistantChecklist,
  assistantFlow,
  assistantPageActions,
  assistantRowActions,
  overview,
  canEdit = false,
  canExport = false,
  isActionRunning = false,
  onAssistantNavigate,
  onExport,
  onRegenerate,
}: LogisticsPageProps) {
  const assignments = overview?.assignments ?? EMPTY_ASSIGNMENTS;
  const trips = overview?.trips ?? EMPTY_TRIPS;
  const conflicts = activePlanConflicts(overview?.conflicts ?? EMPTY_CONFLICTS);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<number | null>(
    assignments[0]?.id ?? null,
  );
  const selectedTrip = selectedTripFor(trips, assignments, selectedAssignmentId);
  const selectedConflict = conflictForTrip(conflicts, selectedTrip?.id);
  const assistantActions = [
    ...(assistantRowActions ?? []),
    ...(assistantPageActions ?? []),
    ...(assistantBlockedActions ?? []),
  ];
  const operationalCount = assignments.filter((item) => (
    statusTone(item.status) === "ok"
  )).length;
  const delayedCount = assignments.filter((item) => (
    statusTone(item.status) === "pending"
  )).length;
  const blockedCount = assignments.filter((item) => (
    statusTone(item.status) === "critical"
  )).length;

  return (
    <section className="workspace-page logistics-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Operations / Tug-Barge Assignment</p>
          <h1>Tug/Barge Assignment</h1>
        </div>
        <div className="planning-actions">
          <span className="phase-chip">Fleet feasibility</span>
          <DisabledReasonTooltip actionId="REGENERATE_PLAN" actions={assistantActions}>
            <button
              disabled={!canEdit || !onRegenerate || isActionRunning}
              onClick={onRegenerate}
              type="button"
            >
              Regenerate plan
            </button>
          </DisabledReasonTooltip>
          <DisabledReasonTooltip actionId="GENERATE_EXPORT" actions={assistantActions}>
            <button
              disabled={!canExport || !onExport || isActionRunning}
              onClick={onExport}
              type="button"
            >
              Export chain
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
            <span>Status · tug unit · barge unit · assigned <Abbr term="OGV">OGV</Abbr> · next availability</span>
          </div>
          <div className="grid-scroll">
            <table className="planning-table logistics-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Tug Unit</th>
                  <th>Barge Unit</th>
                  <th>Location</th>
                  <th>Assigned <Abbr term="OGV">OGV</Abbr></th>
                  <th>Next <Abbr term="Avail">Avail</Abbr> <Abbr term="PLN">PLN</Abbr></th>
                  <th>Next <Abbr term="Avail">Avail</Abbr> <Abbr term="PRD">PRD</Abbr></th>
                  <th>Delay Reason</th>
                  <th>Hint</th>
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
                      <td><span className={`status-chip ${statusTone(assignment.status)}`}>{shortStatus(assignment.status)}</span></td>
                      <td><strong>{assignment.tug?.name ?? "UNASSIGNED"}</strong></td>
                      <td>{assignment.barge?.code ?? "NONE"}</td>
                      <td>{assignment.route_segment ? `SEG-${assignment.route_segment}` : assignment.jetty?.code ?? "-"}</td>
                      <td>{assignment.vessel_name}</td>
                      <td>{dt(assignment.planned_arrival)}</td>
                      <td>{dt(trip?.planned_end)}</td>
                      <td>{conflict?.message || assignment.next_constraint || "—"}</td>
                      <td>
                        <RowActionHint
                          actions={assistantActions}
                          objectId={assignment.id}
                          objectType="assignment"
                          onNavigate={onAssistantNavigate}
                        />
                      </td>
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
              <span className={`status-chip ${statusTone(selectedTrip.status)}`}>
                {shortStatus(selectedTrip.status)}
              </span>
              <h2>{selectedTrip.voyage.vessel_name}</h2>
              <p>{selectedTrip.assignment?.next_action ?? selectedConflict?.message ?? "No blocker recorded."}</p>
              <dl>
                <div><dt>Tug</dt><dd>{selectedTrip.assignment?.tug?.code ?? "Unassigned"}</dd></div>
                <div><dt>Barge</dt><dd>{selectedTrip.assignment?.barge?.code ?? "Unassigned"}</dd></div>
                <div><dt>Jetty</dt><dd>{selectedTrip.assignment?.jetty?.code ?? "Unassigned"}</dd></div>
                <div><dt><Abbr term="CTS">CTS</Abbr></dt><dd>{selectedTrip.assignment?.cts?.code ?? "Unassigned"}</dd></div>
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
                  className={`gantt-pill ${statusTone(trip.status)}`}
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

export function JettyLoadingPage({
  assistantBlockedActions,
  assistantChecklist,
  assistantFlow,
  assistantPageActions,
  assistantRowActions,
  overview,
  canEdit = false,
  canConfirmJetty = false,
  canExport = false,
  isActionRunning = false,
  operationCandidates = EMPTY_CANDIDATES,
  confirmedOperationalEvents = EMPTY_CONFIRMED_EVENTS,
  operationDevices = EMPTY_DEVICES,
  onAssistantNavigate,
  onExport,
  onForceStartJetty,
  onConfirmOperationalEvent,
  onRejectOperationalEvent,
}: LogisticsPageProps) {
  const assignments = overview?.assignments ?? EMPTY_ASSIGNMENTS;
  const trips = overview?.trips ?? EMPTY_TRIPS;
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<number | null>(
    assignments.find((assignment) => assignment.jetty)?.id ?? assignments[0]?.id ?? null,
  );
  const [isOverridePanelOpen, setIsOverridePanelOpen] = useState(false);
  const [effectiveStart, setEffectiveStart] = useState("");
  const byJetty = useMemo(() => {
    const groups = new Map<string, AssignmentRecord[]>();
    assignments.forEach((assignment) => {
      const key = assignment.jetty?.code ?? "UNASSIGNED";
      groups.set(key, [...(groups.get(key) ?? []), assignment]);
    });
    return [...groups.entries()];
  }, [assignments]);
  const selectedAssignment = assignments.find((assignment) => assignment.id === selectedAssignmentId)
    ?? assignments.find((assignment) => assignment.jetty)
    ?? assignments[0];
  const selectedTrip = trips.find((trip) => trip.id === selectedAssignment?.trip);
  const plannedLoadStart = selectedTrip?.events.find((event) => event.event_type === "load_start")?.planned_at
    ?? selectedTrip?.planned_start
    ?? "";
  const loadStartEvent = eventFor(selectedTrip, "load_start");
  const loadCompleteEvent = eventFor(selectedTrip, "load_complete");
  const departJettyEvent = eventFor(selectedTrip, "depart_jetty");
  const selectedJettyCandidate = latestCandidate(operationCandidates, (candidate) => (
    candidate.trip === selectedTrip?.id
    && JETTY_EVENT_KINDS.includes(candidate.event_kind as (typeof JETTY_EVENT_KINDS)[number])
    && candidate.status === "pending"
  ));
  const selectedJettyConfirmedEvent = selectedJettyCandidate
    ? confirmedEventForCandidate(confirmedOperationalEvents, selectedJettyCandidate.id)
    : latestConfirmedEvent(confirmedOperationalEvents, (event) => (
      event.trip === selectedTrip?.id
      && JETTY_EVENT_KINDS.includes(event.event_kind as (typeof JETTY_EVENT_KINDS)[number])
    ));
  const selectedDevice = deviceFor(operationDevices, selectedAssignment?.jetty?.code);
  const confirmedJettyCount = confirmedOperationalEvents.filter((event) => (
    event.asset_type === "jetty"
  )).length;
  const assistantActions = [
    ...(assistantRowActions ?? []),
    ...(assistantPageActions ?? []),
    ...(assistantBlockedActions ?? []),
  ];

  useEffect(() => {
    if (!selectedAssignmentId && assignments.length) {
      setSelectedAssignmentId(assignments.find((assignment) => assignment.jetty)?.id ?? assignments[0].id);
    }
  }, [assignments, selectedAssignmentId]);

  function openOverridePanel() {
    setEffectiveStart(datetimeLocalValue(plannedLoadStart, 120));
    setIsOverridePanelOpen(true);
  }

  function submitOverride(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const actualStartAt = toIsoFromLocal(effectiveStart);
    if (!selectedAssignment || !actualStartAt) return;
    void onForceStartJetty?.(selectedAssignment.id, actualStartAt);
    setIsOverridePanelOpen(false);
  }

  return (
    <section className="workspace-page logistics-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Operations / Jetty Loading Plan</p>
          <h1>Jetty Loading</h1>
        </div>
        <div className="planning-actions">
          <span className="phase-chip">Source-side queue</span>
          <DisabledReasonTooltip actionId="FORCE_START_JETTY" actions={assistantActions}>
            <button
              disabled={!canEdit || !onForceStartJetty || !selectedAssignment || isActionRunning}
              onClick={openOverridePanel}
              title={!canEdit ? "Your role cannot force-start jetty queues." : undefined}
              type="button"
            >
              Force start jetty
            </button>
          </DisabledReasonTooltip>
          <DisabledReasonTooltip actionId="GENERATE_EXPORT" actions={assistantActions}>
            <button
              disabled={!canExport || !onExport || isActionRunning}
              onClick={onExport}
              type="button"
            >
              Export loading plan
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

      <div className="metric-strip five-up planning-kpis">
        <div><span>Confirmed jetty events</span><strong className="success-text">{confirmedJettyCount}</strong></div>
        <div><span>Pending review</span><strong className={selectedJettyCandidate ? "warning-text" : ""}>{selectedJettyCandidate ? 1 : 0}</strong></div>
        <div><span>Actual load start</span><strong>{loadStartEvent?.actual_at ? "SET" : "-"}</strong></div>
        <div><span>Actual load end</span><strong className={loadCompleteEvent?.actual_at ? "success-text" : ""}>{loadCompleteEvent?.actual_at ? "SET" : "-"}</strong></div>
        <div><span>Feed health</span><strong className={`${operationalTone(selectedDevice?.latest_health?.healthStatus ?? selectedDevice?.status)}-text`}>{deviceHealthLabel(selectedDevice)}</strong></div>
      </div>

      <div className="jetty-layout">
        <section className="board-surface jetty-plan-panel">
          <div className="grid-header">
            <div><SvgIcon name="locations" /><strong>Jetty execution queue</strong></div>
            <span><Abbr term="OGV">OGV</Abbr>, grade, hatch/layer, tonnage, start/end, readiness, next constraint</span>
          </div>
          <div className="jetty-sections">
            {byJetty.map(([jettyCode, rows]) => (
              <section className="jetty-section" key={jettyCode}>
                <h2>{jettyCode}<span>{rows[0]?.jetty?.status?.toUpperCase() ?? "PLANNED"}</span></h2>
                <div className="jetty-row jetty-row-header">
                  <span><Abbr term="OGV">OGV</Abbr></span><span>Grade</span><span>Hatch</span><span>Load <Abbr term="MT">MT</Abbr></span>
                  <span>Progress</span><span>Planned start / end</span><span>Actual start / end</span><span>Readiness</span><span>Next</span>
                </div>
                {rows.map((assignment) => {
                  const trip = trips.find((item) => item.id === assignment.trip);
                  return (
                    <div
                      className={selectedAssignment?.id === assignment.id ? "jetty-row selected-row" : "jetty-row"}
                      key={assignment.id}
                      onClick={() => setSelectedAssignmentId(assignment.id)}
                    >
                      <strong>{assignment.vessel_name}</strong>
                      <span>{trip?.cargo_layer_step?.coal_grade.code ?? "-"}</span>
                      <span>H{trip?.cargo_layer_step?.hatch_no ?? "-"}-L{trip?.cargo_layer_step?.layer_no ?? "-"}</span>
                      <span>{mt(assignment.planned_quantity_mt)}</span>
                      <span><i style={{ width: `${trip ? progressFor(trip) : 0}%` }} /></span>
                      <span>{dt(trip?.planned_start)} / {dt(trip?.planned_end)}</span>
                      <span>
                        {dt(eventFor(trip, "load_start")?.actual_at)}
                        {" / "}
                        {dt(eventFor(trip, "load_complete")?.actual_at)}
                      </span>
                      <span className={statusTone(assignment.status)}>{trip ? `${progressFor(trip)}%` : "0%"}</span>
                      <span>{assignment.next_action}</span>
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
            <span>Reason and impact capture</span>
          </div>
          <div className="inspector-body">
            <span className="status-chip pending">Operator controlled</span>
            <h2>{selectedAssignment?.jetty?.code ?? "Jetty readiness"}</h2>
            <p>{selectedAssignment
              ? `${selectedAssignment.vessel_name} / ${selectedAssignment.trip_ref}`
              : "Select an assignment before applying a governed override."}</p>
            <dl>
              <div><dt>Planned load</dt><dd>{dt(plannedLoadStart)}</dd></div>
              <div><dt>Actual start</dt><dd>{dt(loadStartEvent?.actual_at)}</dd></div>
              <div><dt>Actual complete</dt><dd>{dt(loadCompleteEvent?.actual_at)}</dd></div>
              <div><dt>Loaded <Abbr term="MT">MT</Abbr></dt><dd>{selectedTrip ? mt(selectedTrip.loaded_quantity_mt) : "-"}</dd></div>
              <div><dt>Barge</dt><dd>{selectedAssignment?.barge?.code ?? "Unassigned"}</dd></div>
              <div><dt>Grade</dt><dd>{selectedTrip?.cargo_layer_step?.coal_grade.code ?? "-"}</dd></div>
              <div><dt>Departure ready</dt><dd>{departJettyEvent?.actual_at ? "Confirmed" : "Pending"}</dd></div>
              <div><dt>Feed health</dt><dd>{deviceHealthLabel(selectedDevice)}</dd></div>
              <div><dt>Status</dt><dd>{selectedAssignment ? shortStatus(selectedAssignment.status) : "-"}</dd></div>
            </dl>
            {isOverridePanelOpen ? (
              <form className="governed-override-form" onSubmit={submitOverride}>
                <label>
                  Effective start time
                  <input
                    onChange={(event) => setEffectiveStart(event.target.value)}
                    required
                    type="datetime-local"
                    value={effectiveStart}
                  />
                </label>
                <div className="override-form-actions">
                  <DisabledReasonTooltip actionId="FORCE_START_JETTY" actions={assistantActions}>
                    <button disabled={!effectiveStart || isActionRunning} type="submit">
                      Apply governed override
                    </button>
                  </DisabledReasonTooltip>
                  <button onClick={() => setIsOverridePanelOpen(false)} type="button">
                    Cancel
                  </button>
                </div>
              </form>
            ) : (
              <>
                <section className="recovery-box">
                  <strong>Calculated impact</strong>
                  <p>Force start captures the effective start time and calculates current-trip tide and bridge risk.</p>
                </section>
                <CandidateReviewPanel
                  assistantActions={assistantActions}
                  candidate={selectedJettyCandidate}
                  canConfirm={canConfirmJetty}
                  confirmedEvent={selectedJettyConfirmedEvent}
                  isActionRunning={isActionRunning}
                  onAssistantNavigate={onAssistantNavigate}
                  onConfirm={onConfirmOperationalEvent}
                  onReject={onRejectOperationalEvent}
                />
              </>
            )}
          </div>
        </aside>
      </div>
    </section>
  );
}

export function CtsOperationsPage({
  assistantBlockedActions,
  assistantChecklist,
  assistantFlow,
  assistantPageActions,
  assistantRowActions,
  overview,
  canConfirmCts = false,
  canExport = false,
  isActionRunning = false,
  operationCandidates = EMPTY_CANDIDATES,
  confirmedOperationalEvents = EMPTY_CONFIRMED_EVENTS,
  operationDevices = EMPTY_DEVICES,
  onAssistantNavigate,
  onExport,
  onConfirmOperationalEvent,
  onRejectOperationalEvent,
}: LogisticsPageProps) {
  const assignments = overview?.assignments ?? EMPTY_ASSIGNMENTS;
  const trips = overview?.trips ?? EMPTY_TRIPS;
  const activeCts = new Set(assignments.map((assignment) => assignment.cts?.code).filter(Boolean)).size;
  const waitingQueue = assignments.filter((assignment) => assignment.status.includes("waiting")).length;
  const downtime = assignments.filter((assignment) => (
    statusTone(assignment.status) === "critical"
  )).length;
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<number | null>(assignments[0]?.id ?? null);
  const selectedAssignment = assignments.find((assignment) => assignment.id === selectedAssignmentId)
    ?? assignments[0];
  const selectedTrip = trips.find((trip) => trip.id === selectedAssignment?.trip);
  const selectedCtsCandidate = latestCandidate(operationCandidates, (candidate) => (
    candidate.trip === selectedTrip?.id
    && CTS_EVENT_KINDS.includes(candidate.event_kind as (typeof CTS_EVENT_KINDS)[number])
    && candidate.status === "pending"
  ));
  const selectedCtsConfirmedEvent = selectedCtsCandidate
    ? confirmedEventForCandidate(confirmedOperationalEvents, selectedCtsCandidate.id)
    : latestConfirmedEvent(confirmedOperationalEvents, (event) => (
      event.trip === selectedTrip?.id
      && CTS_EVENT_KINDS.includes(event.event_kind as (typeof CTS_EVENT_KINDS)[number])
    ));
  const selectedCtsDevice = deviceFor(operationDevices, selectedAssignment?.cts?.code);
  const lowRateCandidates = operationCandidates.filter((candidate) => (
    candidate.event_kind === "cts_rate_updated"
    && candidate.status === "pending"
  ));
  const assistantActions = [
    ...(assistantRowActions ?? []),
    ...(assistantPageActions ?? []),
    ...(assistantBlockedActions ?? []),
  ];

  return (
    <section className="workspace-page logistics-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Operations / <Abbr term="CTS">CTS</Abbr> Floating Crane</p>
          <h1><Abbr term="CTS">CTS</Abbr> / Floating Crane</h1>
        </div>
        <div className="planning-actions">
          <span className="phase-chip">Transshipment capacity</span>
          <DisabledReasonTooltip actionId="GENERATE_EXPORT" actions={assistantActions}>
            <button
              disabled={!canExport || !onExport || isActionRunning}
              onClick={onExport}
              type="button"
            >
              Export <Abbr term="CTS">CTS</Abbr> queue
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

      <div className="metric-strip four-up planning-kpis">
        <div><span>Active <Abbr term="CTS">CTS</Abbr></span><strong>{activeCts}</strong></div>
        <div><span><Abbr term="Avg">Avg</Abbr> discharge rate</span><strong>{Math.round((overview?.validation.loadedMt ?? 0) / Math.max(activeCts, 1)).toLocaleString()}</strong></div>
        <div><span>Barge queue</span><strong className={waitingQueue ? "warning-text" : ""}>{waitingQueue}</strong></div>
        <div><span>Low-rate signals</span><strong className={lowRateCandidates.length ? "warning-text" : ""}>{lowRateCandidates.length || downtime}</strong></div>
      </div>

      <div className="cts-layout">
        <section className="board-surface planning-grid-panel cts-panel">
          <div className="grid-header">
            <div><SvgIcon name="operations" /><strong><Abbr term="CTS">CTS</Abbr> operations board</strong></div>
            <span>Planned versus actual discharge state, low-rate signals, queue pressure</span>
          </div>
          <div className="grid-scroll">
            <table className="planning-table logistics-table">
              <thead>
                <tr>
                  <th><Abbr term="CTS">CTS</Abbr> <Abbr term="ID">ID</Abbr></th><th>Current <Abbr term="OGV">OGV</Abbr></th><th>Assigned Barge</th><th>Queue <Abbr term="Pos">Pos</Abbr></th>
                  <th>Coal Grade</th><th>Planned start</th><th>Actual start</th><th>Actual complete</th>
                  <th>Rate signal</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {assignments.map((assignment, index) => {
                  const trip = trips.find((item) => item.id === assignment.trip);
                  const rateCandidate = latestCandidate(operationCandidates, (candidate) => (
                    candidate.trip === trip?.id && candidate.event_kind === "cts_rate_updated"
                  ));
                  return (
                    <tr
                      className={selectedAssignment?.id === assignment.id ? "selected-row" : ""}
                      key={assignment.id}
                      onClick={() => setSelectedAssignmentId(assignment.id)}
                    >
                      <td><strong>{assignment.cts?.code ?? "UNASSIGNED"}</strong></td>
                      <td>{assignment.vessel_name}</td>
                      <td>{assignment.barge?.code ?? "-"}</td>
                      <td>Q{index + 1}</td>
                      <td>{trip?.cargo_layer_step?.coal_grade.code ?? "-"}</td>
                      <td>{dt(eventFor(trip, "arrive_cts")?.planned_at)}</td>
                      <td>{dt(eventFor(trip, "discharge_start")?.actual_at)}</td>
                      <td>{dt(eventFor(trip, "discharge_complete")?.actual_at)}</td>
                      <td>{rateCandidate ? shortOperationalLabel(rateCandidate.status) : "-"}</td>
                      <td><span className={`status-chip ${statusTone(assignment.status)}`}>{shortStatus(assignment.status)}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="board-surface logistics-inspector">
          <div className="grid-header">
            <div><SvgIcon name="account-tree" /><strong><Abbr term="CTS">CTS</Abbr> event detail</strong></div>
            <span>{selectedAssignment?.cts?.code ?? <AbbrText text="No CTS" />}</span>
          </div>
          <div className="inspector-body">
            <span className={`status-chip ${operationalTone(selectedCtsDevice?.latest_health?.healthStatus ?? selectedCtsDevice?.status)}`}>
              {deviceHealthLabel(selectedCtsDevice)}
            </span>
            <h2>{selectedAssignment?.vessel_name ?? <AbbrText text="CTS queue" />}</h2>
            <dl>
              <div><dt>Arrived actual</dt><dd>{dt(eventFor(selectedTrip, "arrive_cts")?.actual_at)}</dd></div>
              <div><dt>Discharge start</dt><dd>{dt(eventFor(selectedTrip, "discharge_start")?.actual_at)}</dd></div>
              <div><dt>Discharge complete</dt><dd>{dt(eventFor(selectedTrip, "discharge_complete")?.actual_at)}</dd></div>
              <div><dt>Pending rate</dt><dd>{selectedCtsCandidate?.event_kind === "cts_rate_updated" ? shortOperationalLabel(selectedCtsCandidate.status) : "-"}</dd></div>
              <div><dt>Queue impact</dt><dd>{selectedCtsCandidate ? "Review before downstream release" : "No active signal"}</dd></div>
            </dl>
            <CandidateReviewPanel
              assistantActions={assistantActions}
              candidate={selectedCtsCandidate}
              canConfirm={canConfirmCts}
              confirmedEvent={selectedCtsConfirmedEvent}
              isActionRunning={isActionRunning}
              onAssistantNavigate={onAssistantNavigate}
              onConfirm={onConfirmOperationalEvent}
              onReject={onRejectOperationalEvent}
            />
          </div>
        </aside>
      </div>
    </section>
  );
}

export function PublishedPlanPage({
  assistantBlockedActions,
  assistantChecklist,
  assistantFlow,
  assistantPageActions,
  assistantRowActions,
  overview,
  canCreateDraft = false,
  isActionRunning = false,
  onAssistantNavigate,
  onCreateDraft,
  onSubmitApproval,
}: LogisticsPageProps) {
  const trips = overview?.trips ?? EMPTY_TRIPS;
  const conflicts = activePlanConflicts(overview?.conflicts ?? EMPTY_CONFLICTS);
  const activeVersion = overview?.activePlanVersion;
  const lineage = activeVersion?.scenario_lineage;
  const scenarioDiff = activeVersion?.scenario_diff_summary;
  const selectedTrip = trips[0];
  const selectedConflict = conflictForTrip(conflicts, selectedTrip?.id);
  const range = useMemo(() => ganttRange(trips), [trips]);
  const assistantActions = [
    ...(assistantRowActions ?? []),
    ...(assistantPageActions ?? []),
    ...(assistantBlockedActions ?? []),
  ];

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
          <DisabledReasonTooltip actionId="CREATE_DRAFT" actions={assistantActions}>
            <button
              disabled={!canCreateDraft || !onCreateDraft || isActionRunning}
              onClick={onCreateDraft}
              type="button"
            >
              Create draft
            </button>
          </DisabledReasonTooltip>
          <DisabledReasonTooltip actionId="SUBMIT_APPROVAL" actions={assistantActions}>
            <button
              disabled={!canCreateDraft || !onSubmitApproval || isActionRunning}
              onClick={onSubmitApproval}
              type="button"
            >
              Submit approval
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
                {range.ticks.map((tick, index) => (
                  <span
                    key={tick}
                    style={{ left: `${ganttPosition(tick, range)}%` }}
                  >
                    {ganttTickLabel(tick, index, range.ticks)}
                  </span>
                ))}
              </div>
              <div aria-hidden="true" className="gantt-gridlines">
                {range.ticks.map((tick) => (
                  <i key={tick} style={{ left: `${ganttPosition(tick, range)}%` }} />
                ))}
              </div>
              {trips.map((trip) => {
                const conflict = conflictForTrip(conflicts, trip.id);
                return (
                  <div className="gantt-resource-row" key={trip.id}>
                    <span
                      className={`gantt-block ${statusTone(trip.status)}`}
                      style={ganttBlockStyle(trip, range)}
                      title={`${dtText(trip.planned_start)} - ${dtText(trip.planned_end)}`}
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
              <span className={`status-chip ${statusTone(selectedTrip.status)}`}>
                {selectedTrip.status}
              </span>
              <h2>{selectedTrip.trip_id}</h2>
              <p>{selectedTrip.voyage.vessel_name}</p>
              <dl>
                <div><dt>Jetty</dt><dd>{selectedTrip.origin_jetty?.code ?? "Unassigned"}</dd></div>
                <div><dt>Tug</dt><dd>{selectedTrip.assignment?.tug?.code ?? "Unassigned"}</dd></div>
                <div><dt>Barge</dt><dd>{selectedTrip.assignment?.barge?.code ?? "Unassigned"}</dd></div>
                <div><dt><Abbr term="CTS">CTS</Abbr></dt><dd>{selectedTrip.assignment?.cts?.code ?? "Unassigned"}</dd></div>
                <div><dt>Planned start</dt><dd>{dt(selectedTrip.planned_start)}</dd></div>
                <div><dt>Planned end</dt><dd>{dt(selectedTrip.planned_end)}</dd></div>
              </dl>
              {lineage ? (
                <section className="recovery-box">
                  <strong>Promoted scenario ancestry</strong>
                  <dl>
                    <div><dt>Scenario</dt><dd>{lineage.scenarioId}</dd></div>
                    <div><dt>Run</dt><dd>{lineage.selectedRunRef}</dd></div>
                    <div><dt>Baseline</dt><dd>{lineage.baselineVersionRef}</dd></div>
                    <div><dt>Changed trips</dt><dd>{scenarioDiff?.changedTripCount ?? 0}</dd></div>
                    <div><dt>Aggregate delay</dt><dd>{scenarioDiff ? `${scenarioDiff.delayDeltaMinutes > 0 ? "+" : ""}${scenarioDiff.delayDeltaMinutes}m` : "0m"}</dd></div>
                  </dl>
                </section>
              ) : null}
              <section className="recovery-box">
                <strong>Conflict center <Abbr term="MVP">MVP</Abbr></strong>
                <p>{selectedConflict?.message ?? "No active conflict on this trip."}</p>
              </section>
            </div>
          ) : null}
        </aside>
      </div>
    </section>
  );
}
