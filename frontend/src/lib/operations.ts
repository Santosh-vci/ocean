import type {
  ConfirmedOperationalEventRecord,
  OperationalEventCandidateRecord,
  TripRecord,
} from "../types";

export type OperationalExceptionRecord = {
  id: string;
  source: "event_candidate" | "confirmed_event";
  severity: "warning" | "critical";
  code: string;
  title: string;
  message: string;
  raisedAt: string;
  assetCode: string;
  assetType: string;
  tripId: number | null;
  tripRef: string | null;
  vesselName: string | null;
  eventKind: string;
  candidate: OperationalEventCandidateRecord | null;
  confirmedEvent: ConfirmedOperationalEventRecord | null;
  varianceMinutes: number | null;
  nextAction: string;
};

export const JETTY_EVENT_KINDS = [
  "jetty_loading_started",
  "jetty_loading_completed",
  "jetty_departed",
] as const;

export const CTS_EVENT_KINDS = [
  "cts_arrived",
  "cts_discharge_started",
  "cts_rate_updated",
  "cts_discharge_completed",
] as const;

export const BRIDGE_EVENT_KINDS = [
  "bridge_opened",
  "bridge_closed",
  "bridge_crossed",
] as const;

export const TIDE_EVENT_KINDS = [
  "tide_level_observed",
  "tide_gate_passed",
] as const;

export function shortOperationalLabel(value: string | null | undefined) {
  return value ? value.replaceAll("_", " ").toUpperCase() : "-";
}

export function operationalVarianceMinutes(
  plannedAt: string | null | undefined,
  observedAt: string | null | undefined,
) {
  if (!plannedAt || !observedAt) return null;
  const planned = new Date(plannedAt);
  const observed = new Date(observedAt);
  if (Number.isNaN(planned.getTime()) || Number.isNaN(observed.getTime())) return null;
  return Math.round((observed.getTime() - planned.getTime()) / 60000);
}

export function operationalVarianceLabel(value: number | null) {
  if (value === null) return "No match";
  return `${value > 0 ? "+" : ""}${value}m`;
}

export function latestCandidate(
  candidates: OperationalEventCandidateRecord[],
  predicate: (candidate: OperationalEventCandidateRecord) => boolean,
) {
  return candidates
    .filter(predicate)
    .sort((left, right) => (
      new Date(right.event_at).getTime() - new Date(left.event_at).getTime()
    ))[0] ?? null;
}

export function latestConfirmedEvent(
  events: ConfirmedOperationalEventRecord[],
  predicate: (event: ConfirmedOperationalEventRecord) => boolean,
) {
  return events
    .filter(predicate)
    .sort((left, right) => (
      new Date(right.actual_at).getTime() - new Date(left.actual_at).getTime()
    ))[0] ?? null;
}

export function confirmedEventForCandidate(
  events: ConfirmedOperationalEventRecord[],
  candidateId: number | null | undefined,
) {
  return events.find((event) => event.candidate === candidateId) ?? null;
}

