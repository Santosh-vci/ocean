# Next Action Assist — Testing and Acceptance Plan

## 1. Test objective

Prove that the Next Action Assist layer is:

- deterministic
- permission-aware
- state-aware
- non-mutating from read endpoint
- correctly ranked
- correctly rendered
- aligned with existing workflow governance

---

## 2. Backend unit tests

### 2.1 Registry tests

File:

```text
backend/apps/assistant/tests/test_action_registry.py
```

Cases:

| Test | Expected result |
|---|---|
| Registry loads | No exception. |
| Action IDs unique | No duplicate IDs. |
| Required fields present | Every action has route, label, CTA, owner role. |
| Mutating actions audited | Mutating actions have `audit_required=true` unless explicitly exempted. |
| Required action IDs exist | All first-sprint IDs are present. |

### 2.2 Rule tests

File examples:

```text
backend/apps/assistant/tests/test_planning_rules.py
backend/apps/assistant/tests/test_exception_rules.py
backend/apps/assistant/tests/test_approval_publish_export_rules.py
backend/apps/assistant/tests/test_operations_event_rules.py
```

Cases:

| Business state | Expected top/page action |
|---|---|
| No active demand | `IMPORT_OGV_DEMAND` |
| Demand exists, no tide/bridge windows | `ENTER_OPERATING_WINDOWS` |
| Demand + windows, no active plan | `GENERATE_PLAN` |
| Active published plan and changes needed | `CREATE_DRAFT` |
| Editable stale plan | `REGENERATE_PLAN` |
| Blocking conflicts exist | `OPEN_EXCEPTION_CENTER` top ranked |
| Conflict exists, no scenario | `CREATE_SCENARIO` |
| Scenario has assumptions, no run | `RUN_SIMULATION` |
| Scenario improves risk | `PROMOTE_SCENARIO` |
| Feasible plan, no approval request | `SUBMIT_APPROVAL` |
| Current user has pending approval decision | `APPROVE_PLAN` |
| All approvals complete | `PUBLISH_PLAN` |
| Published plan, no export | `GENERATE_EXPORT` |
| Pending high-confidence event | `CONFIRM_EVENT` |
| Duplicate/noisy candidate | `REJECT_EVENT` |
| Stale telemetry signal | `REVIEW_SIGNAL_HEALTH` or `OPEN_EXCEPTION_CENTER` |

---

## 3. API tests

File:

```text
backend/apps/assistant/tests/test_next_actions_api.py
```

Cases:

| Test | Expected result |
|---|---|
| Unauthenticated request | 401/403 consistent with project auth. |
| Authenticated request | 200 with response schema. |
| `mode=off` | Empty/nonessential recommendation arrays. |
| `route=/dashboard/situation` | global + dashboard actions returned. |
| `route=/approvals/publishing` | approval/publish scoped actions returned. |
| `object_type=assignment&object_id=...` | row/object scoped action returned when eligible. |
| Unknown route | returns global recommendations, no crash. |
| Unknown object | returns no row actions, no crash. |
| Same seed state repeated | stable same top action. |
| No permission | enabled action omitted or moved to blocked actions. |

Response contract assertions:

```text
generated_at exists
mode exists
context exists
global_next_action is object/null
page_actions is list
row_actions is list
blocked_actions is list
checklist is list
all recommendations have action_id, label, priority, route, reason, source
```

---

## 4. Non-mutation test

The assistant endpoint must not write to database.

Approach:

1. Capture counts/checksums for relevant tables.
2. Call `/api/assistant/next-actions/`.
3. Re-check counts/checksums.
4. Assert no changes.

Tables to watch:

```text
plans / plan versions
trips
assignments
conflicts
overrides
approval requests
approval decisions
exports
operational event candidates
confirmed operational events
audit events
simulation scenarios
scenario runs
```

Audit events should not be created by read-only assistant calls unless the repo logs all reads by policy. If read audit exists, explicitly document that exception.

---

## 5. Ranking tests

Cases:

| State | Must outrank |
|---|---|
| Blocking conflict exists | `OPEN_EXCEPTION_CENTER` outranks `SUBMIT_APPROVAL`, `PUBLISH_PLAN`, `GENERATE_EXPORT` |
| Approval pending | `APPROVE_PLAN` outranks `PUBLISH_PLAN` |
| Published without export | `GENERATE_EXPORT` appears after publish, not before |
| High-confidence event candidate | `CONFIRM_EVENT` outranks low-priority `REVIEW_AUDIT` |
| Current plan published and change needed | `CREATE_DRAFT` outranks `REGENERATE_PLAN` |

---

## 6. Permission tests

Create users with representative roles:

```text
Berau Scheduler
ABL Dispatcher
Joint Control
Read-only Viewer
Admin
```

