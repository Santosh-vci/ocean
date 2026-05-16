import { useMemo, useState } from "react";

import { SvgIcon } from "../components/SvgIcon";
import type { ExportFormat, ExportJobRecord, ExportOverview, ExportType } from "../types";

type ExportCommand = {
  exportType: ExportType;
  exportFormat: ExportFormat;
};

type ExportHandoffPageProps = {
  overview: ExportOverview | null;
  canGenerate: boolean;
  isLoading: boolean;
  isGenerating: boolean;
  error: string | null;
  onGenerate: (command: ExportCommand) => Promise<void>;
};

const EMPTY_EXPORTS: ExportJobRecord[] = [];

const COMMANDS: Array<ExportCommand & { title: string; detail: string }> = [
  {
    exportType: "plan",
    exportFormat: "print",
    title: "Printable schedule",
    detail: "Operator-readable plan handoff for Berau/ABL coordination.",
  },
  {
    exportType: "plan",
    exportFormat: "csv",
    title: "Plan CSV",
    detail: "Trip, tug, barge, jetty, CTS, tonnage, and timing rows.",
  },
  {
    exportType: "conflict",
    exportFormat: "json",
    title: "Conflict pack",
    detail: "Open blocker register with plan version and trip context.",
  },
  {
    exportType: "audit",
    exportFormat: "json",
    title: "Audit evidence",
    detail: "Latest governed event chain, scoped by access policy.",
  },
];

function formatType(type: ExportType) {
  if (type === "plan") return "Plan";
  if (type === "conflict") return "Conflict";
  return "Audit";
}

function formatDate(value: string) {
  return new Date(value).toLocaleString(undefined, {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
  });
}

function sizeLabel(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024).toLocaleString()} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ExportHandoffPage({
  overview,
  canGenerate,
  isLoading,
  isGenerating,
  error,
  onGenerate,
}: ExportHandoffPageProps) {
  const exports = overview?.exports ?? EMPTY_EXPORTS;
  const [selectedExportId, setSelectedExportId] = useState<number | null>(exports[0]?.id ?? null);
  const selectedExport = useMemo(
    () => exports.find((item) => item.id === selectedExportId) ?? exports[0],
    [exports, selectedExportId],
  );
  const latestPlanExport = exports.find((item) => item.export_type === "plan");

  return (
    <section className="workspace-page export-handoff-board">
      <header className="page-heading planning-heading">
        <div>
          <p>Admin / Reporting & Handoff</p>
          <h1>Exports & Operational Handoff</h1>
        </div>
        <div className="planning-actions">
          <span className="phase-chip secure">Chunk 7 · Governed exports</span>
          <button disabled={!canGenerate || isGenerating} onClick={() => onGenerate({
            exportType: "plan",
            exportFormat: "print",
          })} type="button">
            Generate schedule
          </button>
        </div>
      </header>

      <div className="metric-strip four-up export-kpis">
        <div>
          <span>Total exports</span>
          <strong>{overview?.summary.total ?? 0}</strong>
        </div>
        <div>
          <span>Plan handoffs</span>
          <strong>{overview?.summary.plan ?? 0}</strong>
        </div>
        <div>
          <span>Conflict packs</span>
          <strong>{overview?.summary.conflict ?? 0}</strong>
        </div>
        <div>
          <span>Access scope</span>
          <strong>{overview?.scope.label ?? "Loading"}</strong>
        </div>
      </div>

      {error ? <div className="workspace-banner critical">{error}</div> : null}
      {!canGenerate ? (
        <div className="workspace-banner muted">
          Export visibility is enabled for this role; generation requires export.generate.
        </div>
      ) : null}

      <div className="export-layout">
        <section className="board-surface export-command-panel">
          <div className="grid-header">
            <div>
              <SvgIcon name="schedule" />
              <strong>Generate governed artifact</strong>
            </div>
            <span>Plan · conflict · audit</span>
          </div>
          <div className="export-command-list">
            {COMMANDS.map((command) => (
              <button
                disabled={!canGenerate || isGenerating || isLoading}
                key={`${command.exportType}-${command.exportFormat}`}
                onClick={() => onGenerate(command)}
                type="button"
              >
                <span>{formatType(command.exportType)} · {command.exportFormat.toUpperCase()}</span>
                <strong>{command.title}</strong>
                <em>{command.detail}</em>
              </button>
            ))}
          </div>
        </section>

        <section className="board-surface export-history-panel">
          <div className="grid-header">
            <div>
              <SvgIcon name="audit" />
              <strong>Import / export history</strong>
            </div>
            <span>{isLoading ? "Loading" : `${exports.length} visible artifacts`}</span>
          </div>

          <div className="grid-scroll export-history-scroll">
            {isLoading ? (
              <div className="empty-state">
                <strong>Loading export history</strong>
                <span>Fetching governed artifacts and storage checksums.</span>
              </div>
            ) : null}
            {!isLoading && exports.length === 0 ? (
              <div className="empty-state">
                <strong>No governed exports generated</strong>
                <span>Generate a schedule, conflict pack, or audit evidence file when handoff is needed.</span>
              </div>
            ) : null}
            {exports.length ? (
              <table className="planning-table">
                <thead>
                  <tr>
                    <th>Generated</th>
                    <th>Type</th>
                    <th>Format</th>
                    <th>Records</th>
                    <th>Storage object</th>
                    <th>Checksum</th>
                  </tr>
                </thead>
                <tbody>
                  {exports.map((item) => (
                    <tr
                      className={selectedExport?.id === item.id ? "selected-row" : ""}
                      key={item.id}
                      onClick={() => setSelectedExportId(item.id)}
                    >
                      <td>{formatDate(item.created_at)}</td>
                      <td><span className="status-chip ok">{formatType(item.export_type)}</span></td>
                      <td>{item.export_format.toUpperCase()}</td>
                      <td>{item.record_count.toLocaleString()}</td>
                      <td>{item.file_name}</td>
                      <td><code>{item.checksum_sha256.slice(0, 12)}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
          </div>
        </section>

        <aside className="board-surface export-detail-rail">
          <div className="grid-header">
            <div>
              <SvgIcon name="account-tree" />
              <strong>Handoff inspector</strong>
            </div>
            <span>{selectedExport?.status ?? "empty"}</span>
          </div>
          {selectedExport ? (
            <div className="export-inspector">
              <span className="status-chip ok">{formatType(selectedExport.export_type)}</span>
              <h2>{selectedExport.file_name}</h2>
              <p>
                Stored as {selectedExport.storage_uri}. Download URL is policy-gated and checksum-bound.
              </p>
              <dl>
                <div><dt>Plan version</dt><dd>{selectedExport.plan_version_ref ?? "n/a"}</dd></div>
                <div><dt>Records</dt><dd>{selectedExport.record_count.toLocaleString()}</dd></div>
                <div><dt>Size</dt><dd>{sizeLabel(selectedExport.size_bytes)}</dd></div>
                <div><dt>Scope</dt><dd>{selectedExport.scope.label}</dd></div>
                <div><dt>Created by</dt><dd>{selectedExport.created_by_email ?? "system"}</dd></div>
              </dl>
              <a href={selectedExport.download_url}>Download artifact</a>
            </div>
          ) : (
            <div className="export-inspector empty">
              <span className="status-chip pending">No file</span>
              <h2>Awaiting first handoff</h2>
              <p>
                {latestPlanExport
                  ? "Select an export row to inspect scope, checksum, and storage key."
                  : "No generated artifacts are visible for this access scope yet."}
              </p>
            </div>
          )}
        </aside>
      </div>
    </section>
  );
}
