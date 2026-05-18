# Next Action Assist — Governance and Change Control

## 1. Purpose

This governance document ensures that the assistant remains aligned with the operational workflow as future code additions, route changes, business rules, roles, or buttons are introduced.

The assistant is part of the operating model, not a decorative UI feature. Any change to workflow must update assistant governance.

---

## 2. Core governance principle

Every user-facing action must answer:

```text
Who can do it?
When is it allowed?
When is it blocked?
What state changes does it cause?
Is it audited?
What should the assistant recommend before/after it?
```

No mutating UI action should exist outside this governance.

---

## 3. Change-control checklist for new features

When adding a new page, route, button, backend action, status, exception type, approval type, telemetry alert, export type, or simulation operation, the implementing agent must update this checklist.

### 3.1 For a new route/page

Required updates:

- Add route to assistant route ownership table.
- Decide whether page needs global, page, row, checklist, or disabled-reason guidance.
- Add page-specific assistant props/components if applicable.
- Add route filter behavior to `/api/assistant/next-actions/`.
- Add tests showing route-specific recommendations.

### 3.2 For a new mutating button

Required updates:

- Add or map an `action_id` in the registry.
- Define permission.
- Define eligible states.
- Define blocked states.
- Define audit requirement.
- Define route and CTA label.
- Add disabled reason.
- Add backend rule if it should be recommended.
- Add frontend mapping if it should be rendered.
- Add tests.

### 3.3 For a new status/state

Required updates:

- Update assistant context selectors.
- Update eligibility/blocked-state logic for affected actions.
- Update checklist state mapping.
- Add regression tests proving old states still work.

### 3.4 For a new permission/role

Required updates:

- Update owner roles and required permissions in registry.
- Update permission shaping tests.
- Confirm users without permission see blocked explanation or no action as appropriate.
- Confirm users with permission see enabled CTA.

### 3.5 For a new exception/conflict type

Required updates:

- Decide severity mapping.
- Decide whether it recommends Exception Center, scenario, event confirmation, override, approval block, or audit review.
- Add rule source ID.
- Add route/object target.
- Add impact text.
- Add test with fixture/seed data.

### 3.6 For a new simulation capability

Required updates:

- Add or update scenario action IDs.
- Define assumption readiness logic.
- Define run readiness logic.
- Define promotion safety logic.
- Add “do not promote” blocked reason for unsafe scenario.
- Add tests for successful and unsafe promotion.

### 3.7 For approval/publish changes

Required updates:

- Update required authority logic.
- Update publish readiness rule.
- Update top-action ranking so publish never outranks unresolved blockers.
- Update audit text.
- Add tests.

---

## 4. Assistant registry ownership

The action registry is a governed artifact.

Rules:

1. Action IDs are permanent once used in UI/tests/audit metadata.
2. Do not rename action IDs. Deprecate and alias if needed.
3. Do not duplicate actions with slightly different names.
4. Prefer expanding metadata over creating a new action for the same business intent.
5. Every action must have a single default route.
6. Every action must have at least one owner role.
7. Every mutating action must declare audit requirement.
8. Every action must define blocked states.

---

## 5. Recommendation rule governance

Rules must be:

- deterministic
- explainable
- testable
- source-tagged
- permission-shaped
- non-mutating
- stable across repeated calls for same state

Every rule must include:

```text
rule_id
input state
condition
emitted action_id
priority
rank score
reason
impact if ignored
```

Example:

```text
Rule ID: exceptions.blocking_conflicts
Condition: active plan has blocking_conflict_count > 0
Action: OPEN_EXCEPTION_CENTER
Priority: critical
Reason: The active plan has unresolved blocking conflicts.
Impact: Approval/publish cannot safely proceed.
```

---

## 6. Ranking governance

The assistant must follow this priority ladder:

1. Safety / operational blockers
2. Governance blockers
3. Active event confirmation / actualization risk
4. Exception recovery / simulation
5. Approval/publish actions
6. Export actions
7. Audit verification
8. Informational guidance

Specific hard rules:

