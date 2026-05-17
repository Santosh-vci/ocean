export type Organization = {
  id: number;
  name: string;
  slug: string;
  kind: string;
  is_active: boolean;
};

export type DataScope = {
  id: number;
  name: string;
  code: string;
  scope_type: string;
  organization: Organization | null;
  rules: Record<string, unknown>;
  is_active: boolean;
};

export type AccessPermission = {
  id: number;
  code: string;
  module: string;
  action: string;
  description: string;
};

export type Role = {
  id: number;
  name: string;
  code: string;
  description: string;
  organization: Organization | null;
  permissions: AccessPermission[];
  is_system_role: boolean;
  is_active: boolean;
};

export type Membership = {
  organization: Organization;
  title: string;
  is_default: boolean;
  is_active: boolean;
};

export type Assignment = {
  role: Role;
  organization: Organization;
  data_scope: DataScope;
  is_active: boolean;
};

export type UserSummary = {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  memberships: Membership[];
  assignments: Assignment[];
};

export type CurrentUser = UserSummary & {
  permissions: string[];
};

export type AuditEvent = {
  id: number;
  actor: {
    id: number;
    username: string;
    email: string;
  } | null;
  organization: Organization | null;
  action: string;
  object_type: string;
  object_id: string;
  object_repr: string;
  metadata: Record<string, unknown>;
  request_id: string | null;
  ip_address: string | null;
  created_at: string;
};

export type DashboardTone = "ok" | "pending" | "critical";

export type DashboardKpi = {
  key: string;
  label: string;
  value: string | number;
  unit?: string;
  detail: string;
  tone: DashboardTone;
  href: string;
};

export type DashboardPlanVersion = {
  id: number;
  planCode: string;
  planName: string;
  versionNo: number;
  status: string;
  validationStatus: string;
  generatedAt: string | null;
  publishedAt: string | null;
  liveSnapshotId: string | null;
  liveVersionNo: number | null;
};

export type DashboardRoleShape = {
  profile: string;
  organizationName: string;
  organizationKind: string;
  dataScope: string;
  sections: Record<string, boolean>;
  redactions: string[];
};

export type DashboardResourceRow = {
  label: string;
  tripId: string;
  status: string;
  start: string;
  end: string;
  tone: DashboardTone;
  offsetPct: number;
  widthPct: number;
};

export type DashboardReadModel = {
  generatedAt: string;
  roleShape: DashboardRoleShape;
  latestVersion: DashboardPlanVersion | null;
  kpis: DashboardKpi[];
  planRisk: {
    riskScore: number;
    tone: DashboardTone;
    blockingConflicts: number;
    criticalConflicts: number;
    warningConflicts: number;
    highestRiskOgv: {
      tripId?: string | null;
      vesselName: string;
      detail: string;
      tone: DashboardTone;
    };
    mostConstrainedResource: {
      label: string;
      code?: string;
      count: number;
      tone: DashboardTone;
    };
    firstBlockingConstraint: string;
    publishState: string;
    liveLabel: string;
  };
  queuePressure: {
    peakResource: string;
    summary: string;
    tone: DashboardTone;
    href: string;
    jetties: Array<{ code: string; queuedTrips: number; tone: DashboardTone }>;
    cts: Array<{ code: string; queuedTrips: number; tone: DashboardTone }>;
    fleet: {
      activeTugs: number;
      totalTugs: number;
      activeBarges: number;
      totalBarges: number;
      activeCts: number;
      totalCts: number;
      tugBargePairs: number;
      blockedAssets: number;
    };
    navigationRisk: {
      openTideBridgeConflicts: number;
      label: string;
    };
  };
  conflictAggregation: Array<{
    code: string;
    severity: string;
    objectType: string;
    total: number;
    blocking: number;
    tone: DashboardTone;
    href: string;
  }>;
  priorityActions: Array<{
    label: string;
    detail: string;
    severity: string;
    href: string;
    sourceType: string;
    sourceId: number | null;
  }>;
  resourceTimeline: Array<{
    category: string;
    rows: DashboardResourceRow[];
  }>;
  drilldowns: Array<{
    label: string;
    href: string;
    detail: string;
  }>;
};

