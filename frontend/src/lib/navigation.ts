export type IconName =
  | "account-tree"
  | "apps"
  | "audit"
  | "bell"
  | "chevron-down"
  | "chevron-left"
  | "chevron-right"
  | "coal"
  | "dashboard"
  | "fleet"
  | "help"
  | "locations"
  | "map"
  | "operations"
  | "organization"
  | "rule"
  | "schedule"
  | "search"
  | "settings"
  | "sync";

export type NavItem = {
  path: string;
  label: string;
  module: string;
  requiredPermission: string;
  icon: IconName;
  disabled?: boolean;
};

export type NavModule = {
  id: string;
  label: string;
  eyebrow: string;
  icon: IconName;
  items: NavItem[];
};

export const NAV_MODULES: NavModule[] = [
  {
    id: "control-tower",
    label: "Control Tower",
    eyebrow: "Live overview",
    icon: "dashboard",
    items: [
      {
        path: "/dashboard/situation",
        label: "Network Situation",
        module: "Control Tower",
        requiredPermission: "dashboard.view",
        icon: "dashboard",
      },
    ],
  },
  {
    id: "planning",
    label: "Planning",
    eyebrow: "Demand & sequence",
    icon: "schedule",
    items: [
      {
        path: "/schedule/ogv-demand",
        label: "OGV Demand & Laycan",
        module: "Planning",
        requiredPermission: "schedule.view",
        icon: "schedule",
      },
      {
        path: "/schedule/coal-grade-sequence",
        label: "Coal Grade Sequence",
        module: "Planning",
        requiredPermission: "schedule.view",
        icon: "coal",
      },
    ],
  },
  {
    id: "constraints",
    label: "Constraints",
    eyebrow: "Navigation feasibility",
    icon: "rule",
    items: [
      {
        path: "/constraints/tide-bridge",
        label: "Tide & Bridge Window",
        module: "Constraints",
        requiredPermission: "schedule.view",
        icon: "rule",
      },
    ],
  },
  {
    id: "operations",
    label: "Operations",
    eyebrow: "Execution boards",
    icon: "operations",
    items: [
      {
        path: "/operations/tug-barge-assignment",
        label: "Tug/Barge Assignment",
        module: "Operations",
        requiredPermission: "schedule.view",
        icon: "fleet",
      },
      {
        path: "/operations/jetty-loading",
        label: "Jetty Loading",
        module: "Operations",
        requiredPermission: "schedule.view",
        icon: "locations",
      },
      {
        path: "/operations/cts-floating-crane",
        label: "CTS / Floating Crane",
        module: "Operations",
        requiredPermission: "schedule.view",
        icon: "operations",
      },
      {
        path: "/schedule/published-plan",
        label: "Published Plan & Schedule",
        module: "Operations",
        requiredPermission: "schedule.view",
        icon: "account-tree",
      },
    ],
  },
  {
    id: "exceptions",
    label: "Recovery Loop",
    eyebrow: "Governance loop",
    icon: "rule",
    items: [
      {
        path: "/exceptions/center",
        label: "Exception Center",
        module: "Recovery Loop",
        requiredPermission: "schedule.view",
        icon: "rule",
      },
      {
        path: "/simulation/workspace",
        label: "Simulation Workspace",
        module: "Recovery Loop",
        requiredPermission: "schedule.edit",
        icon: "account-tree",
      },
      {
        path: "/approvals/publishing",
        label: "Approvals & Publishing",
        module: "Recovery Loop",
        requiredPermission: "schedule.approve",
        icon: "audit",
      },
    ],
  },
  {
    id: "map",
    label: "Map & Signals",
    eyebrow: "MVP-lite",
    icon: "map",
    items: [
      {
        path: "/map/live",
        label: "Live Resource Map",
        module: "Map & Signals",
        requiredPermission: "fleet.view",
        icon: "map",
      },
    ],
  },
  {
    id: "admin",
    label: "Admin Console",
    eyebrow: "Configured truth",
    icon: "settings",
    items: [
      {
        path: "/admin/master-data",
        label: "Master Data Console",
        module: "Admin Console",
        requiredPermission: "masterdata.view",
        icon: "settings",
      },
      {
        path: "/admin/users-rbac",
        label: "Users & RBAC",
        module: "Admin Console",
        requiredPermission: "admin.view",
        icon: "organization",
      },
      {
        path: "/admin/audit-logs",
        label: "Audit & Logs",
        module: "Admin Console",
        requiredPermission: "audit.view",
        icon: "audit",
      },
      {
        path: "/admin/export-handoff",
        label: "Exports & Handoff",
        module: "Admin Console",
        requiredPermission: "export.view",
        icon: "account-tree",
      },
    ],
  },
];

export function canAccess(permissions: string[], requiredPermission: string): boolean {
  return permissions.includes("*") || permissions.includes(requiredPermission);
}

export function visibleNavModules(permissions: string[]): NavModule[] {
  return NAV_MODULES.map((module) => ({
    ...module,
    items: module.items.filter((item) => canAccess(permissions, item.requiredPermission)),
  })).filter((module) => module.items.length > 0);
}

export function visibleNavItems(permissions: string[]): NavItem[] {
  return visibleNavModules(permissions)
    .flatMap((module) => module.items)
    .filter((item) => !item.disabled);
}
