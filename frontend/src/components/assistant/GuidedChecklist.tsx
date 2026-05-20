import type { AssistantChecklistItem, AssistantMode } from "../../types/assistant";
import { AbbrText } from "../Abbreviation";

type GuidedChecklistProps = {
  items?: AssistantChecklistItem[];
  limit?: number;
  mode?: AssistantMode;
  title?: string;
};

const STATUS_LABELS: Record<AssistantChecklistItem["status"], string> = {
  blocked: "Blocked",
  complete: "Done",
  current: "Now",
  pending: "Next",
};

export function GuidedChecklist({
  items = [],
  limit = 8,
  mode = "assisted",
  title,
}: GuidedChecklistProps) {
  const visibleItems = items.slice(0, limit);
  if (!visibleItems.length) return null;

  const activeItem =
    visibleItems.find((item) => item.status === "current" || item.status === "blocked")
    ?? visibleItems.find((item) => item.status === "pending")
    ?? visibleItems[0];
  const resolvedTitle = title
    ?? (mode === "guided" ? "Guided checklist preview" : "Lifecycle checklist");

  return (
    <section className={`guided-checklist ${mode}`}>
      <div className="guided-checklist-header">
        <span>{resolvedTitle}</span>
        <strong><AbbrText text={activeItem.label} /></strong>
      </div>
      <ol>
        {visibleItems.map((item) => (
          <li className={item.status} key={item.key}>
            <span className="guided-checklist-dot" aria-hidden="true" />
            <div>
              <strong><AbbrText text={item.label} /></strong>
              {item.reason ? <em><AbbrText text={item.reason} /></em> : null}
            </div>
            <small>{STATUS_LABELS[item.status]}</small>
          </li>
        ))}
      </ol>
    </section>
  );
}
