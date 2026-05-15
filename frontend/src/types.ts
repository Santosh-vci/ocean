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

