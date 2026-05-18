import type { ReactNode } from "react";

import type { ActionRecommendation } from "../../types/assistant";
import { blockedReasonFor } from "./actionMatching";

type DisabledReasonTooltipProps = {
  actionId: string;
  actions?: ActionRecommendation[];
  children: ReactNode;
  fallback?: string;
};

export function DisabledReasonTooltip({
  actionId,
  actions = [],
  children,
  fallback = "",
}: DisabledReasonTooltipProps) {
  const reason = blockedReasonFor(actions, actionId) || fallback;

  if (!reason) return <>{children}</>;

  return (
    <span className="disabled-reason-tooltip" title={reason}>
      {children}
      <span className="disabled-reason-badge" aria-label={`Blocked reason: ${reason}`}>
        Blocked
      </span>
    </span>
  );
}
