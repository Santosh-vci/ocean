import { useEffect, useMemo, useState } from "react";

import type { NavModule } from "../lib/navigation";
import { SvgIcon } from "./SvgIcon";

type SidebarProps = {
  activePath: string;
  collapsed: boolean;
  modules: NavModule[];
  canOpenSystemAudit: boolean;
  canOpenTerminalSupport: boolean;
  onNavigate: (path: string) => void;
  onOpenSystemAudit: () => void;
  onOpenTerminalSupport: () => void;
  onToggleCollapsed: () => void;
};

export function Sidebar({
  activePath,
  collapsed,
  modules,
  canOpenSystemAudit,
  canOpenTerminalSupport,
  onNavigate,
  onOpenSystemAudit,
  onOpenTerminalSupport,
  onToggleCollapsed,
}: SidebarProps) {
  const activeModuleId = useMemo(
    () => modules.find((module) => module.items.some((item) => item.path === activePath))?.id,
    [activePath, modules],
  );
  const [openModuleIds, setOpenModuleIds] = useState<Set<string>>(
    () => new Set(modules.map((module) => module.id)),
  );

  useEffect(() => {
    if (!activeModuleId) {
      return;
    }
    setOpenModuleIds((previous) => new Set(previous).add(activeModuleId));
  }, [activeModuleId]);

  function toggleModule(moduleId: string) {
    setOpenModuleIds((previous) => {
      const next = new Set(previous);
      if (next.has(moduleId)) {
        next.delete(moduleId);
      } else {
        next.add(moduleId);
      }
      return next;
    });
  }

  return (
    <aside className={collapsed ? "sidebar collapsed" : "sidebar"}>
      <div className="brand-block">
        <div>
          <span>Coalflow</span>
          <strong>Tower</strong>
        </div>
        <button
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="sidebar-toggle"
          onClick={onToggleCollapsed}
          type="button"
        >
          <SvgIcon name={collapsed ? "chevron-right" : "chevron-left"} />
        </button>
      </div>

      <nav aria-label="Primary navigation" className="module-nav">
        {modules.map((module) => {
          const isOpen = openModuleIds.has(module.id) && !collapsed;
          const isActiveModule = module.id === activeModuleId;
          return (
            <section className={isActiveModule ? "nav-module active" : "nav-module"} key={module.id}>
              <button
                aria-expanded={isOpen}
                className="nav-module-trigger"
                onClick={() => toggleModule(module.id)}
                title={collapsed ? module.label : undefined}
                type="button"
              >
                <SvgIcon name={module.icon} />
                <span className="module-copy">
                  <strong>{module.label}</strong>
                  <em>{module.eyebrow}</em>
                </span>
                <SvgIcon name="chevron-down" className={isOpen ? "svg-icon open" : "svg-icon"} />
              </button>

              {isOpen ? (
                <div className="nav-submodule-list">
                  {module.items.map((item) => {
                    const className = [
                      "nav-item",
                      item.path === activePath ? "active" : "",
                      item.disabled ? "disabled" : "",
                    ]
                      .filter(Boolean)
                      .join(" ");
                    return (
                      <button
                        aria-disabled={item.disabled || undefined}
                        className={className}
                        key={item.path}
                        onClick={() => {
                          if (!item.disabled) {
                            onNavigate(item.path);
                          }
                        }}
                        type="button"
                      >
                        <SvgIcon name={item.icon} />
                        <span>{item.label}</span>
                      </button>
                    );
                  })}
                </div>
              ) : null}
            </section>
          );
        })}
      </nav>

      <div className="sidebar-support">
        <button
          disabled={!canOpenSystemAudit}
          onClick={onOpenSystemAudit}
          type="button"
          title={collapsed ? "System Audit" : undefined}
        >
          <SvgIcon name="audit" />
          <span>System Audit</span>
        </button>
        <button
          disabled={!canOpenTerminalSupport}
          onClick={onOpenTerminalSupport}
          type="button"
          title={collapsed ? "Terminal Support" : undefined}
        >
          <SvgIcon name="help" />
          <span>Terminal Support</span>
        </button>
      </div>
    </aside>
  );
}
