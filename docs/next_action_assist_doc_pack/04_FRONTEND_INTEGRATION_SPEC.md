# Frontend Integration Specification — Next Action Assist

## 1. Objective

Integrate the backend Next Action Assist response into the existing React/Vite frontend without disrupting existing cockpit workflows.

The assistant should feel like an embedded operational guide:

- global next-action pill
- dashboard action inbox
- page-level recommendation card
- row-level hint where relevant
- disabled-button reasons
- optional guided checklist
- user-controlled mode toggle

---

## 2. New frontend files

Create:

```text
frontend/src/types/assistant.ts
frontend/src/hooks/useNextActions.ts
frontend/src/components/assistant/AssistantModeToggle.tsx
frontend/src/components/assistant/NextActionPill.tsx
frontend/src/components/assistant/ActionInboxPanel.tsx
frontend/src/components/assistant/RecommendationCard.tsx
frontend/src/components/assistant/DisabledReasonTooltip.tsx
frontend/src/components/assistant/GuidedChecklist.tsx
frontend/src/components/assistant/RowActionHint.tsx
frontend/src/components/assistant/index.ts
```

If the repo prefers keeping types in `frontend/src/types.ts`, add assistant types there instead of a new folder.

---

## 3. TypeScript types

```ts
export type AssistantMode = "off" | "assisted" | "guided" | "supervisor";
export type AssistantPriority = "critical" | "warning" | "normal" | "info";

export type ActionRecommendation = {
  actionId: string;
  label: string;
  priority: AssistantPriority;
  rankScore: number;
  enabled: boolean;
  route: string;
  ctaLabel: string;
  reason: string;
  hoverHint: string;
  detailText: string;
  impactIfIgnored: string;
  ownerRole: string;
  requiredPermission: string | null;
  auditRequired: boolean;
  targetObjectType: string | null;
  targetObjectId: string | null;
  blockedReason: string;
  source: string;
  expiresAt: string | null;
  metadata: Record<string, unknown>;
};

export type AssistantChecklistItem = {
  key: string;
  label: string;
  status: "complete" | "current" | "blocked" | "pending";
  actionId?: string;
  route?: string;
  reason?: string;
};

export type NextActionResponse = {
  generatedAt: string;
  mode: AssistantMode;
  context: Record<string, unknown>;
  globalNextAction: ActionRecommendation | null;
  pageActions: ActionRecommendation[];
  rowActions: ActionRecommendation[];
  blockedActions: ActionRecommendation[];
  checklist: AssistantChecklistItem[];
};
```

Backend returns snake_case. Either:

1. Add a frontend normalization function from snake_case to camelCase, or
2. Configure backend serializer to emit camelCase.

Given the existing frontend types use camelCase, prefer frontend normalization.

---

## 4. API integration

Add to `frontend/src/lib/api.ts`:

```ts
export type NextActionParams = {
  route?: string;
  objectType?: string;
  objectId?: string | number;
  mode?: AssistantMode;
};

export async function fetchNextActions(params: NextActionParams): Promise<NextActionResponse> {
  const query = new URLSearchParams();
  if (params.route) query.set("route", params.route);
  if (params.objectType) query.set("object_type", params.objectType);
  if (params.objectId !== undefined) query.set("object_id", String(params.objectId));
  if (params.mode) query.set("mode", params.mode);

  const suffix = query.toString() ? `?${query.toString()}` : "";
  const raw = await apiFetch<unknown>(`/assistant/next-actions/${suffix}`);
  return normalizeNextActionResponse(raw);
}
```

---

## 5. Hook: `useNextActions`

```ts
export function useNextActions(route: string, options?: { objectType?: string; objectId?: string | number }) {
  const [mode, setMode] = useAssistantMode();
  const [data, setData] = useState<NextActionResponse | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (mode === "off") {
      setData(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    fetchNextActions({ route, mode, objectType: options?.objectType, objectId: options?.objectId })
      .then((response) => {
        if (!cancelled) setData(response);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err : new Error("Assistant unavailable"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [route, mode, options?.objectType, options?.objectId]);

  return { mode, setMode, data, error, loading };
}
```