export type RbacOverview = {
  users: UserSummary[];
  roles: Role[];
  permissions: AccessPermission[];
  organizations: Organization[];
  scopes: DataScope[];
  assignmentCount: number;
  auditEventCount: number;
};



export type MasterRecordBase = {
  id: number;
  code: string;
  name: string;
  organization: Organization | null;
  is_active: boolean;
  effective_from: string | null;
  effective_to: string | null;
  created_at: string;
  updated_at: string;
};

export type LocationRecord = MasterRecordBase & {
  location_type: string;
  latitude: string;
  longitude: string;
  geofence_radius_m: number;
  parent_area: string;
  operational_notes: string;
};

export type CoalGradeRecord = MasterRecordBase & {
  brand_family: string;
  typical_cv_kcal: number | null;
  sulfur_pct: string | null;
  ash_pct: string | null;
  sequence_priority: number;
};

export type MineRecord = MasterRecordBase & {
  region: string;
  default_haul_distance_km: string | null;
};

export type StockpileRecord = MasterRecordBase & {
  mine: number;
  mine_code: string;
  coal_grade: number;
  coal_grade_code: string;
  available_quantity_mt: number;
  reserved_quantity_mt: number;
};

export type JettyRecord = MasterRecordBase & {
  location_name: string;
  loading_rate_tph: number;
  max_barge_draft_m: string | null;
  status: string;
};

export type TugRecord = MasterRecordBase & {
  horsepower: number;
  bollard_pull_tonnes: string;
  ais_mmsi: string;
  gps_device_id: string;
  status: string;
};

export type BargeRecord = MasterRecordBase & {
  capacity_mt: number;
  barge_class: string;
  max_draft_m: string | null;
  status: string;
};

export type CTSAssetRecord = MasterRecordBase & {
  cts_type: string;
  daily_capacity_mt: number;
  operating_area: string;
  is_available: boolean;
};

export type RouteSegmentRecord = {
  id: number;
  route: number;
  sequence: number;
  from_location: string;
  to_location: string;
  distance_nm: string;
  loaded_duration_minutes: number;
  empty_duration_minutes: number;
  requires_tide_window: boolean;
  requires_bridge_window: boolean;
};

export type RouteRecord = MasterRecordBase & {
  origin: string;
  destination: string;
  default_loaded_duration_minutes: number;
  default_empty_duration_minutes: number;
  segments: RouteSegmentRecord[];
};

export type LoadingRateProfileRecord = MasterRecordBase & {
  resource_type: string;
  resource_code: string;
  coal_grade: number | null;
  coal_grade_code: string | null;
  rate_tph: number;
};

export type CompatibilityRuleRecord = MasterRecordBase & {
  rule_type: string;
  left_code: string;
  right_code: string;
  is_compatible: boolean;
  reason: string;
};

export type MasterDataRecord =
  | LocationRecord
  | CoalGradeRecord
  | MineRecord
  | StockpileRecord
  | JettyRecord
  | TugRecord
  | BargeRecord
  | CTSAssetRecord
  | RouteRecord
  | LoadingRateProfileRecord
  | CompatibilityRuleRecord;

export type MasterDataCatalogs = {
  locations: LocationRecord[];
  coalGrades: CoalGradeRecord[];
  mines: MineRecord[];
  stockpiles: StockpileRecord[];
  jetties: JettyRecord[];
  tugs: TugRecord[];
  barges: BargeRecord[];
  ctsAssets: CTSAssetRecord[];
  routes: RouteRecord[];
  loadingRateProfiles: LoadingRateProfileRecord[];
  compatibilityRules: CompatibilityRuleRecord[];
};

export type MasterDataOverview = {
  catalogs: MasterDataCatalogs;
  validation: {
    inactiveRecords: number;
    blockingRules: number;
    missingGpsDevices: number;
  };
};

