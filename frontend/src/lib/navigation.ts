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
  phase?: string;
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
        phase: "Chunk 3",
      },
      {
        path: "/schedule/coal-grade-sequence",
        label: "Coal Grade Sequence",
        module: "Planning",
        requiredPermission: "schedule.view",
        icon: "coal",
        phase: "Chunk 3",
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
        phase: "Chunk 3",
      },
    ],
  },
  {
    id: "operations",
    label: "Operations",
    eyebrow: "Chunk 4 boards",
    icon: "operations",
    items: [
      {
        path: "/operations/tug-barge-assignment",
        label: "Tug/Barge Assignment",
        module: "Operations",
        requiredPermission: "schedule.view",
        icon: "fleet",
        phase: "Chunk 4",
      },
      {
        path: "/operations/jetty-loading",
        label: "Jetty Loading",
        module: "Operations",
        requiredPermission: "schedule.view",
        icon: "locations",
        phase: "Chunk 4",
      },
      {
        path: "/operations/cts-floating-crane",
        label: "CTS / Floating Crane",
        module: "Operations",
        requiredPermission: "schedule.view",
        icon: "operations",
        phase: "Chunk 4",
      },
      {
        path: "/schedule/published-plan",
        label: "Published Plan & Schedule",
        module: "Operations",
        requiredPermission: "schedule.view",
        icon: "account-tree",
        phase: "Chunk 4",
      },
    ],
  },
  {
    id: "exceptions",
    label: "Recovery Loop",
    eyebrow: "Chunk 5 governance",
    icon: "rule",
    items: [
      {
        path: "/exceptions/center",
        label: "Exception Center",
        module: "Recovery Loop",
        requiredPermission: "schedule.view",
        icon: "rule",
        phase: "Chunk 5",
        disabled: true,
      },
      {
        path: "/simulation/workspace",
        label: "Simulation Workspace",
        module: "Recovery Loop",
        requiredPermission: "schedule.edit",
        icon: "account-tree",
        phase: "Chunk 5",
        disabled: true,
      },
      {
        path: "/approvals/publishing",
        label: "Approvals & Publishing",
        module: "Recovery Loop",
        requiredPermission: "schedule.approve",
        icon: "audit",
        phase: "Chunk 5",
        disabled: true,
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
        phase: "Chunk 6",
        disabled: true,
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