Fail closed: if API fails, do not block existing screens.

---

## 6. Assistant mode storage

First build:

```ts
const ASSISTANT_MODE_KEY = "ocean.assistantMode";
```

Default:

```text
assisted
```

Mode toggle options:

```text
Off
Assisted
Guided (disabled or preview until implemented)
Supervisor (disabled unless role supports it)
```

---

## 7. Components

### 7.1 `NextActionPill`

Placement: shell/topbar area in `App.tsx` or `Topbar.tsx`.

Props:

```ts
type Props = {
  action: ActionRecommendation | null;
  onNavigate: (route: string) => void;
};
```

Behavior:

- Hidden if mode off or no action.
- Shows priority tone and short label.
- On click navigates to `action.route`.
- If `enabled=false`, show disabled reason instead of navigation.

Text example:

```text
Next: Resolve blocking conflicts
```

### 7.2 `ActionInboxPanel`

Placement: `DashboardPage.tsx`.

Props:

```ts
type Props = {
  actions: ActionRecommendation[];
  onNavigate: (route: string) => void;
};
```

Behavior:

- Shows top 3–5 page/global recommendations.
- Groups by priority.
- Shows owner role and reason.

### 7.3 `RecommendationCard`

Placement: each major page header/right rail.

Props:

```ts
type Props = {
  title?: string;
  action: ActionRecommendation | null;
  secondaryActions?: ActionRecommendation[];
  onNavigate: (route: string) => void;
};
```

Content:

```text
Recommended next action
Action
Reason
Impact if ignored
Owner
CTA
```

### 7.4 `DisabledReasonTooltip`

Wrap existing disabled buttons when matching blocked action exists.

Props:

```ts
type Props = {
  actionId: string;
  blockedActions: ActionRecommendation[];
  children: ReactNode;
};
```

Behavior:

- Find blocked action by `actionId`.
- Show `blockedReason` or `reason` in title/popover.
- Do not change existing button handler.

### 7.5 `RowActionHint`

For assignment rows, event candidates, conflicts, alerts.

Props:

```ts
type Props = {
  objectType: string;
  objectId: string | number;
  rowActions: ActionRecommendation[];
};
```

Behavior:

- Match by target object.
- Show small icon/badge with hover hint.
- Do not clutter dense tables.

### 7.6 `GuidedChecklist`

Initial implementation can be read-only if guided mode is deferred.

Checklist stages:

```text
Demand imported
Cargo sequence reviewed
Operating windows entered
Plan generated
Exceptions resolved
Approval submitted
Approval completed
Plan published
Export generated
```

---

## 8. Integration in `App.tsx`

Current `App.tsx` owns:

- route state
- current user
- action handlers
- page rendering
- workspace sync
- success/error banners

Add assistant hook near current route state:

```ts
const assistant = useNextActions(activePath);
```

Pass to `Topbar` or render near shell:

```tsx
<NextActionPill
  action={assistant.data?.globalNextAction ?? null}
  onNavigate={handleNavigate}
/>
```

Add mode toggle:

```tsx
<AssistantModeToggle mode={assistant.mode} onChange={assistant.setMode} />
```

Pass `assistant.data?.pageActions`, `blockedActions`, `rowActions`, `checklist` into page props only where integrated.

Avoid refactoring all pages in one pass. Add optional props.

---

## 9. Page-by-page integration

### 9.1 Dashboard

Add `ActionInboxPanel` below KPI strip or right rail.

Actions:

```text
globalNextAction + pageActions
```

### 9.2 OGV Demand

Add `RecommendationCard` in header:

- If no demand: import demand.
- If demand exists: review coal sequence.

Wrap Import Demand disabled button with `DisabledReasonTooltip` for `IMPORT_OGV_DEMAND`.

### 9.3 Coal Grade Sequence

