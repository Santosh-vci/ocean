import type { NavItem } from "../lib/navigation";

type SidebarProps = {
  activePath: string;
  items: NavItem[];
  onNavigate: (path: string) => void;
};

export function Sidebar({ activePath, items, onNavigate }: SidebarProps) {
  const groupedItems = items.reduce<Record<string, NavItem[]>>((groups, item) => {
    groups[item.group] ??= [];
    groups[item.group].push(item);
    return groups;
  }, {});

  return (
    <aside className="sidebar">
      <div className="brand-block">
        <span>Coalflow</span>
        <strong>Tower</strong>
      </div>

      <nav aria-label="Primary navigation">
        {Object.entries(groupedItems).map(([group, groupItems]) => (
          <section key={group} className="nav-group">
            <p>{group}</p>
            {groupItems?.map((item) => (
              <button
                className={item.path === activePath ? "nav-item active" : "nav-item"}
                key={item.path}
                onClick={() => onNavigate(item.path)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </section>
        ))}
      </nav>
    </aside>
  );
}
