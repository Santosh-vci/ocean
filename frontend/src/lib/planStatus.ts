import type { ConflictRecord, TrackingAlertRecord } from "../types";

export function activePlanConflicts(
  conflicts: readonly ConflictRecord[] | null | undefined,
) {
  return (conflicts ?? []).filter((conflict) => !conflict.resolved_at);
}

export function activeTrackingAlerts(
  alerts: readonly TrackingAlertRecord[] | null | undefined,
) {
  return (alerts ?? []).filter((alert) => (
    alert.status === "open" || alert.status === "acknowledged"
  ));
}

export function primaryConflict(conflicts: readonly ConflictRecord[]) {
  return conflicts.find((conflict) => conflict.is_blocking)
    ?? conflicts.find((conflict) => conflict.severity === "critical")
    ?? conflicts[0];
}

export function activeConflictForTrip(
  conflicts: readonly ConflictRecord[] | null | undefined,
  tripId: number | null | undefined,
) {
  if (!tripId) return undefined;
  return primaryConflict(
    activePlanConflicts(conflicts).filter((conflict) => conflict.trip === tripId),
  );
}
