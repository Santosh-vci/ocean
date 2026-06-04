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
const PREVIEW_DIR = `${ROOT}/preview`;
const FINAL_PPTX = "F:/ocean/docs/proposal/final_version/ABL_Client_Presentation_Deck_Draft_v1.pptx";

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
    thesis: "ABL needs synchronized planning across a moving transshipment flow.",
    block: "Opening",
    draw: () => [
      ...sectionBand("OPERATING SYSTEM MAP", C.blue),
      ...flowNodes(["Berau demand", "Cargo readiness", "Jetty / BLC", "Tug-barge flow", "CTS", "OGV loading"], 115, 320, 190, 82, 28, C.blue),
      ...pill("Tide window", 410, 235, 136, C.green),
      ...pill("Bridge window", 642, 235, 160, C.green),
      ...pill("Berth / CTS", 900, 235, 132, C.amber),
      ...pill("Fleet availability", 675, 472, 186, C.orange),
      t("Each operational decision changes the feasibility of the next movement.", 242, 612, 1110, 34, bodyStyle(24, C.ink, true)),
      t("The platform must synchronize demand, assets, windows and approvals into one governed flow.", 318, 660, 960, 30, bodyStyle(19, C.slate)),
    ],
  },
  {
    title: "Problem Statement",
    thesis: "Planning changes faster than manual coordination can stabilize it.",
    block: "Opening",
    draw: () => [
      ...sectionBand("PLANNING STRESS LOOP", C.orange),
      ...node("Demand plan", 300, 260, 190, 72, C.lightOrange, "#F2C89E"),
      ...node("Spreadsheet revision", 560, 210, 230, 72, C.white, C.grey),
      ...node("WhatsApp / phone coordination", 855, 260, 270, 72, C.white, C.grey),
      ...node("Planner judgement", 855, 455, 240, 72, C.white, C.grey),
      ...node("Field change", 560, 510, 210, 72, C.white, C.grey),
      ...node("Replanned schedule", 290, 455, 240, 72, C.lightOrange, "#F2C89E"),
      arrow(492, 295, 552, 250, C.orange, 2),
      arrow(792, 250, 848, 295, C.orange, 2),
      arrow(990, 334, 990, 448, C.orange, 2),
      arrow(854, 492, 778, 542, C.orange, 2),
      arrow(558, 545, 532, 492, C.orange, 2),
      arrow(332, 454, 330, 335, C.orange, 2),
      ...pill("Missed OGV schedule", 195, 665, 208, C.red),
      ...pill("Waiting", 452, 665, 108, C.red),
      ...pill("Repeated reassignment", 610, 665, 234, C.red),
      ...pill("Underutilized assets", 895, 665, 216, C.red),
      ...pill("Reactive escalation", 1160, 665, 194, C.red),
    ],
  },
  {
    title: "Root Cause Perspective",
    thesis: "The active constraint moves. The plan must move with it.",
    block: "Opening",
    draw: () => {
      const labels = ["Cargo ready", "Jetty", "Tide", "Bridge", "Tug-barge", "CTS", "OGV laycan"];
      const els = [...sectionBand("CCR-BASED LENS", C.green)];
      labels.forEach((label, i) => {
        const x = 130 + i * 195;
        const active = i === 3;
        els.push(rect(x, 350, 150, 86, active ? C.green : C.pale, { radius: 12, line: { color: active ? C.green : C.grey, width: 1.5 } }));
        els.push(t(label, x + 16, 378, 118, 30, bodyStyle(17, active ? C.white : C.ink, true)));
        if (i < labels.length - 1) els.push(arrow(x + 154, 393, x + 190, 393, C.slate, 1.5));
      });
      els.push(t("Root cause: demand commitments are not continuously synchronized with the current executable capacity of the controlling constraint.", 165, 560, 1270, 58, bodyStyle(26, C.ink, true)));
      els.push(t("The solution must make the active constraint visible, test feasibility and keep planning decisions governed.", 290, 635, 1010, 28, bodyStyle(19, C.slate)));
      return els;
    },
  },
  {
    title: "Core Operating Philosophy",
    thesis: "Every movement must pass through eligible resources and valid operating windows.",
    block: "Opening",
    draw: () => [
      ...sectionBand("FEASIBILITY GATE", C.green),
      ...node("Demand", 110, 310, 170, 58, C.lightBlue, "#BFD6EF"),
      ...node("Cargo", 110, 392, 170, 58, C.lightBlue, "#BFD6EF"),
      ...node("Assets", 110, 474, 170, 58, C.lightBlue, "#BFD6EF"),
      ...node("Route", 110, 556, 170, 58, C.lightBlue, "#BFD6EF"),
      ...node("Tide / bridge", 350, 350, 190, 58, C.lightGreen, "#C6DEC6"),
      ...node("Jetty / CTS", 350, 458, 190, 58, C.lightGreen, "#C6DEC6"),
      arrow(282, 339, 628, 438, C.slate, 1.4),
      arrow(282, 421, 628, 438, C.slate, 1.4),
      arrow(282, 503, 628, 438, C.slate, 1.4),
      arrow(542, 380, 628, 438, C.slate, 1.4),
      arrow(542, 488, 628, 438, C.slate, 1.4),
      rect(640, 330, 300, 220, C.navy, { radius: 18 }),
      t("Constraint-aware\nfeasibility gate", 690, 390, 200, 76, titleStyle(28, C.white)),
      arrow(952, 438, 1045, 388, C.green, 2),
      arrow(952, 438, 1045, 505, C.orange, 2),
      ...node("Feasible movement candidates", 1060, 345, 340, 82, C.lightGreen, "#BFD8BF", C.green),
      ...node("Reason-coded blockers", 1060, 468, 340, 82, C.lightOrange, "#EDC8A5", C.orange),
      t("Planner discretion remains possible, but it is captured through override reason, approval and audit.", 258, 662, 1060, 30, bodyStyle(20, C.slate)),
    ],
  },
  {
    title: "Vector Approach & Proprietary Scaffolding",
    thesis: "Vector brings the scheduling base. Blueprinting makes it ABL-specific.",
    block: "Opening",
    draw: () => {
      const els = [...sectionBand("VECTOR BUILD APPROACH", C.navy)];
      const layersData = [
        ["Governed planning platform", C.navy, C.white],
        ["ABL routes, assets, windows, approvals and integrations", C.blue, C.white],
        ["Dynamic constraint handling", C.green, C.white],
        ["Scenario and recovery engine", C.orange, C.white],
        ["Vector proprietary scheduling base", C.amber, C.white],
      ];
      layersData.forEach((l, i) => {
        const y = 270 + i * 78;
        els.push(rect(350 + i * 35, y, 900 - i * 70, 56, l[1], { radius: 10 }));
        els.push(t(l[0], 390 + i * 35, y + 16, 820 - i * 70, 24, bodyStyle(17, l[2], true)));
      });
      els.push(t("Configured around ABL-specific operating rules, assets, routes, tide and bridge logic, recovery workflows and governance.", 225, 705, 1150, 44, bodyStyle(23, C.ink, true)));
      return els;
    },
  },
  {
    title: "Product Concept",
    thesis: "Demand to publish. Evidence to recovery.",
    block: "Opening",
    draw: () => [
      ...sectionBand("END-TO-END PRODUCT FLOW", C.blue),
      ...flowNodes(["OGV demand", "Cargo layer", "Operating windows", "Movement candidates", "Conflict review", "Approval", "Publish", "Evidence & recovery"], 70, 375, 150, 76, 28, C.blue),
      t("The product creates one governed path from planning intent to approved execution, then supports monitoring and recovery decisions.", 170, 596, 1260, 52, bodyStyle(25, C.ink, true)),
      ...pill("Plan", 325, 690, 84, C.blue),
      ...pill("Govern", 494, 690, 104, C.green),
      ...pill("Publish", 682, 690, 104, C.green),
      ...pill("Monitor", 872, 690, 112, C.slate),
      ...pill("Recover", 1068, 690, 112, C.orange),
    ],
  },
  {
    title: "Release 1 Product Layer",
    thesis: "Release 1 proves the governed scheduling spine.",
    block: "Opening",
    draw: () => {
      const els = [...sectionBand("FIRST USABLE PRODUCT LAYER", C.green)];
      const blocks = [
        ["Master data\nand roles", C.lightBlue, C.blue],
        ["Demand and\ncargo layers", C.lightBlue, C.blue],
        ["Operating\nwindows", C.lightGreen, C.green],
        ["Candidate movement\ngeneration", C.lightGreen, C.green],
        ["Conflict output\nand override", C.lightOrange, C.orange],
        ["Approval, publish\nand audit", C.lightAmber, C.amber],
      ];
      blocks.forEach((b, i) => {
        const x = 130 + (i % 3) * 430;
        const y = 300 + Math.floor(i / 3) * 155;
        els.push(rect(x, y, 340, 94, b[0], { radius: 14, line: { color: b[2], width: 1.4 } }));
        els.push(t(b[0], x + 24, y + 24, 292, 46, titleStyle(23, b[2])));
      });
      els.push(t("Output: a working governed scheduling application for structured planning, feasibility review, approval and publication.", 190, 665, 1220, 48, bodyStyle(24, C.ink, true)));
      return els;
    },
  },
  {
    title: "Application Modules & Master Data Spine",
    thesis: "The product begins with controlled operating data.",
    block: "Demo Block 1",
    draw: () => {
      const els = [...sectionBand("DEMO BLOCK 1: CORE APP + HAPPY PATH", C.blue)];
      const cx = 800, cy = 455;
      els.push(rect(cx - 190, cy - 78, 380, 156, C.navy, { radius: 16 }));
      els.push(t("Operator\nCockpit", cx - 92, cy - 43, 184, 78, titleStyle(30, C.white)));
      const mods = [
        ["Access", 230, 285, C.blue],
        ["Master Data", 510, 245, C.blue],
        ["Planning", 890, 245, C.blue],
        ["Scheduling", 1180, 285, C.green],
        ["Exception", 1180, 585, C.orange],
        ["Telemetry", 890, 635, C.slate],
        ["Operations", 510, 635, C.slate],
        ["Audit", 230, 585, C.amber],
      ];
      mods.forEach((m) => {
        els.push(rect(m[1], m[2], 180, 66, m[2] < 400 ? C.lightBlue : C.pale, { radius: 12, line: { color: m[3], width: 1.3 } }));
        els.push(t(m[0], m[1] + 20, m[2] + 22, 140, 22, bodyStyle(17, m[3], true)));
        els.push(arrow(m[1] + 90, m[2] + 33, cx, cy, "#B8C6D6", 1.2));
      });
      els.push(...pill("Demo focus: modules, master data, assets, routes, windows", 465, 738, 670, C.blue));
      return els;
    },
  },
  {
    title: "OGV Demand To Feasible Schedule",
    thesis: "Demand becomes schedulable work only after cargo, route, asset and window checks.",
    block: "Demo Block 1",
    draw: () => {
      const els = [
        ...sectionBand("HAPPY PATH: DEMAND TO CANDIDATE SCHEDULE", C.blue),
        ...screenFrame(80, 245, 660, 430, "Planning cockpit - demand and windows", C.blue),
      ];
      const steps = [
        ["OGV demand", 805, 285, C.blue],
        ["Cargo layer", 1088, 285, C.white],
        ["Route steps", 805, 385, C.white],
        ["Asset / CTS fit", 1088, 385, C.white],
        ["Tide / bridge", 805, 485, C.white],
        ["Candidate schedule", 1088, 485, C.lightGreen],
      ];
      steps.forEach((s, i) => {
        els.push(...node(s[0], s[1], s[2], 230, 62, s[3], s[3] === C.white ? C.grey : s[3], s[3] === C.blue ? C.white : C.ink));
        if (i % 2 === 0) els.push(arrow(s[1] + 232, s[2] + 31, s[1] + 278, s[2] + 31, C.slate, 1.4));
        if (i === 1 || i === 3) els.push(arrow(s[1] - 20, s[2] + 64, s[1] - 20, s[2] + 94, C.slate, 1.4));
      });
      els.push(...callout(1, "Demand intake", 835, 620, C.blue));
      els.push(...callout(2, "Cargo layer sequence", 835, 666, C.blue));
      els.push(...callout(3, "Operating windows", 1120, 620, C.green));
      els.push(...callout(4, "Candidate movements", 1120, 666, C.green));
      return els;
    },
  },
  {
    title: "Approval, Publish & Audit Trail",
    thesis: "Published plans are controlled execution contracts.",
    block: "Demo Block 1",
    draw: () => [
      ...sectionBand("HAPPY PATH: GOVERNANCE TO PUBLISH", C.green),
      ...flowNodes(["Draft plan", "Conflict review", "Override reason", "ABL / Berau approval", "Publishability", "Published snapshot", "Export & audit"], 76, 310, 180, 72, 24, C.green),
      rect(190, 548, 1220, 120, C.lightGreen, { radius: 16, line: { color: "#C6DEC6", width: 1 } }),
      t("Governance principle", 232, 574, 270, 28, titleStyle(22, C.green)),
      t("Manual decisions remain possible, but each override, approval and publication creates a traceable decision lineage.", 514, 576, 780, 48, bodyStyle(22, C.ink, true)),
      ...pill("Demo cue: conflict review -> approval -> publish -> audit", 510, 715, 580, C.green),
    ],
  },
  {
    title: "Scenario & Exception Flow",
    thesis: "Simulate disruption before changing the plan.",
    block: "Demo Block 2",
    draw: () => [
      ...sectionBand("DEMO BLOCK 2: RECOVERY + SCENARIO", C.orange),
      t("Baseline plan", 160, 273, 220, 28, titleStyle(24, C.ink)),
      rect(160, 320, 520, 240, C.lightBlue, { radius: 16, line: { color: "#C7DAEE", width: 1.2 } }),
      ...flowNodes(["Published plan", "Active constraint", "Current conflict"], 190, 392, 135, 60, 30, C.blue),
      t("Scenario plan", 920, 273, 220, 28, titleStyle(24, C.ink)),
      rect(920, 320, 520, 240, C.lightOrange, { radius: 16, line: { color: "#EFC7A4", width: 1.2 } }),
      ...flowNodes(["Delay / outage", "Reassignment", "Projected impact"], 948, 392, 135, 60, 30, C.orange),
      arrow(700, 438, 900, 438, C.orange, 2),
      ...pill("Trip impact", 255, 635, 140, C.orange),
      ...pill("OGV risk", 450, 635, 112, C.orange),
      ...pill("Utilization", 645, 635, 126, C.orange),
      ...pill("Remaining blockers", 840, 635, 190, C.orange),
      ...pill("Promotion path", 1105, 635, 154, C.green),
    ],
  },
  {
    title: "Recovery Path To Publish",
    thesis: "Recovery is recommended, simulated, approved and then published.",
    block: "Demo Block 2",
    draw: () => [
      ...sectionBand("RECOVERY TO PUBLICATION", C.orange),
      ...flowNodes(["Active exception", "Recovery snapshot", "Ranked options", "Root-cause validation", "Scenario run", "Approval", "Publish recovery plan"], 70, 320, 178, 76, 25, C.orange),
      rect(270, 560, 1060, 112, C.lightOrange, { radius: 16, line: { color: "#EFC7A4", width: 1 } }),
      t("Demo sequence", 315, 590, 200, 28, titleStyle(23, C.orange)),
      t("Show one disruption from exception identification through ranked options, scenario validation, approval and recovery publication.", 535, 590, 690, 48, bodyStyle(21, C.ink, true)),
      ...pill("Proof pack", 562, 723, 118, C.amber),
      ...pill("Publishability", 730, 723, 150, C.green),
      ...pill("Audit lineage", 930, 723, 140, C.green),
    ],
  },
  {
    title: "Telemetry Evidence & Operational Monitoring",
    thesis: "Evidence informs the plan. Confirmation changes the execution state.",
    block: "Demo Block 3",
    draw: () => {
      const els = [...sectionBand("DEMO BLOCK 3: TELEMETRY + EVIDENCE", C.slate)];
      els.push(rect(82, 238, 820, 482, "#EAF1F8", { radius: 18, line: { color: "#C7D5E5", width: 1 } }));
      els.push(t("Navigational monitoring view", 115, 260, 420, 28, titleStyle(24, C.ink)));
      for (let i = 0; i < 9; i++) {
        els.push(line(120 + i * 85, 320, 1, 340, "#D6E0EA"));
        els.push(line(120, 320 + i * 40, 700, 1, "#D6E0EA"));
      }
      const assets = [
        [235, 430, C.green, "TB-12"],
        [430, 515, C.blue, "CTS-3"],
        [660, 405, C.orange, "B-08"],
      ];
      assets.forEach((a) => {
        els.push(rect(a[0], a[1], 44, 44, a[2], { radius: 22 }));
        els.push(t(a[3], a[0] - 16, a[1] + 50, 90, 18, smallStyle(12, C.ink, true)));
      });
      els.push(rect(960, 238, 520, 482, C.white, { radius: 18, line: { color: C.grey, width: 1.2 } }));
      els.push(t("Evidence and trust panel", 1000, 266, 360, 28, titleStyle(24, C.ink)));
      const states = [
        ["AIS / GPS evidence", C.blue],
        ["Latest asset state", C.slate],
        ["Geofence / ETA variance", C.orange],
        ["Event candidate", C.amber],
        ["Confirm or reject", C.green],
        ["Actual execution state", C.green],
      ];
      states.forEach((s, i) => {
        els.push(rect(1000, 326 + i * 55, 420, 36, i === 4 ? C.lightGreen : C.pale, { radius: 8, line: { color: s[1], width: 1 } }));
        els.push(t(s[0], 1020, 335 + i * 55, 300, 18, smallStyle(14, s[1], true)));
      });
      return els;
    },
  },
  {
    title: "Delivery Roadmap: Release 1 Focus",
    thesis: "Blueprint first. Release 1 validates governed scheduling by Weeks 17-18.",
    block: "Delivery Roadmap",
    draw: () => [
      ...timelineRoadmap(),
      t("Release 1 validates the core flow, business rules, operating windows, approvals and planner adoption before later layers are activated.", 208, 730, 1180, 52, bodyStyle(23, C.ink, true)),
    ],
  },
  {
    title: "Adoption Review & Client Alignment",
    thesis: "The next decision is readiness: rules, data, owners, users and integrations.",
    block: "Delivery Roadmap",
    draw: () => {
      const els = [...sectionBand("CLIENT ALIGNMENT BOARD", C.amber)];
      const cols = [
        ["Operating rules", C.green, "Validated constraints\nand window logic"],
        ["Data ownership", C.blue, "Master data and\ndemand responsibility"],
        ["Pilot users", C.orange, "Named planners and\napprovers"],
        ["Approval authority", C.green, "ABL and Berau\npublish governance"],
        ["Integration access", C.slate, "Source owners and\nreadiness path"],
      ];
      cols.forEach((col, i) => {
        const x = 95 + i * 295;
        els.push(rect(x, 290, 240, 250, C.white, { radius: 16, line: { color: col[1], width: 1.5 } }));
        els.push(rect(x, 290, 240, 54, col[1], { radius: 16 }));
        els.push(rect(x, 334, 240, 11, col[1]));
        els.push(t(col[0], x + 20, 309, 200, 22, bodyStyle(16, C.white, true)));
        els.push(t(col[2], x + 24, 390, 190, 70, bodyStyle(19, C.ink, true)));
        els.push(rect(x + 88, 482, 64, 36, C.lightGreen, { radius: 18, line: { color: C.green, width: 1 } }));
        els.push(t("check", x + 103, 491, 40, 18, smallStyle(11, C.green, true)));
      });
      els.push(rect(245, 650, 1110, 62, C.navy, { radius: 18 }));
      els.push(t("Build  ->  Operate  ->  Transfer  ->  Audit", 490, 666, 620, 28, titleStyle(23, C.white)));
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