Add recommendation card:

- Review/fix sequence.
- Enter tide/bridge windows next if sequence is ready.

### 9.4 Tide/Bridge

Add recommendation card near planning actions:

- Enter operating windows.
- Regenerate/generate plan once windows are ready.
- Open Exception Center if actuals/constraint checks create blockers.

### 9.5 Tug/Barge Assignment

Add page recommendation:

- Generate/regenerate plan.
- Open exceptions if blocked.

Add row hints for assignments using target object type `assignment`.

### 9.6 Jetty Loading

Add page recommendation:

- Confirm high-confidence event.
- Avoid/allow force start with explanation.
- Create scenario when actualization creates downstream risk.

Wrap force-start action with disabled reason and caution copy.

### 9.7 CTS / Floating Crane

Add page recommendation:

- Confirm discharge event.
- Create scenario if CTS rate variance is critical.

### 9.8 Published Plan

Add page recommendation:

- Create draft if current plan published and change exists.
- Submit approval if generated/validated and no blockers.
- Generate export if already published.

Wrap submit approval disabled state with `SUBMIT_APPROVAL` reason.

### 9.9 Exception Center

Add action inbox by exception source:

- Create scenario.
- Run simulation.
- Promote scenario.

Each selected conflict/alert/override detail panel should include recommended next action.

### 9.10 Simulation Workspace

Add `GuidedChecklist` or recommendation card:

- Add assumption.
- Run simulation.
- Promote scenario.
- Submit approval.

### 9.11 Approvals

Add recommendation card:

- Approve/reject if current user has pending decision.
- Publish if all approvals complete.

Reject should be shown as a secondary action unless the plan is invalid or has critical risk.

### 9.12 Map

Add unobtrusive hint:

- Review stale signal.
- Open Exception Center for critical alert.
- Create scenario from alert if allowed.

### 9.13 Event Confirmation

Add row-level hints:

- Confirm high-confidence candidate.
- Reject duplicate/noisy candidate.
- Manual review for conflicts.

### 9.14 Export Handoff

Add recommendation:

- Generate final schedule export only after publish.
- Generate conflict/scenario/audit export for internal review when allowed.

### 9.15 Audit Logs

Add low-priority verification hint after governed mutation:

- Review audit trail.
- Filter by correlation/request/object.

---

## 10. Styling guidance

Use existing cockpit styling.

Recommended CSS classes:

```css
.assistant-pill
.assistant-card
.assistant-card.critical
.assistant-card.warning
.assistant-card.normal
.assistant-card.info
.assistant-action-inbox
.assistant-row-hint
.assistant-disabled-reason
.assistant-mode-toggle
.assistant-checklist
```

Keep density high:

- no oversized cards
- compact text
- one clear CTA
- short reason first, detail on hover/expand

---

## 11. UX copy rules

Use direct operational language.

Good:

```text
Next action: Submit approval.
Reason: The generated plan has no blocking conflicts.
```

Bad:

```text
You may want to consider submitting this for approval if you think everything looks good.
```

Blocked action copy:

```text
Publish disabled: ABL approval is still pending.
```

Governed action copy:

```text
This action will be audited and may change downstream tide/bridge risk.
```

---

## 12. Frontend tests

Add tests for:

1. `NextActionPill` hidden when no action.
2. `NextActionPill` navigates to route when enabled.
3. Blocked action does not navigate and shows reason.
4. Dashboard renders action inbox.
5. Assisted mode can be switched off.
6. API failure does not crash page.
7. Disabled reason tooltip finds matching blocked action.
8. RowActionHint filters by target object.

---

## 13. Implementation sequence

1. Add assistant types and API client.
2. Add hook and local storage mode.
3. Add basic components.
4. Render global pill in shell.
5. Render dashboard inbox.
6. Add recommendation card to Published Plan and Approvals.
7. Add Exception Center and Simulation guidance.
8. Add operational page row hints.
9. Add CSS polish.
10. Add tests.
