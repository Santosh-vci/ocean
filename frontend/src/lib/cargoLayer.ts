import type { CargoLayerStepRecord } from "../types";

const BLOCKING_STATUSES = new Set(["blocked", "qc_hold"]);

function formattedStatus(status: string) {
  return status.replaceAll("_", " ").toUpperCase();
}

export function cargoLayerNeedsRecovery(step: CargoLayerStepRecord) {
  return (
    step.sequence_violation
    || BLOCKING_STATUSES.has(step.status)
    || Boolean(step.blocking_reason.trim())
  );
}

export function cargoLayerSeverity(step: CargoLayerStepRecord) {
  if (step.sequence_violation) return "critical";
  if (BLOCKING_STATUSES.has(step.status)) return "pending";
  return "ok";
}

export function cargoLayerChainStatusLabel(step: CargoLayerStepRecord) {
  const rawChainStatus = step.chain_status.trim();

  if (cargoLayerNeedsRecovery(step)) {
    if (rawChainStatus) return rawChainStatus;
    return step.sequence_violation ? "SEQUENCE REVIEW" : "WAITING RECOVERY";
  }

  if (!rawChainStatus || rawChainStatus.toUpperCase() === "WAITING RECOVERY") {
    return step.status === "planned" ? "PLANNED" : formattedStatus(step.status);
  }

  return rawChainStatus;
}

export function cargoLayerRecoveryMessage(step: CargoLayerStepRecord) {
  if (!cargoLayerNeedsRecovery(step)) {
    return "No recovery needed for this layer.";
  }

  if (step.sequence_violation) {
    return "Confirm hatch and layer order before publishing.";
  }

  if (step.blocking_reason.trim().toLowerCase().includes("tide/bridge")) {
    return "Fix tide and bridge availability, then regenerate the plan.";
  }

  if (step.status === "qc_hold") {
    return "Clear the QC hold before publishing.";
  }

  return "Resolve the blocker, then review the plan before publishing.";
}
