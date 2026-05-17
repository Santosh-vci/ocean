import { useEffect, useMemo, useState } from "react";

import { SvgIcon } from "../components/SvgIcon";
import type { IconName } from "../lib/navigation";
import type {
  MasterDataCatalogs,
  MasterDataOverview,
  MasterDataRecord,
  Organization,
  RouteSegmentRecord,
} from "../types";

type CatalogKey = keyof MasterDataCatalogs;

type CatalogConfig = {
  key: CatalogKey;
  label: string;
  module: string;
  icon: IconName;
  columns: string[];
};

const CATALOGS: CatalogConfig[] = [
  {
    key: "tugs",
    label: "Tugs",
    module: "Fleet Master",
    icon: "fleet",
    columns: ["status", "code", "name", "ais_mmsi", "owner", "capacity", "device", "validation"],
  },
  {
    key: "barges",
    label: "Barges",
    module: "Fleet Master",
    icon: "fleet",
    columns: ["status", "code", "name", "owner", "capacity", "draft", "validation"],
  },
  {
    key: "ctsAssets",
    label: "CTS / Floating Crane",
    module: "Fleet Master",
    icon: "operations",
    columns: ["status", "code", "name", "type", "area", "capacity", "validation"],
  },
  {
    key: "locations",
    label: "Locations",
    module: "Route & Geofence",
    icon: "locations",
    columns: ["status", "code", "name", "type", "area", "latitude", "longitude", "validation"],
  },
  {
    key: "jetties",
    label: "Jetties",
    module: "Route & Geofence",
    icon: "locations",
    columns: ["status", "code", "name", "location", "rate", "draft", "validation"],
  },
  {
    key: "routes",
    label: "Routes & Segments",
    module: "Route & Geofence",
    icon: "map",
    columns: ["status", "code", "name", "origin", "destination", "segments", "validation"],
  },
  {
    key: "coalGrades",
    label: "Coal Grades",
    module: "Coal & Cargo",
    icon: "coal",
    columns: ["status", "code", "name", "family", "cv", "sulfur", "priority", "validation"],
  },
  {
    key: "mines",
    label: "Mines",
    module: "Coal & Cargo",
    icon: "coal",
    columns: ["status", "code", "name", "region", "haul", "validation"],
  },
  {
    key: "stockpiles",
    label: "Stockpiles",
    module: "Coal & Cargo",
    icon: "coal",
    columns: ["status", "code", "name", "mine", "grade", "available", "reserved", "validation"],
  },
  {
    key: "loadingRateProfiles",
    label: "Loading Rates",
    module: "Constraints",
    icon: "rule",
    columns: ["status", "code", "name", "resource", "grade", "rate", "validation"],
  },
  {
    key: "compatibilityRules",
    label: "Compatibility Rules",
    module: "Constraints",
    icon: "rule",
    columns: ["status", "code", "name", "rule", "left", "right", "validation"],
  },
];

const MODULE_ORDER = ["Fleet Master", "Route & Geofence", "Coal & Cargo", "Constraints"];

function organizationLabel(organization: Organization | null | undefined) {
  return organization?.slug?.toUpperCase() ?? "SHARED";
}