- `OPEN_EXCEPTION_CENTER` for blocking conflict outranks `SUBMIT_APPROVAL`.
- `APPROVE_PLAN` outranks `PUBLISH_PLAN` until all approvals are complete.
- `PUBLISH_PLAN` outranks `GENERATE_EXPORT` until published.
- `CONFIRM_EVENT` outranks low-priority audit review when event is high confidence.
- `CREATE_DRAFT` must be recommended before regeneration if current plan is published.
- Final schedule export must not be recommended before publish unless explicitly internal/draft export.

---

## 7. UI governance

### 7.1 Expert mode respect

If mode is `off`:

- hide global pill
- hide action inbox
- hide recommendation cards
- hide guided checklist
- keep hard disabled reasons where they prevent confusion

### 7.2 Assisted mode behavior

If mode is `assisted`:

- show one global next action
- show page recommendation card if available
- show dashboard action inbox
- show disabled button explanations
- show row hints only where compact

### 7.3 Guided mode behavior

If mode is `guided`:

- show checklist
- highlight current step
- preserve ability to skip/exit guidance
- do not prevent expert navigation unless action is truly blocked by business state

### 7.4 Supervisor mode behavior

If mode is `supervisor`:

- show cross-role pending actions
- show owner and SLA
- avoid mutating CTAs unless supervisor has direct permission
- emphasize bottleneck ownership rather than operator button-clicking

---

## 8. Copy governance

Assistant copy must be:

- short
- direct
- operational
- specific
- state-backed
- non-speculative

Required phrasing pattern:

```text
Next action: <action>.
Reason: <state-backed explanation>.
Impact: <business consequence if ignored>.
Owner: <role>.
```

Avoid:

```text
Maybe
Probably
You might want to
The system thinks
AI recommends
```

Use:

```text
Recommended
Blocked
Required
Ready
Pending
```

---

## 9. Audit and compliance governance

For all `audit_required=true` actions:

- recommendation metadata should include the source rule ID
- UI must mention that action is governed if action directly mutates state
- resulting backend mutation must continue using existing audit infrastructure
- audit logs should show the actual action, not merely assistant recommendation
- do not log sensitive internal reasoning text unless useful and safe

Recommended metadata on mutation payloads when applicable:

```json
{
  "assistant_action_id": "PROMOTE_SCENARIO",
  "assistant_source_rule": "scenario.promotable",
  "assistant_recommendation_generated_at": "..."
}
```

This is optional in first implementation, but useful for future explainability.

---

## 10. CI governance checks

Add tests or static checks to enforce:

1. All registry action IDs are unique.
2. All emitted action IDs exist in registry.
3. Every mutating action has `audit_required=true` or explicit justification.
4. Every route in navigation has a route ownership mapping or explicit exemption.
5. Every button marked with `data-action-id` references a registry action.
6. No top-ranked recommendation is disabled.
7. Blocking conflicts prevent publish/export top recommendations.
8. Assistant endpoint never writes to database.

Optional static frontend pattern:

```tsx
<button data-action-id="SUBMIT_APPROVAL" ...>
```

Then CI can scan for new `data-action-id` values and compare registry.

---

## 11. Documentation governance

When assistant behavior changes, update:

- `02_ACTION_REGISTRY.md`
- backend registry code
- rule tests
- frontend integration tests
- operator manual/runbook if visible to users

Do not update code without docs for workflow-affecting changes.

---

## 12. Release governance

Before releasing assistant changes:

1. Run backend tests.
2. Run frontend tests.
3. Run existing phase proof commands if applicable.
4. Validate seeded happy path:
   - demand import
   - windows entry
   - plan generation
   - conflict triage
   - simulation
   - approval
   - publish
   - export
5. Validate seeded exception path:
   - high-confidence event
   - override risk
   - blocking conflict
   - stale signal
6. Capture screenshots for Dashboard, Exception Center, Approvals, Event Console, Export Handoff.

---

## 13. Future LLM governance

If LLM explanation is added later:

- LLM may summarize/explain deterministic recommendations.
- LLM must not choose the action.
- LLM must not invent target objects.
- LLM must not override permission shaping.
- LLM output must be bounded by registry fields and selected state facts.
- LLM failure must degrade to deterministic copy.
- LLM prompt must include only safe, minimal, relevant operational context.

Allowed:

```text
Explain why ENTER_OPERATING_WINDOWS is required in plain language.
```

Not allowed:

```text
Decide what the dispatcher should do next from raw database state.
```
