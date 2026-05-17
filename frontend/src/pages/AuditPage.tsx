import { useMemo, useState } from "react";

import { GridDate } from "../components/GridDate";
import type { AuditEvent } from "../types";

type AuditPageProps = {
  events: AuditEvent[];
};

export function AuditPage({ events }: AuditPageProps) {
  const [selectedEventId, setSelectedEventId] = useState<number>(events[0]?.id ?? 0);
  const selectedEvent = events.find((event) => event.id === selectedEventId) ?? events[0];
  const actorCount = useMemo(
    () => new Set(events.map((event) => event.actor?.email ?? "system")).size,
    [events],
  );
  const authEventCount = events.filter((event) => event.action.startsWith("auth.")).length;

  return (
    <section className="workspace-page audit-cockpit">
      <header className="page-heading">
        <div>
          <p>Admin</p>
          <h1>Audit & Logs</h1>
        </div>
        <span className="phase-chip secure">Audit write · Secure</span>
      </header>

      <div className="metric-strip four-up">
        <div>
          <span>Events</span>
          <strong>{events.length}</strong>
        </div>
        <div>
          <span>Actors</span>
          <strong>{actorCount}</strong>
        </div>
        <div>
          <span>Auth events</span>
          <strong>{authEventCount}</strong>
        </div>
        <div>
          <span>Audit health</span>
          <strong>Secure</strong>
        </div>
      </div>

      <div className="audit-layout">
        <section className="plain-section board-surface">
          <h2>Governance filters</h2>
          <div className="filter-strip">
            <span>All actions</span>
            <span>All actors</span>
            <span>Newest first</span>
          </div>

          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Object</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr
                  className={event.id === selectedEvent?.id ? "selected-row" : ""}
                  key={event.id}
                  onClick={() => setSelectedEventId(event.id)}
                >
                  <td><GridDate value={event.created_at} /></td>
                  <td>{event.actor?.email ?? "system"}</td>
                  <td>{event.action}</td>
                  <td>{event.object_repr || `${event.object_type}:${event.object_id}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {selectedEvent ? (
          <aside className="detail-drawer audit-drawer">
            <div>
              <span>Event details</span>
              <strong>{selectedEvent.action}</strong>
            </div>
            <dl>
              <div>
                <dt>Actor</dt>
                <dd>{selectedEvent.actor?.email ?? "system"}</dd>
              </div>
              <div>
                <dt>Object</dt>
                <dd>{selectedEvent.object_repr || selectedEvent.object_id}</dd>
              </div>
              <div>
                <dt>Request ID</dt>
                <dd>{selectedEvent.request_id ?? "—"}</dd>
              </div>
            </dl>
            <section>
              <h2>Governance traceability</h2>
              <ol className="trace-list">
                <li>
                  <GridDate value={selectedEvent.created_at} />
                  <strong>{selectedEvent.action}</strong>
                </li>
                <li>
                  <span>Object</span>
                  <strong>{selectedEvent.object_type}</strong>
                </li>
                <li>
                  <span>Archive</span>
                  <strong>Pending domain chain</strong>
                </li>
              </ol>
            </section>
            <section>
              <h2>Technical metadata</h2>
              <code>
                IP {selectedEvent.ip_address ?? "n/a"} · object {selectedEvent.object_id}
              </code>
            </section>
          </aside>
        ) : null}
      </div>
    </section>
  );
}
