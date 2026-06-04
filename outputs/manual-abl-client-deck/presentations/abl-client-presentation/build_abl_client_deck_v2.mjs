import fs from "node:fs/promises";
import path from "node:path";
import {
  Presentation,
  PresentationFile,
  layers,
  text,
  shape,
  connector,
} from "file:///C:/Users/santosh%20(07564B3B)/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const ROOT = "F:/ocean/outputs/manual-abl-client-deck/presentations/abl-client-presentation";
const PREVIEW_DIR = `${ROOT}/preview_v2`;
const FINAL_PPTX = "F:/ocean/docs/proposal/final_version/ABL_Client_Presentation_Deck_Draft_v2.pptx";

const W = 1600;
const H = 900;

const C = {
  navy: "#0B2948",
  blue: "#2F7DBD",
  lightBlue: "#EAF4FD",
  green: "#2E7D32",
  lightGreen: "#EFF8EF",
  orange: "#E96500",
  lightOrange: "#FFF2E4",
  amber: "#A9781A",
  lightAmber: "#FFF7E7",
  red: "#BA2D2D",
  ink: "#10233F",
  slate: "#4A5F78",
  grey: "#D9E2EC",
  pale: "#F6F9FC",
  white: "#FFFFFF",
};

function titleStyle(size = 34, color = C.ink) {
  return { fontSize: size, fontFace: "Segoe UI", color, bold: true };
}

function bodyStyle(size = 18, color = C.slate, bold = false) {
  return { fontSize: size, fontFace: "Segoe UI", color, bold };
}

function smallStyle(size = 14, color = C.slate, bold = false) {
  return { fontSize: size, fontFace: "Segoe UI", color, bold };
}

function t(value, x, y, w, h, style = bodyStyle()) {
  return text(value, { position: { left: x, top: y }, width: w, height: h, style });
}

function rect(x, y, w, h, fill, opts = {}) {
  return shape({
    position: { left: x, top: y },
    width: w,
    height: h,
    fill,
    borderRadius: opts.radius ?? 0,
    line: opts.line ?? { color: fill, width: 0 },
  });
}

function line(x, y, w, h, fill = C.grey) {
  return rect(x, y, w, h, fill);
}

function pill(label, x, y, w, color, textColor = C.white) {
  return [
    rect(x, y, w, 34, color, { radius: 17 }),
    t(label, x + 12, y + 7, w - 24, 24, smallStyle(13, textColor, true)),
  ];
}

function node(label, x, y, w, h, fill = C.white, border = C.grey, color = C.ink) {
  return [
    rect(x, y, w, h, fill, { radius: 12, line: { color: border, width: 1.4 } }),
    t(label, x + 14, y + 15, w - 28, h - 26, bodyStyle(17, color, true)),
  ];
}

function arrow(x1, y1, x2, y2, color = C.grey, width = 2) {
  return connector({
    kind: "straight",
    from: { left: x1, top: y1 },
    to: { left: x2, top: y2 },
    line: { color, width },
    head: "triangle",
  });
}

function header(title, thesis, kicker = "ABL | Dynamic Operational Synchronization Platform") {
  return [
    rect(0, 0, W, 86, C.navy),
    t(title, 64, 26, 930, 46, titleStyle(31, C.white)),
    t(kicker, 1090, 33, 450, 30, smallStyle(15, "#DCE8F5", false)),
    thesis ? t(thesis, 64, 110, 1180, 44, bodyStyle(25, C.ink, true)) : null,
    line(64, 166, 1472, 2, C.grey),
  ].filter(Boolean);
}

function footer(slideNo, block = "") {
  return [
    t(`PT Vector Management Consulting${block ? `  |  ${block}` : ""}`, 64, 854, 780, 20, smallStyle(11, "#6B7C92")),
    t(`${slideNo}/15`, 1488, 854, 48, 20, smallStyle(11, "#6B7C92", true)),
  ];
}

function sectionBand(label, color, x = 64, y = 184, w = 220) {
  return [
    rect(x, y, w, 34, color, { radius: 17 }),
    t(label, x + 16, y + 7, w - 32, 22, smallStyle(12, C.white, true)),
  ];
}

function slideBase(slide, title, thesis, no, block = "") {
  slide.compose(
    layers({ width: W, height: H }, [
      rect(0, 0, W, H, C.white),
      ...header(title, thesis),
      ...footer(no, block),
    ])
  );
}

function compose(slide, elements) {
  slide.compose(layers({ width: W, height: H }, elements.flat().filter(Boolean)));
}