function recordValue(record: MasterDataRecord, key: string) {
  const source = record as unknown as Record<string, unknown>;
  switch (key) {
    case "status":
      return "status" in source ? String(source.status).toUpperCase() : record.is_active ? "ACTIVE" : "DRAFT";
    case "owner":
      return organizationLabel(record.organization);
    case "capacity":
      if ("horsepower" in source) return `${source.horsepower}HP`;
      if ("capacity_mt" in source) return `${source.capacity_mt}MT`;
      if ("daily_capacity_mt" in source) return `${source.daily_capacity_mt}MT/D`;
      return "-";
    case "device":
      return String(source.gps_device_id || source.ais_mmsi || "UNMAPPED");
    case "draft":
      return String(source.max_draft_m || source.max_barge_draft_m || "-");
    case "type":
      return String(source.cts_type || source.location_type || "-").replaceAll("_", " ").toUpperCase();
    case "area":
      return String(source.operating_area || source.parent_area || "-");
    case "location":
      return String(source.location_name || "-");
    case "rate":
      return source.rate_tph ? `${source.rate_tph} TPH` : source.loading_rate_tph ? `${source.loading_rate_tph} TPH` : "-";
    case "origin":
    case "destination":
    case "region":
      return String(source[key] || "-");
    case "segments":
      return Array.isArray(source.segments) ? source.segments.length : "-";
    case "family":
      return String(source.brand_family || "-");
    case "cv":
      return source.typical_cv_kcal ? `${source.typical_cv_kcal} KCAL` : "-";
    case "sulfur":
      return source.sulfur_pct ? `${source.sulfur_pct}%` : "-";
    case "priority":
      return String(source.sequence_priority || "-");
    case "haul":
      return source.default_haul_distance_km ? `${source.default_haul_distance_km} KM` : "-";
    case "mine":
      return String(source.mine_code || "-");
    case "grade":
      return String(source.coal_grade_code || "-");
    case "available":
      return source.available_quantity_mt ? `${source.available_quantity_mt} MT` : "-";
    case "reserved":
      return source.reserved_quantity_mt ? `${source.reserved_quantity_mt} MT` : "-";
    case "resource":
      return `${String(source.resource_type || "-").toUpperCase()} ${source.resource_code || ""}`;
    case "rule":
      return String(source.rule_type || "-").replaceAll("_", " /").toUpperCase();
    case "left":
      return String(source.left_code || "-");
    case "right":
      return String(source.right_code || "-");
    case "latitude":
    case "longitude":
      return String(source[key] || "-");
    case "validation":
      return validationState(record).label;
    default:
      return String(source[key] || "-");
  }
}

function validationState(record: MasterDataRecord): { label: string; tone: "ok" | "pending" | "critical" } {
  const source = record as unknown as Record<string, unknown>;
  if (!record.is_active) return { label: "INACTIVE", tone: "pending" };
  if ("gps_device_id" in source && !source.gps_device_id) return { label: "ISSUES", tone: "pending" };
  if ("is_compatible" in source && source.is_compatible === false) return { label: "BLOCKING", tone: "critical" };
  if ("status" in source && ["degraded", "maintenance", "breakdown", "blocked"].includes(String(source.status))) {
    return { label: "WARNING", tone: "pending" };
  }
  return { label: "PASSED", tone: "ok" };
}

function statusTone(record: MasterDataRecord) {
  const state = validationState(record);
  if (state.tone === "critical") return "critical";
  if (state.tone === "pending") return "pending";
  return "ok";
}

function fieldRows(record: MasterDataRecord) {
  const source = record as unknown as Record<string, unknown>;
  return [
    ["Unique identifier", record.code],
    ["Owner", organizationLabel(record.organization)],
    ["Effective from", record.effective_from ?? "Immediate"],
    ["Effective to", record.effective_to ?? "Open"],
    ["Operational status", recordValue(record, "status")],
    ["Primary capacity", recordValue(record, "capacity")],
    ["Location / Area", recordValue(record, "area") !== "-" ? recordValue(record, "area") : recordValue(record, "location")],
    ["Device / route ref", recordValue(record, "device") !== "UNMAPPED" ? recordValue(record, "device") : String(source.origin || source.resource_code || "Manual")],
  ];
}

function routeSegments(record: MasterDataRecord): RouteSegmentRecord[] {
  const segments = (record as { segments?: unknown }).segments;
  return Array.isArray(segments) ? segments as RouteSegmentRecord[] : [];
}

type MasterDataPageProps = {
  overview: MasterDataOverview;
  canManage: boolean;
  isActionRunning: boolean;
  onExportCatalog: (catalogKey: CatalogKey) => void;
  onImportCatalog: (catalogKey: CatalogKey, selectedRecord: MasterDataRecord | null) => void;
  onValidateCatalog: (catalogKey: CatalogKey) => void;
};