function numericPayload(payload: Record<string, unknown>, key: string) {
  const value = payload[key];
  if (typeof value === "number") return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function tripContext(trips: TripRecord[], tripId: number | null | undefined) {
  const trip = trips.find((item) => item.id === tripId);
  return {
    vesselName: trip?.voyage.vessel_name ?? null,
    tripRef: trip?.trip_id ?? null,
  };
}

export function deriveOperationalExceptions(
  candidates: OperationalEventCandidateRecord[],
  confirmedEvents: ConfirmedOperationalEventRecord[],
  trips: TripRecord[],
) {
  const rows: OperationalExceptionRecord[] = [];

  confirmedEvents.forEach((event) => {
    const variance = operationalVarianceMinutes(event.schedule_event_planned_at, event.actual_at);
    const context = tripContext(trips, event.trip);
    if (event.event_kind === "jetty_loading_completed" && variance !== null && variance > 15) {
      rows.push({
        id: `confirmed-${event.id}`,
        source: "confirmed_event",
        severity: variance > 30 ? "critical" : "warning",
        code: "LOADING_COMPLETE_LATE",
        title: "Loading complete late",
        message: `${event.asset_code || "Jetty"} completed loading ${variance} minutes after plan.`,
        raisedAt: event.confirmed_at,
        assetCode: event.asset_code || "-",
        assetType: event.asset_type || "jetty",
        tripId: event.trip,
        tripRef: event.trip_ref ?? context.tripRef,
        vesselName: context.vesselName,
        eventKind: event.event_kind,
        candidate: null,
        confirmedEvent: event,
        varianceMinutes: variance,
        nextAction: "Review",
      });
    }
  });

  candidates.forEach((candidate) => {
    const context = tripContext(trips, candidate.trip);
    if (candidate.status === "pending" && candidate.event_kind === "cts_rate_updated") {
      const plannedRate = numericPayload(candidate.payload, "planned_rate_tph");
      rows.push({
        id: `candidate-${candidate.id}`,
        source: "event_candidate",
        severity: "warning",
        code: "CTS_LOW_RATE_CANDIDATE",
        title: "CTS low-rate candidate",
        message: plannedRate
          ? `${candidate.asset_code} reported a low-rate candidate against ${plannedRate.toLocaleString()} TPH planned.`
          : `${candidate.asset_code} reported a low-rate candidate pending confirmation.`,
        raisedAt: candidate.received_at,
        assetCode: candidate.asset_code || "-",
        assetType: candidate.asset_type || "cts",
        tripId: candidate.trip,
        tripRef: candidate.trip_ref ?? context.tripRef,
        vesselName: context.vesselName,
        eventKind: candidate.event_kind,
        candidate,
        confirmedEvent: null,
        varianceMinutes: operationalVarianceMinutes(
          candidate.schedule_event_planned_at,
          candidate.event_at,
        ),
        nextAction: "Confirm",
      });
    }

    if (candidate.status === "pending" && candidate.event_kind === "tide_level_observed") {
      const observed = numericPayload(candidate.payload, "observed_level_m");
      const threshold = numericPayload(candidate.payload, "threshold_m");
      if (observed !== null && threshold !== null && observed < threshold) {
        rows.push({
          id: `candidate-${candidate.id}`,
          source: "event_candidate",
          severity: "critical",
          code: "TIDE_SENSOR_BELOW_THRESHOLD",
          title: "Tide below threshold",
          message: `${candidate.asset_code} observed ${observed.toFixed(2)}m against ${threshold.toFixed(2)}m threshold.`,
          raisedAt: candidate.received_at,
          assetCode: candidate.asset_code || "-",
          assetType: candidate.asset_type || "tide_gate",
          tripId: candidate.trip,
          tripRef: candidate.trip_ref ?? context.tripRef,
          vesselName: context.vesselName,
          eventKind: candidate.event_kind,
          candidate,
          confirmedEvent: null,
          varianceMinutes: null,
          nextAction: "Review",
        });
      }
    }

    if (candidate.status === "pending" && candidate.event_kind === "bridge_closed") {
      rows.push({
        id: `candidate-${candidate.id}`,
        source: "event_candidate",
        severity: "critical",
        code: "BRIDGE_CLOSED_UNEXPECTEDLY",
        title: "Bridge closed unexpectedly",
        message: `${candidate.asset_code} reported a bridge-closed candidate pending review.`,
        raisedAt: candidate.received_at,
        assetCode: candidate.asset_code || "-",
        assetType: candidate.asset_type || "bridge",
        tripId: candidate.trip,
        tripRef: candidate.trip_ref ?? context.tripRef,
        vesselName: context.vesselName,
        eventKind: candidate.event_kind,
        candidate,
        confirmedEvent: null,
        varianceMinutes: null,
        nextAction: "Review",
      });
    }
  });

  return rows.sort((left, right) => (
    new Date(right.raisedAt).getTime() - new Date(left.raisedAt).getTime()
  ));
}
