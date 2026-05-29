import { FormEvent, useEffect, useMemo, useState } from "react";

import { GridDate } from "../components/GridDate";
import { SvgIcon } from "../components/SvgIcon";
import {
  DisabledReasonTooltip,
  RecommendationCard,
  RowActionHint,
  type AssistantRecommendationSurfaceProps,
} from "../components/assistant";
import type {
  ConfirmedOperationalEventRecord,
  DeviceEndpointRecord,
  OperationalEventCandidateRecord,
  OperationsOverviewRecord,
} from "../types";

type CandidateStatusFilter = "pending" | "confirmed" | "rejected" | "all";

type OperationsEventConsolePageProps = AssistantRecommendationSurfaceProps & {
  candidates: OperationalEventCandidateRecord[];
  confirmedEvents: ConfirmedOperationalEventRecord[];
  devices: DeviceEndpointRecord[];
  overview: OperationsOverviewRecord | null;
  permissions: string[];
  isActionRunning?: boolean;
  onConfirm?: (candidateId: number, actualAt: string, reasonCode: string) => void | Promise<void>;
  onReject?: (candidateId: number, reasonCode: string, notes: string) => void | Promise<void>;
};

function short(value: string | null | undefined) {
  return value ? value.replaceAll("_", " ").toUpperCase() : "-";
}

function tone(value: string | null | undefined) {
  if (value === "confirmed" || value === "auto_confirmed" || value === "healthy" || value === "active") {
    return "ok";
  }
  if (value === "rejected" || value === "duplicate" || value === "critical" || value === "offline") {
    return "critical";
  }
  return "pending";
}

function datetimeLocalValue(value: string | null | undefined) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function toIsoFromLocal(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString();
}

function varianceMinutes(plannedAt: string | null, observedAt: string | null) {
  if (!plannedAt || !observedAt) return null;
  const planned = new Date(plannedAt);
  const observed = new Date(observedAt);
  if (Number.isNaN(planned.getTime()) || Number.isNaN(observed.getTime())) return null;
  return Math.round((observed.getTime() - planned.getTime()) / 60000);
}

function varianceLabel(value: number | null) {
  if (value === null) return "No match";
  return `${value > 0 ? "+" : ""}${value}m`;
}

function canConfirmCandidate(permissions: string[], eventKind: string) {
  if (permissions.includes("*")) return true;
  if (eventKind.startsWith("jetty_")) return permissions.includes("operations.confirm_jetty");
  if (eventKind.startsWith("cts_")) return permissions.includes("operations.confirm_cts");
  if (eventKind.startsWith("bridge_")) return permissions.includes("operations.confirm_bridge");
  if (eventKind.startsWith("tide_")) return permissions.includes("operations.confirm_tide");
  return [
    "operations.confirm_jetty",
    "operations.confirm_cts",
    "operations.confirm_bridge",
    "operations.confirm_tide",
  ].some((permission) => permissions.includes(permission));
}

function payloadSummary(payload: Record<string, unknown>) {
  const entries = Object.entries(payload);
  if (!entries.length) return "No payload fields";
  return entries
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(" | ");
}