export type OGVVoyageRecord = {
  id: number;
  voyage_id: string;
  vessel_name: string;
  customer_name: string;
  vessel_class: string;
  eta: string;
  etb: string | null;
  etc_target: string | null;
  laycan_start: string;
  laycan_end: string;
  required_mt: number;
  loaded_mt: number;
  in_transit_mt: number;
  discharged_mt: number;
  remaining_mt: number;
  priority: number;
  demurrage_rate_usd_per_day: string;
  anchorage_location: LocationRecord | null;
  organization: Organization | null;
  status: string;
  risk_status: string;
  current_stage: string;
  next_blocking_constraint: string;
  created_at: string;
  updated_at: string;
};

export type CargoRequirementRecord = {
  id: number;
  voyage: number;
  voyage_ref: string;
  vessel_name: string;
  coal_grade: CoalGradeRecord;
  source_location: LocationRecord | null;
  preferred_jetty: JettyRecord | null;
  required_mt: number;
  loaded_mt: number;
  in_transit_mt: number;
  discharged_mt: number;
  remaining_mt: number;
  status: string;
  created_at: string;
  updated_at: string;
};

export type CargoLayerStepRecord = {
  id: number;
  voyage: number;
  voyage_ref: string;
  vessel_name: string;
  cargo_requirement: number | null;
  hatch_no: number;
  layer_no: number;
  required_sequence_no: number;
  coal_grade: CoalGradeRecord;
  required_mt: number;
  remaining_mt: number;
  planned_barge: BargeRecord | null;
  planned_jetty: JettyRecord | null;
  planned_cts: CTSAssetRecord | null;
  status: string;
  blocking_reason: string;
  chain_status: string;
  sequence_violation: boolean;
  planned_start: string | null;
  planned_end: string | null;
  created_at: string;
  updated_at: string;
};

export type AssetAvailabilityWindowRecord = {
  id: number;
  asset_type: string;
  asset_code: string;
  window_start: string;
  window_end: string;
  status: string;
  reason: string;
  created_at: string;
  updated_at: string;
};

export type JettyAvailabilityWindowRecord = {
  id: number;
  jetty: JettyRecord;
  window_start: string;
  window_end: string;
  status: string;
  loading_rate_override_tph: number | null;
  reason: string;
  created_at: string;
  updated_at: string;
};

