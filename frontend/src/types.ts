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