function flowNodes(labels, x, y, w, h, gap, color = C.blue) {
  const els = [];
  labels.forEach((label, i) => {
    const nx = x + i * (w + gap);
    els.push(...node(label, nx, y, w, h, i === 0 ? color : C.white, i === 0 ? color : C.grey, i === 0 ? C.white : C.ink));
    if (i < labels.length - 1) els.push(arrow(nx + w + 5, y + h / 2, nx + w + gap - 5, y + h / 2, C.slate, 1.5));
  });
  return els;
}

function screenFrame(x, y, w, h, title, accent = C.blue) {
  const els = [
    rect(x, y, w, h, C.white, { radius: 14, line: { color: C.grey, width: 1.5 } }),
    rect(x, y, w, 46, C.navy, { radius: 14 }),
    rect(x, y + 36, w, 12, C.navy),
    t(title, x + 24, y + 13, w - 48, 24, smallStyle(15, C.white, true)),
    rect(x + 22, y + 70, 150, h - 98, C.pale, { radius: 10, line: { color: C.grey, width: 1 } }),
  ];
  ["Dashboard", "Demand", "Windows", "Schedule", "Approval"].forEach((m, i) => {
    els.push(rect(x + 40, y + 96 + i * 42, 112, 24, i === 1 ? accent : "#EEF2F6", { radius: 6 }));
    els.push(t(m, x + 50, y + 100 + i * 42, 96, 18, smallStyle(10, i === 1 ? C.white : C.slate, i === 1)));
  });
  els.push(rect(x + 200, y + 76, w - 230, 58, C.lightBlue, { radius: 10, line: { color: "#C8D9EC", width: 1 } }));
  els.push(t("Active plan workspace", x + 222, y + 94, w - 274, 24, bodyStyle(17, C.ink, true)));
  for (let i = 0; i < 5; i++) {
    els.push(rect(x + 202, y + 158 + i * 47, w - 234, 34, i % 2 ? C.white : C.pale, { radius: 5, line: { color: "#E3EAF2", width: 1 } }));
    els.push(t(["OGV demand", "Cargo layer", "Tide / bridge window", "Movement candidate", "Approval state"][i] ?? "Item", x + 220, y + 166 + i * 47, 260, 18, smallStyle(12, C.ink, true)));
    els.push(rect(x + w - 250, y + 165 + i * 47, 132, 20, [C.blue, C.green, C.amber, C.orange, C.green][i], { radius: 10 }));
  }
  return els;
}

function callout(num, label, x, y, color = C.blue) {
  return [
    rect(x, y, 32, 32, color, { radius: 16 }),
    t(String(num), x + 10, y + 6, 14, 18, smallStyle(14, C.white, true)),
    t(label, x + 42, y + 5, 240, 24, smallStyle(14, C.ink, true)),
  ];
}

function detailCard(title, body, x, y, w, h, accent = C.blue) {
  return [
    rect(x, y, w, h, C.white, { radius: 12, line: { color: "#CCD8E6", width: 1.2 } }),
    rect(x, y, 8, h, accent, { radius: 4 }),
    t(title, x + 22, y + 14, w - 36, 24, bodyStyle(16, accent, true)),
    t(body, x + 22, y + 44, w - 36, h - 56, smallStyle(13, C.ink, false)),
  ];
}

function stateLegend(x, y) {
  const states = [
    ["Planned", C.blue],
    ["Observed", C.slate],
    ["Confirmed", C.green],
    ["Projected", C.orange],
    ["Recommended", C.amber],
    ["Blocked", C.red],
  ];
  const els = [t("State legend", x, y, 110, 20, smallStyle(12, C.slate, true))];
  states.forEach((s, i) => {
    const px = x + 120 + i * 142;
    els.push(rect(px, y - 2, 14, 14, s[1], { radius: 7 }));
    els.push(t(s[0], px + 21, y - 5, 110, 20, smallStyle(11, C.ink, true)));
  });
  return els;
}

function miniHeader(label, x, y, w, color = C.navy) {
  return [
    rect(x, y, w, 34, color, { radius: 8 }),
    t(label, x + 14, y + 8, w - 28, 18, smallStyle(13, C.white, true)),
  ];
}