export type TideWindowRecord = {
  id: number;
  code: string;
  location: LocationRecord;
  window_start: string;
  window_end: string;
  min_water_level_m: string;
  max_loaded_draft_m: string;
  applicable_route_segment: RouteSegmentRecord | null;
  risk_level: string;
  source: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BridgeWindowRecord = {
  id: number;
  code: string;
  location: LocationRecord;
  window_start: string;
  window_end: string;
  clearance_m: string;
  allowed_asset_class: string;
  status: string;
  notes: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type NavigationConstraintCheckRecord = {
  id: number;
  voyage: number;
  voyage_ref: string;
  vessel_name: string;
  asset_code: string;
  route_segment: RouteSegmentRecord | null;
  constraint_type: string;
  eta_gate: string;
  window_start: string;
  window_end: string;
  draft_m: string | null;
  margin_minutes: number;
  status: string;
  recovery_hint: string;
  created_at: string;
  updated_at: string;
};

export type ImportJobRecord = {
  id: number;
  import_type: string;
  filename: string;
  source: string;
  status: string;
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  errors: Array<Record<string, unknown>>;
  created_by: number | null;
  created_by_email: string | null;
  created_at: string;
};

export type PlanningOverview = {
  voyages: OGVVoyageRecord[];
  cargoRequirements: CargoRequirementRecord[];
  cargoLayerSteps: CargoLayerStepRecord[];
  assetAvailability: AssetAvailabilityWindowRecord[];
  jettyAvailability: JettyAvailabilityWindowRecord[];
  tideWindows: TideWindowRecord[];
  bridgeWindows: BridgeWindowRecord[];
  constraintChecks: NavigationConstraintCheckRecord[];
  importJobs: ImportJobRecord[];
  validation: {
    highRiskVoyages: number;
    sequenceViolations: number;
    missedWindows: number;
    activeDemandMt: number;
    remainingDemandMt: number;
  };
};

export type PlanRecord = {
  id: number;
  code: string;
  name: string;
  organization: Organization | null;
  horizon_start: string;
  horizon_end: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type PlanVersionRecord = {
  id: number;
  plan: number;
  plan_code: string;
  plan_name: string;
  version_no: number;
  status: string;
  validation_status: string;
  source_version: number | null;
  generated_at: string | null;
  published_at: string | null;
  created_by: number | null;
  created_by_email: string | null;
  summary: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ScheduleEventRecord = {
  id: number;
  trip: number;
  trip_ref: string;
  sequence: number;
  event_type: string;
  planned_at: string;
  actual_at: string | null;
  location_label: string;
  resource_code: string;
  status: string;
  metadata: Record<string, unknown>;
};

export type AssignmentRecord = {
  id: number;
  trip: number;
  trip_ref: string;
  voyage_ref: string;
  vessel_name: string;
  planned_quantity_mt: number;
  tug: TugRecord | null;
  barge: BargeRecord | null;
  jetty: JettyRecord | null;
  cts: CTSAssetRecord | null;
  route_segment: number | null;
  owner_organization: Organization | null;
  planned_departure: string;
  planned_arrival: string;
  tug_status: string;
  barge_status: string;
  next_constraint: string;
  next_action: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type TripRecord = {
  id: number;
  plan_version: number;
  plan_version_ref: string;
  trip_id: string;
  sequence: number;
  voyage: OGVVoyageRecord;
  cargo_requirement: CargoRequirementRecord | null;
  cargo_layer_step: CargoLayerStepRecord | null;
  origin_jetty: JettyRecord | null;
  destination_location: number | null;
  planned_start: string;
  planned_end: string;
  planned_quantity_mt: number;
  loaded_quantity_mt: number;
  status: string;
  selection_reason: Record<string, unknown>;
  assignment: AssignmentRecord | null;
  events: ScheduleEventRecord[];
  created_at: string;
  updated_at: string;
};

export type ConflictRecord = {
  id: number;
  plan_version: number;
  plan_version_ref: string;
  trip: number | null;
  trip_ref: string | null;
  vessel_name: string | null;
  code: string;
  severity: string;
  object_type: string;
  object_id: string;
  message: string;
  is_blocking: boolean;
  resolved_at: string | null;
  created_at: string;
};

export type ImpactChainNodeRecord = {
  id: string;
  type: string;
  label: string;
  value: string;
  status: "ok" | "warning" | "critical" | string;
  detail: string;
  plannedAt?: string | null;
  projectedAt?: string | null;
  windowStart?: string | null;
  windowEnd?: string | null;
  marginMinutes?: number | null;
  missMinutes?: number | null;
};

export type ImpactChainAssessmentRecord = {
  id: number;
  assessment_id: string;
  plan_version: number;
  plan_version_ref: string;
  trip: number | null;
  trip_ref: string | null;
  assignment: number | null;
  assignment_ref: string | null;
  override_request: number | null;
  override_request_ref: string | null;
  source_kind: string;
  status: "ok" | "warning" | "critical" | string;
  delay_minutes: number;
  nodes: ImpactChainNodeRecord[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type OverrideRequestRecord = {
  id: number;
  plan_version: number;
  plan_version_ref: string;
  trip: number | null;
  trip_ref: string | null;
  vessel_name: string | null;
  assignment: number | null;
  reason_code: string;
  description: string;
  requested_change: Record<string, unknown>;
  before_state: Record<string, unknown>;
  after_state: Record<string, unknown>;
  status: string;
  requested_by: number | null;
  requested_by_email: string | null;
  applied_by: number | null;
  applied_by_email: string | null;
  applied_at: string | null;
  impact_assessment: ImpactChainAssessmentRecord | null;
  created_at: string;
};

export type ApprovalDecisionRecord = {
  id: number;
  approval_request: number;
  authority_role: string;
  decision: string;
  comments: string;
  actor: number | null;
  actor_email: string | null;
  organization: number | null;
  organization_name: string | null;
  created_at: string;
};

export type ApprovalRequestRecord = {
  id: number;
  request_id: string;
  plan_version: number;
  plan_version_ref: string;
  status: string;
  required_authorities: string[];
  reason: string;
  requested_by: number | null;
  requested_by_email: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
  decisions: ApprovalDecisionRecord[];
};

export type PublishedPlanSnapshotRecord = {
  id: number;
  snapshot_id: string;
  plan: number;
  plan_code: string;
  plan_version: number;
  plan_version_ref: string;
  approval_request: number | null;
  status: string;
  payload: Record<string, unknown>;
  published_by: number | null;
  published_by_email: string | null;
  published_at: string;
};

export type ExportType = "plan" | "conflict" | "audit";
export type ExportFormat = "json" | "csv" | "print";

export type ExportJobRecord = {
  id: number;
  export_id: string;
  export_type: ExportType;
  export_format: ExportFormat;
  status: string;
  plan_version: number | null;
  plan_version_ref: string | null;
  organization: number | null;
  organization_name: string | null;
  storage_bucket: string;
  storage_key: string;
  storage_uri: string;
  file_name: string;
  content_type: string;
  checksum_sha256: string;
  size_bytes: number;
  record_count: number;
  scope: {
    scope_type: string;
    label: string;
    organization_id: number | null;
    organization_name: string | null;
    redactions: string[];
  };
  payload: Record<string, unknown>;
  failure_reason: string;
  created_by: number | null;
  created_by_email: string | null;
  created_at: string;
  download_url: string;
};

export type ExportOverview = {
  summary: {
    total: number;
    plan: number;
    conflict: number;
    audit: number;
  };
  scope: {
    scope_type: string;
    label: string;
    organization_id: number | null;
    organization_name: string | null;
    redactions: string[];
  };
  canGenerate: boolean;
  allowedTypes: Array<{ value: ExportType; label: string }>;
  allowedFormats: ExportFormat[];
  exports: ExportJobRecord[];
};

export type SimulationScenarioRecord = {
  id: number;
  scenario_id: string;
  name: string;
  scenario_type: string;
  baseline_version: number;
  baseline_version_ref: string;
  scenario_version: number | null;
  scenario_version_ref: string | null;
  source_conflict: number | null;
  source_conflict_code: string | null;
  source_conflict_message: string | null;
  source_override: number | null;
  source_override_reason_code: string | null;
  source_override_description: string | null;
  source_kind: "manual" | "conflict" | "override" | string;
  status: string;
  recovery_actions: string[];
  impact_summary: Record<string, unknown>;
  delta_summary: Record<string, unknown>;
  created_by: number | null;
  created_by_email: string | null;
  assumptions: ScenarioAssumptionRecord[];
  runs: ScenarioRunRecord[];
  created_at: string;
  updated_at: string;
};

export type ScenarioAssumptionRecord = {
  id: number;
  scenario: number;
  scenario_ref: string;
  assumption_id: string;
  kind: string;
  scope_type: string;
  scope_id: number | null;
  payload: Record<string, unknown>;
  effective_from: string | null;
  effective_to: string | null;
  created_by: number | null;
  created_by_email: string | null;
  created_at: string;
  updated_at: string;
};

export type ScenarioRunRecord = {
  id: number;
  scenario: number;
  scenario_ref: string;
  run_id: string;
  baseline_version: number;
  baseline_version_ref: string;
  status: string;
  algorithm_version: string;
  input_hash: string;
  started_at: string | null;
  completed_at: string | null;
  summary: Record<string, unknown>;
  created_by: number | null;
  created_by_email: string | null;
  created_at: string;
  updated_at: string;
};

export type SchedulingOverview = {
  plans: PlanRecord[];
  planVersions: PlanVersionRecord[];
  activePlanVersion: PlanVersionRecord | null;
  trips: TripRecord[];
  assignments: AssignmentRecord[];
  events: ScheduleEventRecord[];
  conflicts: ConflictRecord[];
  overrideRequests: OverrideRequestRecord[];
  approvalRequests: ApprovalRequestRecord[];
  publishedSnapshots: PublishedPlanSnapshotRecord[];
  simulationScenarios: SimulationScenarioRecord[];
  validation: {
    tripCount: number;
    assignmentCount: number;
    eventCount: number;
    conflictCount: number;
    blockingConflictCount: number;
    criticalConflictCount: number;
    overrideCount: number;
    approvalPendingCount: number;
    scenarioCount: number;
    plannedMt: number;
    loadedMt: number;
  };
};