export function OperationsEventConsolePage({
  assistantBlockedActions,
  assistantChecklist,
  assistantFlow,
  assistantPageActions,
  assistantRowActions,
  candidates,
  confirmedEvents,
  devices,
  overview,
  permissions,
  isActionRunning = false,
  onAssistantNavigate,
  onConfirm,
  onReject,
}: OperationsEventConsolePageProps) {
  const [statusFilter, setStatusFilter] = useState<CandidateStatusFilter>("pending");
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(
    candidates[0]?.id ?? null,
  );
  const [actualAt, setActualAt] = useState("");
  const [confirmReason, setConfirmReason] = useState("operator_verified");
  const [rejectReason, setRejectReason] = useState("manual_reject");
  const [rejectNotes, setRejectNotes] = useState("");

  const filteredCandidates = useMemo(() => {
    if (statusFilter === "all") return candidates;
    if (statusFilter === "confirmed") {
      return candidates.filter((candidate) => ["confirmed", "auto_confirmed"].includes(candidate.status));
    }
    return candidates.filter((candidate) => candidate.status === statusFilter);
  }, [candidates, statusFilter]);

  const selectedCandidate = filteredCandidates.find((candidate) => candidate.id === selectedCandidateId)
    ?? filteredCandidates[0]
    ?? candidates.find((candidate) => candidate.id === selectedCandidateId)
    ?? candidates[0]
    ?? null;
  const selectedConfirmedEvent = selectedCandidate
    ? confirmedEvents.find((event) => event.candidate === selectedCandidate.id) ?? null
    : null;
  const selectedVariance = selectedCandidate
    ? varianceMinutes(selectedCandidate.schedule_event_planned_at, selectedCandidate.event_at)
    : null;
  const selectedCanConfirm = selectedCandidate
    ? canConfirmCandidate(permissions, selectedCandidate.event_kind)
    : false;
  const health = overview?.health ?? null;
  const assistantActions = [
    ...(assistantRowActions ?? []),
    ...(assistantPageActions ?? []),
    ...(assistantBlockedActions ?? []),
  ];

  useEffect(() => {
    if (
      filteredCandidates[0]
      && !filteredCandidates.some((candidate) => candidate.id === selectedCandidateId)
    ) {
      setSelectedCandidateId(filteredCandidates[0].id);
    }
  }, [filteredCandidates, selectedCandidateId]);

  useEffect(() => {
    setActualAt(datetimeLocalValue(selectedCandidate?.event_at));
    setRejectNotes("");
  }, [selectedCandidate?.id, selectedCandidate?.event_at]);

  function submitConfirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCandidate || !selectedCanConfirm) return;
    const confirmedActualAt = toIsoFromLocal(actualAt);
    if (!confirmedActualAt || !confirmReason.trim()) return;
    void onConfirm?.(selectedCandidate.id, confirmedActualAt, confirmReason.trim());
  }

  function submitReject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCandidate || !selectedCanConfirm || !rejectReason.trim()) return;
    void onReject?.(selectedCandidate.id, rejectReason.trim(), rejectNotes.trim());
  }

  return (
    <section className="workspace-page event-console-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Operations / Event Confirmation</p>
          <h1>Operations Event Console</h1>
        </div>
        <div className="planning-actions">
          <span className="phase-chip">Actualization desk</span>
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

      <div className="metric-strip six-up event-kpis">
        <div><span>Pending</span><strong className={overview?.candidates.pending ? "warning-text" : ""}>{overview?.candidates.pending ?? 0}</strong></div>
        <div><span>Confirmed</span><strong className="success-text">{overview?.candidates.confirmed ?? 0}</strong></div>
        <div><span>Rejected</span><strong className={overview?.candidates.rejected ? "critical-text" : ""}>{overview?.candidates.rejected ?? 0}</strong></div>
        <div><span>Duplicates</span><strong>{overview?.candidates.duplicates ?? 0}</strong></div>
        <div><span>Offline devices</span><strong className={overview?.devices.offline ? "critical-text" : ""}>{overview?.devices.offline ?? 0}</strong></div>
        <div><span>Degraded feeds</span><strong className={overview?.feeds.degraded ? "warning-text" : ""}>{overview?.feeds.degraded ?? 0}</strong></div>
      </div>

      <section className="board-surface event-health-strip">
        <div className="grid-header">
          <div><SvgIcon name="operations" /><strong>Feed and device health</strong></div>
          <span>Signal freshness and operator-review risk</span>
        </div>
        <div className="event-health-grid">
          <div>
            <span>Health state</span>
            <strong className={`${tone(health?.status)}-text`}>{short(health?.status)}</strong>
          </div>
          <div>
            <span>Healthy snapshots</span>
            <strong>{health?.snapshots.healthy ?? 0}</strong>
          </div>
          <div>
            <span>Warning snapshots</span>
            <strong className={(health?.snapshots.warning ?? 0) ? "warning-text" : ""}>{health?.snapshots.warning ?? 0}</strong>
          </div>
          <div>
            <span>Critical risks</span>
            <strong className={(health?.criticalRiskCount ?? 0) ? "critical-text" : ""}>{health?.criticalRiskCount ?? 0}</strong>
          </div>
          <div>
            <span>Observed latest</span>
            <strong><GridDate value={health?.snapshots.latestObservedAt} /></strong>
          </div>
        </div>
        <div className="event-health-devices">
          {devices.slice(0, 4).map((device) => (
            <span className={tone(device.latest_health?.healthStatus ?? device.status)} key={device.id}>
              {device.device_id}
              <strong>{short(device.latest_health?.healthStatus ?? device.status)}</strong>
            </span>
          ))}
          {!devices.length ? <em>No device health available</em> : null}
        </div>
      </section>

      <div className="event-console-layout">
        <aside className="board-surface event-filter-rail">
          <div className="grid-header">
            <div><SvgIcon name="rule" /><strong>Queue filters</strong></div>
          </div>
          <div className="event-filter-buttons">
            {(["pending", "confirmed", "rejected", "all"] as CandidateStatusFilter[]).map((filter) => (
              <button
                className={statusFilter === filter ? "active" : ""}
                key={filter}
                onClick={() => setStatusFilter(filter)}
                type="button"
              >
                <span>{short(filter)}</span>
                <strong>
                  {filter === "all"
                    ? candidates.length
                    : filter === "confirmed"
                      ? candidates.filter((candidate) => ["confirmed", "auto_confirmed"].includes(candidate.status)).length
                      : candidates.filter((candidate) => candidate.status === filter).length}
                </strong>
              </button>
            ))}
          </div>
          <section className="event-risk-list">
            <h2>Current health risks</h2>
            {health?.risks.slice(0, 4).map((risk) => (
              <span className={tone(risk.severity)} key={risk.id}>
                <strong>{short(risk.eventKind)}</strong>
                <em>{risk.deviceId ?? risk.assetCode}</em>
              </span>
            ))}
            {!health?.risks.length ? <em>No active health risks</em> : null}
          </section>
        </aside>

        <section className="board-surface event-queue-panel">
          <div className="grid-header">
            <div><SvgIcon name="audit" /><strong>Candidate event queue</strong></div>
            <span>Candidate vs plan, confidence, and review state</span>
          </div>
          <div className="grid-scroll">
            <table className="planning-table event-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Event</th>
                  <th>Asset</th>
                  <th>Variance</th>
                  <th>Planned</th>
                  <th>Candidate</th>
                  <th>Trip</th>
                  <th>Conf.</th>
                  <th>Hint</th>
                </tr>
              </thead>
              <tbody>
                {filteredCandidates.map((candidate) => {
                  const variance = varianceMinutes(
                    candidate.schedule_event_planned_at,
                    candidate.event_at,
                  );
                  return (
                    <tr
                      className={candidate.id === selectedCandidate?.id ? "selected-row" : ""}
                      key={candidate.id}
                      onClick={() => setSelectedCandidateId(candidate.id)}
                    >
                      <td><span className={`status-chip ${tone(candidate.status)}`}>{short(candidate.status)}</span></td>
                      <td><strong>{short(candidate.event_kind)}</strong></td>
                      <td>{candidate.asset_code || short(candidate.asset_type)}</td>
                      <td className={`${tone(variance && variance > 15 ? "warning" : "confirmed")}-text`}>{varianceLabel(variance)}</td>
                      <td><GridDate value={candidate.schedule_event_planned_at} /></td>
                      <td><GridDate value={candidate.event_at} /></td>
                      <td>{candidate.trip_ref ?? "-"}</td>
                      <td>{Math.round(Number(candidate.confidence_score))}%</td>
                      <td>
                        <RowActionHint
                          actions={assistantActions}
                          objectId={candidate.id}
                          objectType="operational_event_candidate"
                          onNavigate={onAssistantNavigate}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!filteredCandidates.length ? (
              <div className="empty-state">
                <strong>No candidate events in this view</strong>
                <span>Change the filter or replay the Phase 4 proof flow to create evidence.</span>
              </div>
            ) : null}
          </div>
        </section>

        <aside className="board-surface event-detail-rail">
          <div className="grid-header">
            <div><SvgIcon name="account-tree" /><strong>Candidate detail</strong></div>
            <span>{selectedCandidate?.candidate_id ?? "No selection"}</span>
          </div>
          {selectedCandidate ? (
            <div className="event-detail-body">
              <span className={`status-chip ${tone(selectedCandidate.status)}`}>{short(selectedCandidate.status)}</span>
              <h2>{short(selectedCandidate.event_kind)}</h2>
              <p>{payloadSummary(selectedCandidate.payload)}</p>
              <dl>
                <div><dt>Asset</dt><dd>{selectedCandidate.asset_code || short(selectedCandidate.asset_type)}</dd></div>
                <div><dt>Trip</dt><dd>{selectedCandidate.trip_ref ?? "-"}</dd></div>
                <div><dt>Feed</dt><dd>{selectedCandidate.feed_ref}</dd></div>
                <div><dt>Device</dt><dd>{selectedCandidate.device_ref ?? "-"}</dd></div>
                <div><dt>Planned</dt><dd><GridDate value={selectedCandidate.schedule_event_planned_at} /></dd></div>
                <div><dt>Candidate</dt><dd><GridDate value={selectedCandidate.event_at} /></dd></div>
                <div><dt>Variance</dt><dd className={`${tone(selectedVariance && selectedVariance > 15 ? "warning" : "confirmed")}-text`}>{varianceLabel(selectedVariance)}</dd></div>
                <div><dt>Confirmed ref</dt><dd>{selectedCandidate.confirmed_event_ref ?? "-"}</dd></div>
              </dl>
              {selectedConfirmedEvent ? (
                <section className="event-confirmed-summary">
                  <strong>Confirmed operational fact</strong>
                  <span>{selectedConfirmedEvent.event_id}</span>
                  <em>{short(selectedConfirmedEvent.confirmation_mode)} by {selectedConfirmedEvent.confirmed_by_email ?? "system"}</em>
                </section>
              ) : null}
              <RowActionHint
                actions={assistantActions}
                objectId={selectedCandidate.id}
                objectType="operational_event_candidate"
                onNavigate={onAssistantNavigate}
              />
              {selectedCandidate.status === "pending" ? (
                <div className="event-action-stack">
                  <form onSubmit={submitConfirm}>
                    <label>
                      Confirmed actual time
                      <input
                        onChange={(event) => setActualAt(event.target.value)}
                        required
                        type="datetime-local"
                        value={actualAt}
                      />
                    </label>
                    <label>
                      Confirmation reason
                      <input
                        onChange={(event) => setConfirmReason(event.target.value)}
                        required
                        value={confirmReason}
                      />
                    </label>
                    <DisabledReasonTooltip
                      actionId="CONFIRM_EVENT"
                      actions={assistantActions}
                      fallback={!selectedCanConfirm ? "Your role cannot confirm this event type." : ""}
                    >
                      <button
                        disabled={!selectedCanConfirm || !onConfirm || !actualAt || !confirmReason.trim() || isActionRunning}
                        title={!selectedCanConfirm ? "Your role cannot confirm this event type." : undefined}
                        type="submit"
                      >
                        Confirm event
                      </button>
                    </DisabledReasonTooltip>
                  </form>
                  <form onSubmit={submitReject}>
                    <label>
                      Rejection reason
                      <input
                        onChange={(event) => setRejectReason(event.target.value)}
                        required
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
                    <DisabledReasonTooltip
                      actionId="REJECT_EVENT"
                      actions={assistantActions}
                      fallback={!selectedCanConfirm ? "Your role cannot reject this event type." : ""}
                    >
                      <button
                        disabled={!selectedCanConfirm || !onReject || !rejectReason.trim() || isActionRunning}
                        title={!selectedCanConfirm ? "Your role cannot reject this event type." : undefined}
                        type="submit"
                      >
                        Reject event
                      </button>
                    </DisabledReasonTooltip>
                  </form>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="empty-state">
              <strong>No candidate selected</strong>
              <span>Replay or ingest an operational event to begin review.</span>
            </div>
          )}
        </aside>
      </div>

      <section className="board-surface confirmed-ledger-panel">
        <div className="grid-header">
          <div><SvgIcon name="audit" /><strong>Confirmed event ledger</strong></div>
          <span>Confirmed facts, reasons, actors, and schedule actualization</span>
        </div>
        <div className="grid-scroll">
          <table className="planning-table event-table">
            <thead>
              <tr>
                <th>Actual</th>
                <th>Event</th>
                <th>Trip</th>
                <th>Variance</th>
                <th>Reason</th>
                <th>Actor</th>
                <th>Mode</th>
              </tr>
            </thead>
            <tbody>
              {confirmedEvents.map((event) => {
                const variance = varianceMinutes(event.schedule_event_planned_at, event.actual_at);
                return (
                  <tr key={event.id}>
                    <td><GridDate value={event.actual_at} /></td>
                    <td><strong>{short(event.event_kind)}</strong></td>
                    <td>{event.trip_ref ?? "-"}</td>
                    <td className={`${tone(variance && variance > 15 ? "warning" : "confirmed")}-text`}>{varianceLabel(variance)}</td>
                    <td>{short(event.reason_code)}</td>
                    <td>{event.confirmed_by_email ?? "system"}</td>
                    <td><span className={`status-chip ${tone(event.confirmation_mode === "manual" ? "pending" : "confirmed")}`}>{short(event.confirmation_mode)}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!confirmedEvents.length ? (
            <div className="empty-state">
              <strong>No confirmed events yet</strong>
              <span>Confirmed operational facts will remain here after review.</span>
            </div>
          ) : null}
        </div>
      </section>
    </section>
  );
}