function timelineRoadmap() {
  const x = 108;
  const y = 285;
  const w = 1380;
  const week = w / 36;
  const bandH = 44;
  const rows = [
    ["Blueprinting", 1, 3, C.blue],
    ["Sprint 0", 4, 5, C.blue],
    ["Sprint 1", 6, 7, C.blue],
    ["Sprint 2", 8, 9, C.blue],
    ["Sprint 3", 10, 11, C.blue],
    ["Sprint 4", 12, 14, "#45A4E3"],
    ["Sprint 5", 15, 16, "#45A4E3"],
    ["Release 1 Review", 17, 18, C.green],
  ];
  const els = [];
  els.push(rect(x, y - 92, w, 44, C.lightGreen, { radius: 8, line: { color: "#C8DEC8", width: 1 } }));
  els.push(t("Release 1 focus: governed scheduling spine and operating-window validation", x + 24, y - 80, w - 48, 24, bodyStyle(18, C.green, true)));
  for (let wk = 2; wk <= 18; wk += 2) {
    const tx = x + wk * week - week / 2;
    els.push(t(`WK${wk}`, tx - 18, y - 26, 44, 20, smallStyle(12, C.slate, true)));
    els.push(line(x + (wk - 1) * week, y, 1, rows.length * bandH, "#D7E0EA"));
  }
  rows.forEach((r, i) => {
    const yy = y + i * bandH;
    els.push(t(r[0], x, yy + 18, 150, 20, smallStyle(13, C.ink, true)));
    const bx = x + (r[1] - 1) * week + 155;
    const bw = (r[2] - r[1] + 1) * week - 10;
    els.push(rect(bx, yy + 12, bw, 30, r[3], { radius: 6 }));
    els.push(t(`W${r[1]}-W${r[2]}`, bx + 10, yy + 18, bw - 20, 16, smallStyle(11, C.white, true)));
    els.push(line(x, yy + bandH - 1, w, 1, "#E7EDF3"));
  });
  els.push(...pill("Blueprint complete", x + 3 * week - 78, y + rows.length * bandH + 26, 160, C.blue));
  els.push(...pill("Release 1 validated", x + 18 * week - 96, y + rows.length * bandH + 26, 190, C.green));
  return els;
}

