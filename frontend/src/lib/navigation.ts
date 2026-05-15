export type NavItem = {
  path: string;
  label: string;
  group: string;
  requiredPermission: string;
};

export const NAV_ITEMS: NavItem[] = [
  {
    path: "/dashboard/situation",
    label: "Network Situation",
    group: "Control Tower",
    requiredPermission: "dashboard.view",
  },
  {
    path: "/admin/users-rbac",
    label: "Users & RBAC",
    group: "Admin",
    requiredPermission: "admin.view",
  },
  {
    path: "/admin/audit-logs",
    label: "Audit & Logs",
    group: "Admin",
    requiredPermission: "audit.view",
  },
];

export function canAccess(permissions: string[], requiredPermission: string): boolean {
  return permissions.includes("*") || permissions.includes(requiredPermission);
}

export function visibleNavItems(permissions: string[]): NavItem[] {
  return NAV_ITEMS.filter((item) => canAccess(permissions, item.requiredPermission));
}

