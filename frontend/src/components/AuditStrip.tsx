import type { AuditEvent } from "../types";

type AuditStripProps = {
  events: AuditEvent[];
  canViewAudit: boolean;
};

export function AuditStrip({ events, canViewAudit }: AuditStripProps) {
  return (
    <footer className="audit-strip">
      <div>
        <span>Audit</span>
        <strong>{canViewAudit ? `${events.length} recent events` : "restricted"}</strong>
      </div>
      {canViewAudit ? (
        <ol>
          {events.slice(0, 4).map((event) => (
            <li key={event.id}>
              <span>{event.action}</span>
              <strong>{event.object_repr || `${event.object_type}:${event.object_id}`}</strong>
            </li>
          ))}
        </ol>
      ) : (
        <p>Audit visibility is limited for this role.</p>
      )}
    </footer>
  );
}