const slides = [
  {
    title: "Proposal Context & Operating Reality",
    thesis: "ABL's planning problem sits inside one connected transshipment operating system.",
    block: "Opening",
    draw: () => [
      ...sectionBand("OPERATING SYSTEM MAP", C.blue, 64, 184, 245),
      ...flowNodes(["Berau OGV demand", "Cargo readiness", "Jetty / BLC loading", "Tug-barge movement", "CTS / floating transfer", "OGV loading"], 86, 304, 205, 78, 22, C.blue),
      ...pill("Tide windows", 392, 236, 146, C.green),
      ...pill("Bridge windows", 595, 236, 166, C.green),
      ...pill("Berth / CTS capacity", 820, 236, 196, C.amber),
      ...pill("Fleet availability", 610, 430, 190, C.orange),
      ...pill("Cargo / quality release", 350, 430, 220, C.blue),
      ...detailCard("Operating reality", "Demand, cargo, assets, windows and OGV commitments change together. A local delay can quickly become a downstream loading risk.", 125, 565, 420, 118, C.blue),
      ...detailCard("Planning implication", "The plan must continuously test executable flow capacity instead of only tracking target dates or asset locations.", 590, 565, 420, 118, C.green),
      ...detailCard("Product requirement", "One governed platform must connect demand intake, scheduling, approval, evidence and recovery.", 1055, 565, 420, 118, C.orange),
    ],
  },
  {
    title: "Problem Statement",
    thesis: "Manual coordination cannot stabilize a plan when the operating constraint keeps moving.",
    block: "Opening",
    draw: () => [
      ...sectionBand("PLANNING STRESS LOOP", C.orange, 64, 184, 230),
      ...node("Demand plan\nchanges", 325, 250, 180, 72, C.lightOrange, "#F2C89E"),
      ...node("Spreadsheet\nrevision", 595, 215, 190, 72, C.white, C.grey),
      ...node("WhatsApp / phone\ncoordination", 870, 250, 230, 72, C.white, C.grey),
      ...node("Planner judgement\nand negotiation", 885, 448, 235, 72, C.white, C.grey),
      ...node("Field condition\nchanges", 600, 515, 190, 72, C.white, C.grey),
      ...node("Replanned\nschedule", 315, 448, 190, 72, C.lightOrange, "#F2C89E"),
      arrow(507, 286, 587, 250, C.orange, 2),
      arrow(787, 250, 862, 286, C.orange, 2),
      arrow(990, 324, 1002, 441, C.orange, 2),
      arrow(884, 486, 796, 544, C.orange, 2),
      arrow(598, 548, 510, 489, C.orange, 2),
      arrow(382, 446, 390, 325, C.orange, 2),
      ...detailCard("Visible pain", "Missed OGV dates, underutilized assets, repeated reassignment, excessive waiting and reactive escalation.", 118, 650, 390, 82, C.red),
      ...detailCard("Why it repeats", "Operating decisions are made faster than the spreadsheet plan can be reconciled and governed.", 605, 650, 390, 82, C.orange),
      ...detailCard("What is missing", "Simulation-backed visibility of blockers, feasible windows, approval lineage and recovery impact.", 1092, 650, 390, 82, C.green),
    ],
  },
  {
    title: "Root Cause Perspective",
    thesis: "The core issue is synchronization with the current controlling constraint.",
    block: "Opening",
    draw: () => {
      const labels = ["Cargo ready", "Jetty", "Tide", "Bridge", "Tug-barge", "CTS", "OGV laycan"];
      const els = [...sectionBand("CCR-BASED OPERATING LENS", C.green, 64, 184, 285)];
      labels.forEach((label, i) => {
        const x = 110 + i * 202;
        const active = i === 3;
        els.push(rect(x, 320, 154, 76, active ? C.green : C.pale, { radius: 12, line: { color: active ? C.green : C.grey, width: 1.4 } }));
        els.push(t(label, x + 14, 346, 126, 25, bodyStyle(16, active ? C.white : C.ink, true)));
        if (i < labels.length - 1) els.push(arrow(x + 157, 358, x + 198, 358, C.slate, 1.4));
      });
      els.push(...detailCard("CCR lens", "The effective capacity of the whole flow is governed by the constraint currently limiting movement.", 160, 510, 390, 112, C.green));
      els.push(...detailCard("ABL reality", "The active constraint can shift between tide, bridge, jetty, CTS, fleet, cargo readiness and laycan pressure.", 605, 510, 390, 112, C.orange));
      els.push(...detailCard("Solution implication", "The schedule must recalculate feasibility around moving operating windows and current execution state.", 1050, 510, 390, 112, C.blue));
      els.push(t("Business need: synchronize demand commitments with executable operational flow capacity.", 280, 700, 1030, 34, titleStyle(25, C.ink)));
      return els;
    },
  },
  {
    title: "Core Operating Philosophy",
    thesis: "The tool must convert every movement into a governed feasibility decision.",
    block: "Opening",
    draw: () => [
      ...sectionBand("FEASIBILITY GATE", C.green, 64, 184, 205),
      ...node("Demand\nlaycan / quantity", 95, 285, 180, 64, C.lightBlue, "#BFD6EF"),
      ...node("Cargo grade\nand layer", 95, 370, 180, 64, C.lightBlue, "#BFD6EF"),
      ...node("Route steps\nand eligibility", 95, 455, 180, 64, C.lightBlue, "#BFD6EF"),
      ...node("Asset / CTS\navailability", 95, 540, 180, 64, C.lightBlue, "#BFD6EF"),
      ...node("Tide and\nbridge windows", 330, 330, 205, 64, C.lightGreen, "#C6DEC6"),
      ...node("Jetty / BLC\ncapacity", 330, 455, 205, 64, C.lightGreen, "#C6DEC6"),
      arrow(278, 318, 626, 430, C.slate, 1.2),
      arrow(278, 402, 626, 430, C.slate, 1.2),
      arrow(278, 488, 626, 430, C.slate, 1.2),
      arrow(538, 362, 626, 430, C.slate, 1.2),
      arrow(538, 488, 626, 430, C.slate, 1.2),
      rect(640, 330, 290, 205, C.navy, { radius: 18 }),
      t("Constraint-aware\nfeasibility gate", 690, 382, 200, 70, titleStyle(26, C.white)),
      t("Eligibility + window + capacity + governance", 675, 468, 230, 24, smallStyle(12, "#DDEAF7", true)),
      arrow(945, 404, 1030, 360, C.green, 2),
      arrow(945, 468, 1030, 520, C.orange, 2),
      ...node("Feasible candidate\nmovement", 1050, 322, 300, 86, C.lightGreen, "#BFD8BF", C.green),
      ...node("Reason-coded\nblocker", 1050, 484, 300, 86, C.lightOrange, "#EDC8A5", C.orange),
      ...detailCard("Governance rule", "Overrides are allowed only with reason, user, timestamp, affected movement and approval lineage.", 1030, 622, 395, 86, C.amber),
      ...stateLegend(260, 746),
    ],
  },
  {
    title: "Vector Approach & Proprietary Scaffolding",
    thesis: "Vector's base platform accelerates the build while blueprinting makes it ABL-specific.",
    block: "Opening",
    draw: () => {
      const els = [...sectionBand("VECTOR BUILD APPROACH", C.navy, 64, 184, 240)];
      const layersData = [
        ["Governed ABL planning platform", C.navy],
        ["ABL rules: routes, assets, tide, bridge, approvals, exports", C.blue],
        ["Dynamic constraint handling", C.green],
        ["Scenario and recovery engine", C.orange],
        ["Vector proprietary scheduling base", C.amber],
      ];
      layersData.forEach((l, i) => {
        const y = 250 + i * 66;
        els.push(rect(365 + i * 35, y, 870 - i * 70, 48, l[1], { radius: 8 }));
        els.push(t(l[0], 390 + i * 35, y + 13, 810 - i * 70, 20, bodyStyle(16, C.white, true)));
      });
      els.push(...detailCard("What Vector owns", "Scheduling model, scenario engine, dynamic-constraint scaffolding and governed workflow patterns.", 100, 610, 420, 104, C.navy));
      els.push(...detailCard("What blueprinting configures", "ABL-specific routes, assets, operating windows, data assumptions, approval gates and integration readiness.", 590, 610, 420, 104, C.blue));
      els.push(...detailCard("What the client gets", "A configured product build that reflects ABL's transshipment operating rules and pilot adoption needs.", 1080, 610, 420, 104, C.green));
      return els;
    },
  },
  {
    title: "Product Concept",
    thesis: "The platform governs the path from demand to publish, then connects evidence to recovery.",
    block: "Opening",
    draw: () => [
      ...sectionBand("END-TO-END PRODUCT FLOW", C.blue, 64, 184, 260),
      ...miniHeader("Plan and govern", 110, 268, 285, C.blue),
      ...flowNodes(["OGV demand", "Cargo layer", "Windows", "Candidate movement", "Conflict review", "Approval", "Publish"], 110, 340, 170, 62, 24, C.blue),
      ...miniHeader("Monitor and recover", 390, 528, 320, C.orange),
      ...flowNodes(["Observed evidence", "Event candidate", "Confirmed state", "Scenario", "Recovery option", "Approval", "Recovery publish"], 110, 600, 170, 62, 24, C.orange),
      ...stateLegend(275, 745),
      t("Key design rule: raw signals support planning, but only governed confirmation and approval change the operating plan.", 260, 690, 1040, 30, bodyStyle(18, C.ink, true)),
    ],
  },
  {
    title: "Release 1 Product Layer",
    thesis: "Release 1 is the first usable product layer for governed scheduling and publication.",
    block: "Opening",
    draw: () => {
      const els = [...sectionBand("FIRST PRODUCT LAYER", C.green, 64, 184, 220)];
      const blocks = [
        ["Screens", "Login, roles, master data, demand, cargo layer, windows, schedule, conflict, approval, publish, audit, export", C.blue],
        ["Capability", "Demand intake, route/resource eligibility, window validation, candidate movement generation, conflict output and plan versioning", C.green],
        ["Governance", "Reason-coded override, dual approval, publishability, immutable published snapshot and governed export", C.amber],
        ["ABL-owned product", "Working scheduling application that replaces spreadsheet-only planning for the core ABL-Berau flow", C.orange],
      ];
      blocks.forEach((b, i) => {
        const x = 115 + (i % 2) * 710;
        const y = 280 + Math.floor(i / 2) * 190;
        els.push(...detailCard(b[0], b[1], x, y, 620, 130, b[2]));
      });
      els.push(t("Release 1 success is validated through pilot-user adoption, conflict quality, approval traceability and publishable-plan cycle time.", 200, 705, 1180, 42, bodyStyle(22, C.ink, true)));
      return els;
    },
  },
  {
    title: "Application Modules & Master Data Spine",
    thesis: "The product is organized around controlled operating data and one operator cockpit.",
    block: "Demo Block 1",
    draw: () => {
      const els = [...sectionBand("DEMO BLOCK 1: CORE APP + HAPPY PATH", C.blue, 64, 184, 335)];
      const cx = 790, cy = 410;
      els.push(rect(cx - 170, cy - 68, 340, 136, C.navy, { radius: 16 }));
      els.push(t("Operator\nCockpit", cx - 80, cy - 38, 160, 66, titleStyle(27, C.white)));
      const mods = [
        ["Access", 230, 260, C.blue, "Users, roles, approval authority"],
        ["Master Data", 520, 225, C.blue, "Assets, routes, locations, grades"],
        ["Planning", 880, 225, C.blue, "OGV demand, cargo, windows"],
        ["Scheduling", 1170, 260, C.green, "Candidates, conflicts, versions"],
        ["Exception", 1170, 560, C.orange, "Families, reason codes, recovery link"],
        ["Telemetry", 880, 625, C.slate, "Signals, geofence, latest state"],
        ["Operations", 520, 625, C.slate, "Event candidates, confirmations"],
        ["Audit", 230, 560, C.amber, "Overrides, approvals, exports"],
      ];
      mods.forEach((m) => {
        els.push(rect(m[1], m[2], 210, 62, m[2] < 400 ? C.lightBlue : C.pale, { radius: 11, line: { color: m[3], width: 1.3 } }));
        els.push(t(m[0], m[1] + 16, m[2] + 12, 180, 20, bodyStyle(15, m[3], true)));
        els.push(t(m[4], m[1] + 16, m[2] + 34, 175, 18, smallStyle(10, C.slate)));
        els.push(arrow(m[1] + 105, m[2] + 31, cx, cy, "#B8C6D6", 1.1));
      });
      els.push(...pill("Demo objective: show module familiarity, master data spine and current product readiness", 420, 744, 760, C.blue));
      return els;
    },
  },
  {
    title: "OGV Demand To Feasible Schedule",
    thesis: "The happy path converts OGV demand into feasible movement candidates through business-rule checks.",
    block: "Demo Block 1",
    draw: () => {
      const els = [
        ...sectionBand("HAPPY PATH: DEMAND TO CANDIDATE SCHEDULE", C.blue, 64, 184, 385),
        ...screenFrame(70, 232, 615, 425, "Planning cockpit - demand and windows", C.blue),
      ];
      const steps = [
        ["1", "OGV demand", "ETA, laycan, quantity, priority", 740, 250, C.blue],
        ["2", "Cargo layer", "Grade and loading sequence", 1045, 250, C.blue],
        ["3", "Route steps", "Jetty, movement, CTS chain", 740, 360, C.green],
        ["4", "Asset / CTS fit", "Compatibility and availability", 1045, 360, C.green],
        ["5", "Operating windows", "Tide, bridge, jetty capacity", 740, 470, C.orange],
        ["6", "Candidate schedule", "Feasible movement placement", 1045, 470, C.green],
      ];
      steps.forEach((s, i) => {
        els.push(rect(s[3], s[4], 250, 78, s[5] === C.green ? C.lightGreen : s[5] === C.orange ? C.lightOrange : C.lightBlue, { radius: 12, line: { color: s[5], width: 1.2 } }));
        els.push(rect(s[3] + 12, s[4] + 20, 28, 28, s[5], { radius: 14 }));
        els.push(t(s[0], s[3] + 22, s[4] + 26, 10, 12, smallStyle(11, C.white, true)));
        els.push(t(s[1], s[3] + 52, s[4] + 15, 175, 20, bodyStyle(15, C.ink, true)));
        els.push(t(s[2], s[3] + 52, s[4] + 41, 175, 20, smallStyle(11, C.slate)));
        if (i % 2 === 0) els.push(arrow(s[3] + 252, s[4] + 38, s[3] + 298, s[4] + 38, C.slate, 1.2));
      });
      els.push(...detailCard("Demo proof", "Show OGV demand entry, cargo-layer representation, operating windows and candidate movement generation.", 760, 620, 560, 92, C.blue));
      return els;
    },
  },
  {
    title: "Approval, Publish & Audit Trail",
    thesis: "The product turns a feasible draft into an approved execution contract.",
    block: "Demo Block 1",
    draw: () => [
      ...sectionBand("HAPPY PATH: GOVERNANCE TO PUBLISH", C.green, 64, 184, 345),
      ...flowNodes(["Draft plan", "Conflict review", "Override reason", "ABL approval", "Berau approval", "Publishability", "Published snapshot", "Export & audit"], 65, 310, 160, 66, 20, C.green),
      ...detailCard("Decision rules", "Hard blockers must carry reason code, affected movement and review action. Manual override does not erase the blocker history.", 130, 500, 390, 112, C.orange),
      ...detailCard("Publish rule", "Published plans remain immutable; replanning creates successor versions and preserves approval lineage.", 605, 500, 390, 112, C.green),
      ...detailCard("Audit proof", "Every approval, override, publish action and export is traceable by user, timestamp and plan version.", 1080, 500, 390, 112, C.amber),
      ...pill("Demo sequence: conflict review -> override reason -> dual approval -> publish -> audit/export", 340, 705, 920, C.green),
    ],
  },
  {
    title: "Scenario & Exception Flow",
    thesis: "Disruption is treated as a governed scenario before the published plan changes.",
    block: "Demo Block 2",
    draw: () => [
      ...sectionBand("DEMO BLOCK 2: RECOVERY + SCENARIO", C.orange, 64, 184, 335),
      ...miniHeader("Baseline plan", 140, 265, 265, C.blue),
      rect(140, 315, 530, 245, C.lightBlue, { radius: 14, line: { color: "#C7DAEE", width: 1.2 } }),
      ...flowNodes(["Published plan", "Active constraint", "Current conflict"], 175, 390, 135, 60, 32, C.blue),
      ...miniHeader("Scenario plan", 925, 265, 265, C.orange),
      rect(925, 315, 530, 245, C.lightOrange, { radius: 14, line: { color: "#EFC7A4", width: 1.2 } }),
      ...flowNodes(["Delay / outage", "Reassignment", "Projected impact"], 960, 390, 135, 60, 32, C.orange),
      arrow(690, 438, 905, 438, C.orange, 2),
      ...detailCard("Exception object", "Family, cause, affected movement, active constraint and recovery linkage.", 155, 625, 300, 88, C.orange),
      ...detailCard("Simulation output", "Trip impact, OGV risk, utilization, remaining blockers and promotion path.", 505, 625, 300, 88, C.orange),
      ...detailCard("Governance", "Scenario can be promoted only after feasibility and approval checks.", 855, 625, 300, 88, C.green),
      ...detailCard("Demo proof", "Show one baseline-vs-scenario comparison with downstream impact.", 1205, 625, 300, 88, C.blue),
    ],
  },
  {
    title: "Recovery Path To Publish",
    thesis: "Recovery remains advisory until simulated, approved and checked for publishability.",
    block: "Demo Block 2",
    draw: () => [
      ...sectionBand("RECOVERY TO PUBLICATION", C.orange, 64, 184, 260),
      ...flowNodes(["Active exception", "Recovery snapshot", "Ranked options", "Root-cause validation", "Scenario run", "Publishability", "Approval", "Recovery publish"], 64, 302, 170, 68, 20, C.orange),
      ...detailCard("Recovery input snapshot", "Active plan, current alerts, confirmed events, operating windows, resource state and conflict history.", 110, 495, 330, 118, C.blue),
      ...detailCard("Ranked options", "Candidate recovery actions are compared by constraint impact, OGV risk, movement feasibility and remaining blockers.", 480, 495, 330, 118, C.amber),
      ...detailCard("Proof pack", "The selected option carries scenario evidence, root-cause validation, publishability result and audit lineage.", 850, 495, 330, 118, C.green),
      ...detailCard("Demo proof", "Demonstrate recovery flow all the way to approved recovery publication.", 1220, 495, 280, 118, C.orange),
      ...pill("Recovery design principle: recommend -> simulate -> approve -> publish", 465, 705, 670, C.orange),
    ],
  },
  {
    title: "Telemetry Evidence & Operational Monitoring",
    thesis: "Signals create observed evidence; confirmed events update the execution state.",
    block: "Demo Block 3",
    draw: () => {
      const els = [...sectionBand("DEMO BLOCK 3: TELEMETRY + EVIDENCE", C.slate, 64, 184, 350)];
      els.push(rect(70, 245, 760, 430, "#EAF1F8", { radius: 18, line: { color: "#C7D5E5", width: 1 } }));
      els.push(t("Navigational monitoring view", 105, 265, 420, 26, titleStyle(22, C.ink)));
      for (let i = 0; i < 8; i++) {
        els.push(line(115 + i * 82, 325, 1, 285, "#D6E0EA"));
        els.push(line(115, 325 + i * 40, 620, 1, "#D6E0EA"));
      }
      const assets = [
        [245, 430, C.green, "TB-12", "Confirmed"],
        [445, 515, C.blue, "CTS-3", "Planned"],
        [645, 395, C.orange, "B-08", "ETA variance"],
      ];
      assets.forEach((a) => {
        els.push(rect(a[0], a[1], 44, 44, a[2], { radius: 22 }));
        els.push(t(a[3], a[0] - 18, a[1] + 52, 90, 18, smallStyle(12, C.ink, true)));
        els.push(t(a[4], a[0] - 38, a[1] + 72, 125, 18, smallStyle(10, C.slate)));
      });
      els.push(rect(890, 245, 610, 430, C.white, { radius: 18, line: { color: C.grey, width: 1.2 } }));
      els.push(t("Evidence and trust panel", 930, 268, 360, 24, titleStyle(22, C.ink)));
      const states = [
        ["AIS / GPS evidence", "Position, speed, heading, timestamp", C.blue],
        ["Latest asset state", "Normalized asset identity and freshness", C.slate],
        ["Geofence / ETA variance", "Alert where movement deviates", C.orange],
        ["Event candidate", "Device, feed or operator event", C.amber],
        ["Confirm or reject", "Trust decision before actualization", C.green],
        ["Actual execution state", "Confirmed event updates schedule status", C.green],
      ];
      states.forEach((s, i) => {
        els.push(rect(930, 320 + i * 54, 510, 38, i === 4 ? C.lightGreen : C.pale, { radius: 8, line: { color: s[2], width: 1 } }));
        els.push(t(s[0], 948, 327 + i * 54, 160, 18, smallStyle(13, s[2], true)));
        els.push(t(s[1], 1115, 327 + i * 54, 285, 18, smallStyle(11, C.slate)));
      });
      els.push(...stateLegend(295, 720));
      return els;
    },
  },
  {
    title: "Delivery Roadmap: Release 1 Focus",
    thesis: "Blueprinting starts the work; Sprint 0 begins from Week 4 and Release 1 is validated by Weeks 17-18.",
    block: "Delivery Roadmap",
    draw: () => [
      ...timelineRoadmap(),
      ...detailCard("Blueprinting", "Weeks 1-3: operating rules, data assumptions, flow logic, integration readiness and sprint backlog.", 110, 690, 390, 82, C.blue),
      ...detailCard("Release 1 build", "Weeks 4-16: foundation, master data, demand/cargo, windows, scheduling, blockers, approvals and publish.", 555, 690, 455, 82, C.green),
      ...detailCard("Review and adoption", "Weeks 17-18: pilot-user validation, conflict quality, override pattern, approval latency and readiness baseline.", 1065, 690, 430, 82, C.amber),
    ],
  },
  {
    title: "Adoption Review & Client Alignment",
    thesis: "The next decision is readiness: rules, data, owners, users and integrations.",
    block: "Delivery Roadmap",
    draw: () => {
      const els = [...sectionBand("CLIENT ALIGNMENT BOARD", C.amber, 64, 184, 265)];
      const cols = [
        ["Operating rules", C.green, "Validate constraint logic, windows, blockers and overrides"],
        ["Data ownership", C.blue, "Confirm names, sources, master-data ownership and update rhythm"],
        ["Pilot users", C.orange, "Name planners, approvers, exception reviewers and champions"],
        ["Approval authority", C.green, "Confirm ABL and Berau sign-off workflow for publication"],
        ["Integration access", C.slate, "Identify source owners, access methods and readiness timing"],
      ];
      cols.forEach((col, i) => {
        const x = 86 + i * 300;
        els.push(rect(x, 278, 250, 285, C.white, { radius: 14, line: { color: col[1], width: 1.4 } }));
        els.push(rect(x, 278, 250, 50, col[1], { radius: 14 }));
        els.push(rect(x, 317, 250, 12, col[1]));
        els.push(t(col[0], x + 18, 296, 210, 18, smallStyle(14, C.white, true)));
        els.push(t(col[2], x + 22, 365, 205, 72, bodyStyle(16, C.ink, true)));
        els.push(rect(x + 36, 480, 178, 30, C.lightGreen, { radius: 15, line: { color: C.green, width: 1 } }));
        els.push(t("validation owner required", x + 52, 488, 146, 14, smallStyle(10, C.green, true)));
      });
      els.push(rect(225, 655, 1150, 62, C.navy, { radius: 18 }));
      els.push(t("Build  ->  Operate  ->  Transfer  ->  Audit", 490, 671, 620, 28, titleStyle(23, C.white)));
      els.push(t("Close the proposal discussion by confirming the operating owners needed for Release 1 adoption.", 330, 745, 940, 28, bodyStyle(18, C.ink, true)));
      return els;
    },
  },
];

async function saveBlob(blob, file) {
  const arrayBuffer = await blob.arrayBuffer();
  await fs.writeFile(file, Buffer.from(arrayBuffer));
}

async function main() {
  await fs.mkdir(PREVIEW_DIR, { recursive: true });
  const pres = Presentation.create();
  for (let i = 0; i < slides.length; i++) {
    const s = pres.slides.add({ width: W, height: H });
    slideBase(s, slides[i].title, slides[i].thesis, i + 1, slides[i].block);
    compose(s, slides[i].draw());
  }

  const pptx = await PresentationFile.exportPptx(pres);
  await pptx.save(FINAL_PPTX);

  for (let i = 0; i < pres.slides.count; i++) {
    const slide = pres.slides.getItem(i);
    const png = await slide.export({ format: "png" });
    await saveBlob(png, `${PREVIEW_DIR}/slide-${String(i + 1).padStart(2, "0")}.png`);
  }
  console.log(FINAL_PPTX);
  console.log(PREVIEW_DIR);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