export function MasterDataPage({
  overview,
  canManage,
  isActionRunning,
  onExportCatalog,
  onImportCatalog,
  onValidateCatalog,
}: MasterDataPageProps) {
  const [activeCatalogKey, setActiveCatalogKey] = useState<CatalogKey>("tugs");
  const [selectedRecordId, setSelectedRecordId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const activeCatalog = CATALOGS.find((catalog) => catalog.key === activeCatalogKey) ?? CATALOGS[0];
  const records = overview.catalogs[activeCatalog.key] as MasterDataRecord[];
  const filteredRecords = useMemo(
    () =>
      records.filter((record) =>
        `${record.code} ${record.name} ${organizationLabel(record.organization)}`
          .toLowerCase()
          .includes(query.toLowerCase()),
      ),
    [query, records],
  );
  const selectedRecord =
    filteredRecords.find((record) => record.id === selectedRecordId) ?? filteredRecords[0] ?? null;
  const selectedRouteSegments = selectedRecord ? routeSegments(selectedRecord) : [];
  const totalRecords = Object.values(overview.catalogs).reduce((sum, catalog) => sum + catalog.length, 0);
  const activeRecords = Object.values(overview.catalogs).reduce(
    (sum, catalog) => sum + catalog.filter((record) => record.is_active).length,
    0,
  );

  useEffect(() => {
    setSelectedRecordId(filteredRecords[0]?.id ?? null);
  }, [activeCatalogKey, filteredRecords]);

  return (
    <section className="workspace-page master-data-console">
      <header className="page-heading master-heading">
        <div>
          <p>Admin Console</p>
          <h1>Master Data Console</h1>
        </div>
        <div className="master-actions">
          <label className="master-search">
            <SvgIcon name="search" />
            <input
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search Master Data..."
              type="search"
              value={query}
            />
          </label>
          <button
            disabled={!canManage || !selectedRecord || isActionRunning}
            onClick={() => onImportCatalog(activeCatalog.key, selectedRecord)}
            type="button"
          >
            Import
          </button>
          <button
            disabled={isActionRunning}
            onClick={() => onExportCatalog(activeCatalog.key)}
            type="button"
          >
            Export
          </button>
        </div>
      </header>

      <div className="metric-strip master-kpis">
        <div>
          <span>Active masters</span>
          <strong>{activeRecords}</strong>
        </div>
        <div>
          <span>Catalog records</span>
          <strong>{totalRecords}</strong>
        </div>
        <div>
          <span>Validation errors</span>
          <strong className={overview.validation.blockingRules ? "critical-text" : ""}>
            {overview.validation.blockingRules}
          </strong>
        </div>
        <div>
          <span>Missing GPS</span>
          <strong className={overview.validation.missingGpsDevices ? "warning-text" : ""}>
            {overview.validation.missingGpsDevices}
          </strong>
        </div>
        <div>
          <span>Version</span>
          <strong>CFG-104</strong>
        </div>
        <div>
          <span>Health</span>
          <strong>99.1%</strong>
        </div>
      </div>

      <div className="master-console-grid">
        <aside className="catalog-rail" aria-label="Master data catalog groups">
          {MODULE_ORDER.map((module) => (
            <section key={module}>
              <p>{module}</p>
              {CATALOGS.filter((catalog) => catalog.module === module).map((catalog) => {
                const count = overview.catalogs[catalog.key].length;
                return (
                  <button
                    className={catalog.key === activeCatalogKey ? "catalog-button active" : "catalog-button"}
                    key={catalog.key}
                    onClick={() => setActiveCatalogKey(catalog.key)}
                    type="button"
                  >
                    <SvgIcon name={catalog.icon} />
                    <span>{catalog.label}</span>
                    <em>{count}</em>
                  </button>
                );
              })}
            </section>
          ))}
        </aside>

        <section className="plain-section board-surface master-grid-panel">
          <h2>{activeCatalog.module} / {activeCatalog.label}</h2>
          <div className="master-grid-scroll">
            <table className="master-table">
              <thead>
                <tr>
                  {activeCatalog.columns.map((column) => (
                    <th key={column}>{column}</th>
                  ))}
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredRecords.map((record) => {
                  const selected = selectedRecord?.id === record.id;
                  const validation = validationState(record);
                  return (
                    <tr
                      className={selected ? "selected-row" : ""}
                      key={`${activeCatalog.key}-${record.id}`}
                      onClick={() => setSelectedRecordId(record.id)}
                    >
                      {activeCatalog.columns.map((column) => (
                        <td key={column}>
                          {column === "status" ? (
                            <span className={`status-chip ${statusTone(record)}`}>
                              {recordValue(record, column)}
                            </span>
                          ) : column === "validation" ? (
                            <span className={`validation-badge ${validation.tone}`}>
                              {validation.label}
                            </span>
                          ) : (
                            recordValue(record, column)
                          )}
                        </td>
                      ))}
                      <td>
                        <button
                          aria-label={`View ${record.code}`}
                          className="row-menu"
                          onClick={(event) => {
                            event.stopPropagation();
                            setSelectedRecordId(record.id);
                          }}
                          type="button"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {selectedRecord ? (
          <aside className="detail-drawer master-drawer">
            <div>
              <span>{activeCatalog.label} record</span>
              <strong>{selectedRecord.code}</strong>
              <small>{selectedRecord.name}</small>
            </div>

            <section>
              <h2>Record Configuration</h2>
              <div className="config-fields">
                {fieldRows(selectedRecord).map(([label, value]) => (
                  <label key={label}>
                    <span>{label}</span>
                    <input readOnly value={String(value)} />
                  </label>
                ))}
              </div>
            </section>

            <section className="validation-engine">
              <h2>Validation Engine</h2>
              <ul>
                <li>
                  <span className="dot ok" /> Identifier uniqueness <strong>VALID</strong>
                </li>
                <li>
                  <span className={`dot ${validationState(selectedRecord).tone}`} /> Operational constraints{" "}
                  <strong>{validationState(selectedRecord).label}</strong>
                </li>
                <li>
                  <span className="dot pending" /> Dependency publish gate <strong>REVIEW</strong>
                </li>
              </ul>
            </section>

            {activeCatalog.key === "routes" ? (
              <section className="route-segment-review">
                <h2>Tide & Bridge Segments</h2>
                <div>
                  {selectedRouteSegments.length ? selectedRouteSegments.map((segment) => (
                    <article key={segment.id}>
                      <span>{String(segment.sequence).padStart(2, "0")}</span>
                      <strong>{segment.from_location} {"->"} {segment.to_location}</strong>
                      <p>
                        {segment.distance_nm} NM / loaded {segment.loaded_duration_minutes}m / empty {segment.empty_duration_minutes}m
                      </p>
                      <em className={segment.requires_tide_window ? "active" : ""}>
                        Tide
                      </em>
                      <em className={segment.requires_bridge_window ? "active" : ""}>
                        Bridge
                      </em>
                    </article>
                  )) : (
                    <p>No route segments configured for this route.</p>
                  )}
                </div>
              </section>
            ) : null}

            <section>
              <h2>Dependency Tree</h2>
              <div className="dependency-grid">
                <div>
                  <strong>{(selectedRecord.id % 4) + 1}</strong>
                  <span>Active schedules</span>
                </div>
                <div>
                  <strong>{selectedRecord.id % 3}</strong>
                  <span>Simulations</span>
                </div>
              </div>
              <div className="impact-preview">
                <strong>Change impact preview</strong>
                <p>
                  Publishing this configuration may change schedule feasibility once OGV demand and
                  availability boards are active.
                </p>
              </div>
            </section>

            <div className="drawer-actions">
              <button disabled={isActionRunning} onClick={() => onValidateCatalog(activeCatalog.key)} type="button">
                Validate
              </button>
              <button
                disabled
                title={canManage
                  ? "Master-data approval workflow is locked for this Phase 1 pilot."
                  : "Your role cannot submit master data for approval."}
                type="button"
              >
                Approval locked
              </button>
              <button disabled title="Master-data publishing is controlled by the seed baseline in Phase 1." type="button">
                Publish config locked
              </button>
            </div>
          </aside>
        ) : null}
      </div>

      <footer className="master-config-strip">
        <span><i /> CFG-104 LIVE</span>
        <strong>CFG-105-RC1</strong>
        <em>{overview.validation.blockingRules} validation errors</em>
        <p>[14:28:01] Master data console synchronized against backend reference catalogs.</p>
      </footer>
    </section>
  );
}