Cases:

| User | State | Expected |
|---|---|---|
| Read-only | plan ready to submit | no enabled `SUBMIT_APPROVAL`; blocked or hidden action only |
| Berau Scheduler | plan ready | `SUBMIT_APPROVAL` enabled if permission exists |
| ABL Dispatcher | approval pending for ABL | `APPROVE_PLAN` enabled |
| Berau Scheduler | approval pending for ABL only | no enabled `APPROVE_PLAN` |
| Joint Control | all approvals complete | `PUBLISH_PLAN` enabled |
| Viewer | published no export | no enabled `GENERATE_EXPORT` |

---

## 7. Frontend unit/component tests

Use the existing frontend test framework.

Cases:

### `NextActionPill`

- Hidden when action is null.
- Renders action label.
- Shows priority class.
- Calls `onNavigate(action.route)` when enabled.
- Does not navigate when disabled.
- Shows blocked reason when disabled.

### `ActionInboxPanel`

- Renders list of actions.
- Sorts or respects pre-sorted order.
- Shows reason and owner.
- Navigates on CTA.

### `RecommendationCard`

- Renders action, reason, impact, owner.
- Renders secondary actions.
- Handles null state gracefully.

### `DisabledReasonTooltip`

- Finds blocked action by action ID.
- Shows blocked reason.
- Leaves child button behavior untouched.

### `RowActionHint`

- Filters actions by target object.
- Shows no badge when no row action.

### `AssistantModeToggle`

- Reads/writes local storage.
- Allows off/assisted.
- Does not expose disabled modes as selectable unless implemented.

---

## 8. Frontend integration tests

Cases:

| Route | Expected assistive behavior |
|---|---|
| Dashboard | action inbox visible in assisted mode |
| OGV Demand | import/review guidance visible |
| Tide/Bridge | operating window/generate plan guidance visible |
| Tug/Barge | generate/regenerate guidance visible |
| Jetty | event/override/scenario guidance visible |
| Exception Center | create scenario/run/promote guidance visible |
| Simulation | run/promote/submit guidance visible |
| Approvals | approve/publish guidance visible |
| Export | export readiness guidance visible |

Mode behavior:

| Mode | Expected |
|---|---|
| assisted | global pill and page cards visible |
| off | assistive UI hidden except hard disabled reasons |

Error behavior:

| API state | Expected |
|---|---|
| assistant API 500 | page still renders, assistant area hidden or shows compact unavailable state |
| malformed response | no crash; log/ignore safely |
| slow response | loading placeholder only, no blocking |

---

## 9. End-to-end UAT scripts

### 9.1 Happy path

1. Log in as scheduler.
2. Dashboard recommends importing demand if no demand exists.
3. Import demand.
4. Assistant recommends reviewing coal sequence.
5. Review sequence.
6. Assistant recommends entering tide/bridge windows.
7. Enter windows.
8. Assistant recommends generating plan.
9. Generate plan.
10. If no blocking conflicts, assistant recommends submitting approval.
11. Submit approval.
12. Log in or switch role to approver.
13. Assistant recommends approval decision.
14. Approve.
15. Once all approvals complete, assistant recommends publish.
16. Publish.
17. Assistant recommends export.
18. Generate export.
19. Audit review is available as low-priority verification.

### 9.2 Blocking conflict path

1. Seed a plan with blocking conflict.
2. Dashboard top action is Exception Center.
3. Exception Center recommends creating scenario.
4. Create scenario.
5. Add assumption if required.
6. Run simulation.
7. If improved, promote scenario.
8. Submit approval after blockers cleared.

### 9.3 Event confirmation path

1. Seed high-confidence operational event candidate.
2. Event Console recommends confirm event.
3. Confirm event.
4. If actualization creates delay risk, assistant recommends Exception Center or scenario.
5. If candidate is duplicate/noisy, assistant recommends reject.

### 9.4 Published-plan change path

1. Publish a plan.
2. Introduce demand/constraint change.
3. Assistant recommends create draft, not regenerate directly.
4. Create draft.
5. Regenerate draft if needed.
6. Continue approval/publish lifecycle.

---

## 10. Acceptance definition

Implementation is complete when:

- backend assistant endpoint exists and is tested
- action registry covers first-sprint actions
- topbar/global next action works
- dashboard action inbox works
- page-level recommendation card works on at least Dashboard, Exception Center, Published Plan, Approvals, Tug/Barge, Tide/Bridge, Event Console, Export Handoff
- disabled reasons exist for publish, approval, regenerate, export, event confirm/reject where applicable
- mode off/assisted works
- no existing user action is broken
- all existing tests pass
- new tests pass
- documentation and registry are updated
