import fs from "node:fs/promises";
import path from "node:path";
import {
  Presentation,
  PresentationFile,
  FileBlob,
  column,
  row,
  grid,
  panel,
  text,
  image,
  shape,
  rule,
  fill,
  fixed,
  hug,
  wrap,
  grow,
  fr,
  auto,
} from "@oai/artifact-tool";

const ROOT = path.resolve("F:/ocean/artifacts/coalflow_deck");
const OUT = path.join(ROOT, "output");
const SCRATCH = path.join(ROOT, "scratch");
const RENDERS = path.join(SCRATCH, "renders");
const PPTX_RENDERS = path.join(SCRATCH, "pptx-renders");

await fs.mkdir(OUT, { recursive: true });
await fs.mkdir(RENDERS, { recursive: true });
await fs.mkdir(PPTX_RENDERS, { recursive: true });

const W = 1920;
const H = 1080;

const C = {
  paper: "#F7F4EE",
  ink: "#10212B",
  muted: "#53656D",
  blue: "#0E6B83",
  teal: "#2F8C73",
  amber: "#C8852C",
  coral: "#B9654A",
  mist: "#DCE5E7",
  soft: "#EAF0F1",
  sand: "#EADFCF",
  white: "#FFFFFF",
};

const FONT = {
  display: "Aptos Display",
  body: "Aptos",
};

function txt(value, opts = {}) {
  return text(value, {
    name: opts.name,
    width: opts.width ?? fill,
    height: opts.height ?? hug,
    style: {
      fontFamily: opts.fontFamily ?? FONT.body,
      fontSize: opts.fontSize ?? 28,
      color: opts.color ?? C.ink,
      bold: opts.bold ?? false,
      italic: opts.italic ?? false,
      lineSpacing: opts.lineSpacing,
      letterSpacing: opts.letterSpacing,
      textAlign: opts.textAlign,
    },
  });
}

function eyebrow(value, name) {
  return txt(value.toUpperCase(), {
    name,
    fontSize: 16,
    color: C.blue,
    bold: true,
    letterSpacing: 1.2,
  });
}

function title(value, name, width = fill, size = 52) {
  return txt(value, {
    name,
    width,
    fontFamily: FONT.display,
    fontSize: size,
    color: C.ink,
    bold: true,
  });
}

function body(value, name, width = fill, size = 25, color = C.muted) {
  return txt(value, {
    name,
    width,
    fontSize: size,
    color,
  });
}

function smallCaps(value, name, color = C.blue) {
  return txt(value.toUpperCase(), {
    name,
    fontSize: 17,
    color,
    bold: true,
    letterSpacing: 1.1,
  });
}

function metric(value, label, color, idx) {
  return column(
    { name: `metric-${idx}`, width: fill, height: hug, gap: 10 },
    [
      txt(value, {
        name: `metric-value-${idx}`,
        fontFamily: FONT.display,
        fontSize: 54,
        color,
        bold: true,
      }),
      txt(label, {
        name: `metric-label-${idx}`,
        fontSize: 18,
        color: C.muted,
      }),
    ],
  );
}

function footer(source, page) {
  return row(
    { name: `footer-${page}`, width: fill, height: hug, gap: 20, align: "center" },
    [
      txt(source, {
        name: `source-${page}`,
        width: grow(1),
        fontSize: 14,
        color: C.muted,
      }),
      txt(String(page).padStart(2, "0"), {
        name: `page-${page}`,
        width: fixed(42),
        fontSize: 14,
        color: C.blue,
        bold: true,
        textAlign: "right",
      }),
    ],
  );
}

function slideRoot(children, page, source = "Project docs") {
  return panel(
    { name: `slide-panel-${page}`, width: fill, height: fill, fill: C.paper },
    column(
      {
        name: `slide-root-${page}`,
        width: fill,
        height: fill,
        padding: { x: 78, y: 62 },
        gap: 26,
      },
      [
        ...children,
        shape({ name: `spacer-${page}`, width: fill, height: grow(1), fill: C.paper }),
        footer(source, page),
      ],
    ),
  );
}

function thinAccent(name) {
  return rule({
    name,
    width: fixed(240),
    stroke: C.blue,
    weight: 4,
  });
}

function labeledChip(label, color, idx, textColor = C.white) {
  return panel(
    {
      name: `chip-${idx}`,
      width: hug,
      height: hug,
      fill: color,
      borderRadius: 999,
      padding: { x: 16, y: 10 },
    },
    txt(label, {
      name: `chip-label-${idx}`,
      width: hug,
      fontSize: 18,
      color: textColor,
      bold: true,
    }),
  );
}

function screenCard(titleText, imagePath, idx) {
  return column(
    { name: `screen-card-${idx}`, width: fill, height: fill, gap: 12 },
    [
      txt(titleText, {
        name: `screen-title-${idx}`,
        fontSize: 20,
        color: C.blue,
        bold: true,
      }),
      panel(
        {
          name: `screen-image-panel-${idx}`,
          width: fill,
          height: fill,
          fill: C.white,
          borderRadius: 18,
          padding: 12,
        },
        image({
          name: `screen-image-${idx}`,
          dataUrl: imagePath,
          width: fill,
          height: fill,
          fit: "contain",
          alt: titleText,
          borderRadius: 14,
        }),
      ),
    ],
  );
}

const presentation = Presentation.create({
  slideSize: { width: W, height: H },
});

async function saveBlob(blob, filePath) {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  await fs.writeFile(filePath, bytes);
}

async function loadPngDataUrl(filePath) {
  const bytes = await fs.readFile(filePath);
  return `data:image/png;base64,${bytes.toString("base64")}`;
}

const SCREENSHOT = {
  demand: await loadPngDataUrl("F:/ocean/docs/evidence/phase1/screenshots/01_ogv_demand.png"),
  tide: await loadPngDataUrl("F:/ocean/docs/evidence/phase1/screenshots/02_tide_bridge.png"),
  published: await loadPngDataUrl("F:/ocean/docs/evidence/phase1/screenshots/03_published_plan.png"),
  approvals: await loadPngDataUrl("F:/ocean/docs/evidence/phase1/screenshots/04_approvals.png"),
};

// Slide 1 — business context / quantified opening
{
  const s = presentation.slides.add();
  s.compose(
    slideRoot(
      [
        eyebrow("Business context", "s1-eyebrow"),
        title("Berau output meets ABL fleet scale.", "s1-title", fill, 58),
        body(
          "The planning challenge is not abstract: it sits between a very large monthly cargo flow and a highly distributed marine asset network.",
          "s1-body",
          wrap(1320),
          25,
        ),
        thinAccent("s1-rule"),
        grid(
          {
            name: "s1-grid",
            width: fill,
            height: fixed(620),
            columns: [fr(0.95), fr(1.05)],
            rows: [fr(1)],
            columnGap: 30,
          },
          [
            panel(
              {
                name: "s1-left-panel",
                width: fill,
                height: fill,
                fill: C.soft,
                borderRadius: 28,
                padding: { x: 30, y: 28 },
              },
              column(
                { name: "s1-left", width: fill, height: fill, gap: 18 },
                [
                  eyebrow("Berau coal", "s1-left-eyebrow"),
                  txt("35.9 Mt", {
                    name: "s1-berau-hero",
                    fontFamily: FONT.display,
                    fontSize: 82,
                    color: C.blue,
                    bold: true,
                  }),
                  body("Coal production in 2024", "s1-berau-label", fill, 22, C.ink),
                  rule({ name: "s1-left-rule", width: fill, stroke: C.mist, weight: 2 }),
                  row(
                    { name: "s1-left-metrics", width: fill, height: hug, gap: 26 },
                    [
                      metric("≈3.0 Mt", "Average / month", C.teal, "s1a"),
                      metric("≈98 kt", "Average / day", C.amber, "s1b"),
                    ],
                  ),
                  body(
                    "This is the demand rhythm the plan must absorb before one tug, barge, jetty, or CTS move is assigned.",
                    "s1-left-note",
                    fill,
                    22,
                    C.muted,
                  ),
                ],
              ),
            ),
            panel(
              {
                name: "s1-right-panel",
                width: fill,
                height: fill,
                fill: C.white,
                borderRadius: 28,
                padding: { x: 30, y: 28 },
              },
              column(
                { name: "s1-right", width: fill, height: fill, gap: 18 },
                [
                  eyebrow("ABL ocean-fleet partner", "s1-right-eyebrow"),
                  row(
                    { name: "s1-right-top", width: fill, height: hug, gap: 28 },
                    [
                      metric("100M+", "Tonnes transshipped / year", C.amber, "s1c"),
                      metric("20–55 kt", "CTS throughput / day", C.blue, "s1d"),
                    ],
                  ),
                  rule({ name: "s1-right-rule", width: fill, stroke: C.mist, weight: 2 }),
                  grid(
                    {
                      name: "s1-right-grid",
                      width: fill,
                      height: fixed(180),
                      columns: [fr(1), fr(1), fr(1)],
                      rows: [fr(1)],
                      columnGap: 18,
                    },
                    [
                      metric("15", "Cargo Transfer Ships", C.blue, "s1e"),
                      metric("61", "Tug + barge sets", C.teal, "s1f"),
                      metric("11", "Ocean-going vessels", C.coral, "s1g"),
                    ],
                  ),
                  body(
                    "The software has to turn this capacity into a coordinated sequence, not merely display it.",
                    "s1-right-note",
                    fill,
                    22,
                    C.muted,
                  ),
                ],
              ),
            ),
          ],
        ),
      ],
      1,
      "Sources: Berau Coal Energy Annual Report 2024; ABL official site.",
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// Slide 2 — current reality
{
  const s = presentation.slides.add();
  s.compose(
    slideRoot(
      [
        eyebrow("Current reality", "s2-eyebrow"),
        title("Data exists. Orchestration is still manual.", "s2-title"),
        body(
          "Today’s operation already produces useful signals; the friction is that the plan is still assembled, reconciled, and updated by hand.",
          "s2-body",
          wrap(1200),
        ),
        thinAccent("s2-rule"),
        grid(
          {
            name: "s2-grid",
            width: fill,
            height: fixed(520),
            columns: [fr(1), fr(1), fr(1)],
            columnGap: 28,
          },
          [
            panel(
              {
                name: "s2-panel1",
                width: fill,
                height: fill,
                fill: C.soft,
                borderRadius: 24,
                padding: { x: 24, y: 22 },
              },
              column(
                { name: "s2-col1", width: fill, height: fill, gap: 18, justify: "between" },
                [
                  column(
                    { name: "s2-col1-top", width: fill, height: hug, gap: 18 },
                    [
                      eyebrow("01", "s2-c1-num"),
                      txt("Excel schedule", {
                        name: "s2-c1-title",
                        fontFamily: FONT.display,
                        fontSize: 40,
                        color: C.ink,
                        bold: true,
                      }),
                      body(
                        "A usable planning workspace—but one that depends on manual collation, edits, and reconciliation.",
                        "s2-c1-body",
                        fill,
                        27,
                      ),
                    ],
                  ),
                  column(
                    { name: "s2-col1-bottom", width: fill, height: hug, gap: 14 },
                    [
                      rule({ name: "s2-c1-rule", width: fill, stroke: C.mist, weight: 2 }),
                      smallCaps("Current state", "s2-c1-kicker", C.blue),
                      body("The data is present.\nThe workflow is brittle.", "s2-c1-note", fill, 27, C.blue),
                    ],
                  ),
                ],
              ),
            ),
            panel(
              {
                name: "s2-panel2",
                width: fill,
                height: fill,
                fill: C.white,
                borderRadius: 24,
                padding: { x: 24, y: 22 },
              },
              column(
                { name: "s2-col2", width: fill, height: fill, gap: 18, justify: "between" },
                [
                  column(
                    { name: "s2-col2-top", width: fill, height: hug, gap: 18 },
                    [
                      eyebrow("02", "s2-c2-num"),
                      txt("Spinergie layer", {
                        name: "s2-c2-title",
                        fontFamily: FONT.display,
                        fontSize: 40,
                        color: C.ink,
                        bold: true,
                      }),
                      body(
                        "Digital daily reports, cycle KPIs, real-time AIS visibility, GPS evidence, and environmental reporting already exist around the operation.",
                        "s2-c2-body",
                        fill,
                        27,
                      ),
                    ],
                  ),
                  column(
                    { name: "s2-col2-bottom", width: fill, height: hug, gap: 14 },
                    [
                      rule({ name: "s2-c2-rule", width: fill, stroke: C.mist, weight: 2 }),
                      smallCaps("Evidence layer", "s2-c2-kicker", C.teal),
                      body("Useful signals.\nNot yet the planning brain.", "s2-c2-note", fill, 27, C.teal),
                    ],
                  ),
                ],
              ),
            ),
            panel(
              {
                name: "s2-panel3",
                width: fill,
                height: fill,
                fill: C.sand,
                borderRadius: 24,
                padding: { x: 24, y: 22 },
              },
              column(
                { name: "s2-col3", width: fill, height: fill, gap: 18, justify: "between" },
                [
                  column(
                    { name: "s2-col3-top", width: fill, height: hug, gap: 18 },
                    [
                      eyebrow("03", "s2-c3-num"),
                      txt("The gap", {
                        name: "s2-c3-title",
                        fontFamily: FONT.display,
                        fontSize: 40,
                        color: C.ink,
                        bold: true,
                      }),
                      body(
                        "What is missing is a governed model that turns demand, assets, constraints, and live evidence into one executable plan.",
                        "s2-c3-body",
                        fill,
                        27,
                      ),
                    ],
                  ),
                  column(
                    { name: "s2-col3-bottom", width: fill, height: hug, gap: 14 },
                    [
                      rule({ name: "s2-c3-rule", width: fill, stroke: "#D7C7AF", weight: 2 }),
                      smallCaps("Needed next", "s2-c3-kicker", C.amber),
                      body("From data presence\n→ planning confidence.", "s2-c3-note", fill, 27, C.amber),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
        panel(
          {
            name: "s2-bottom-panel",
            width: fill,
            height: hug,
            fill: C.soft,
            borderRadius: 22,
            padding: { x: 24, y: 18 },
          },
          body(
            "The gap is not lack of data. It is lack of a single governed workspace that converts data into a plan operators can execute and revise together.",
            "s2-bottom-note",
            fill,
            24,
            C.ink,
          ),
        ),
      ],
      2,
      "Sources: project BRD; Spinergie press release, June 2024.",
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// Slide 3 — key players and demand/fleet side
{
  const s = presentation.slides.add();
  s.compose(
    slideRoot(
      [
        eyebrow("Operating model", "s3-eyebrow"),
        title("The network has two clocks.", "s3-title"),
        body(
          "Demand wants certainty. Fleet operations live inside constraints. The tool exists to make those two clocks agree.",
          "s3-body",
          wrap(1120),
        ),
        thinAccent("s3-rule"),
        grid(
          {
            name: "s3-grid",
            width: fill,
            height: fixed(500),
            columns: [fr(1), fr(0.18), fr(1)],
            columnGap: 20,
          },
          [
            panel(
              {
                name: "s3-demand-panel",
                width: fill,
                height: fill,
                fill: C.soft,
                borderRadius: 26,
                padding: { x: 28, y: 24 },
              },
              column(
                { name: "s3-demand", width: fill, height: fill, gap: 16 },
                [
                  labeledChip("Demand side", C.blue, "s3a"),
                  txt("Berau commercial + scheduling", { name: "s3-demand-title", fontSize: 32, bold: true }),
                  row(
                    { name: "s3-demand-metrics", width: fill, height: hug, gap: 24 },
                    [
                      metric("35.9 Mt", "2024 output", C.blue, "s3d1"),
                      metric("≈3.0 Mt", "Monthly flow", C.teal, "s3d2"),
                    ],
                  ),
                  body("OGV voyages and laycan\nCoal grade + layer sequence\nCustomer commitments\nStockpile / jetty readiness", "s3-demand-body", fill, 24),
                ],
              ),
            ),
            column(
              { name: "s3-middle", width: fill, height: fill, gap: 16, align: "center", justify: "center" },
              [
                txt("↔", { name: "s3-arrow", width: hug, fontSize: 72, color: C.amber, bold: true }),
                body("Shared constraints\nshape every decision", "s3-middle-label", fill, 22, C.muted),
              ],
            ),
            panel(
              {
                name: "s3-fleet-panel",
                width: fill,
                height: fill,
                fill: C.white,
                borderRadius: 26,
                padding: { x: 28, y: 24 },
              },
              column(
                { name: "s3-fleet", width: fill, height: fill, gap: 16 },
                [
                  labeledChip("Fleet side", C.teal, "s3b"),
                  txt("ABL dispatch + operations", { name: "s3-fleet-title", fontSize: 32, bold: true }),
                  row(
                    { name: "s3-fleet-metrics", width: fill, height: hug, gap: 18 },
                    [
                      metric("15", "CTS", C.blue, "s3f1"),
                      metric("61", "Tug + barge", C.teal, "s3f2"),
                      metric("11", "OGV", C.coral, "s3f3"),
                    ],
                  ),
                  body("Asset availability\nCTS / floating-crane capacity\nJetty queue + loading rate\nRiver movement + return cycle", "s3-fleet-body", fill, 24),
                ],
              ),
            ),
          ],
        ),
        panel(
          {
            name: "s3-bottom-panel",
            width: fill,
            height: hug,
            fill: C.sand,
            borderRadius: 18,
            padding: { x: 20, y: 16 },
          },
          body(
            "Shared constraints: tide  •  bridge  •  weather  •  compatibility  •  safety  •  demurrage",
            "s3-bottom",
            fill,
            24,
            C.ink,
          ),
        ),
      ],
      3,
      "Sources: project docs; ABL official site.",
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// Slide 4 — whole solution scope
{
  const s = presentation.slides.add();
  s.compose(
    slideRoot(
      [
        eyebrow("Solution scope", "s4-eyebrow"),
        title("Not a map. Not digital Excel. A planning engine.", "s4-title"),
        body(
          "The product turns multiple evidence streams into one auditable operating plan, while keeping planned, observed, and recommended states separate.",
          "s4-body",
          wrap(1260),
        ),
        thinAccent("s4-rule"),
        grid(
          {
            name: "s4-grid",
            width: fill,
            height: fixed(450),
            columns: [fr(1), fr(1.05), fr(1)],
            columnGap: 28,
          },
          [
            panel(
              {
                name: "s4-input-panel",
                width: fill,
                height: fill,
                fill: C.white,
                borderRadius: 24,
                padding: { x: 24, y: 24 },
              },
              column(
                { name: "s4-inputs", width: fill, height: fill, gap: 18, justify: "between" },
                [
                  column(
                    { name: "s4-inputs-top", width: fill, height: hug, gap: 18 },
                    [
                      eyebrow("Inputs", "s4-in-eyebrow"),
                      body("OGV demand\nGrade + stockpile readiness\nFleet + jetty status\nTide / bridge / weather\nAIS + later GPS evidence", "s4-inputs-body", fill, 28),
                    ],
                  ),
                  body("What the planner knows", "s4-inputs-note", fill, 24, C.blue),
                ],
              ),
            ),
            panel(
              {
                name: "s4-engine-panel",
                width: fill,
                height: fill,
                fill: C.soft,
                borderRadius: 28,
                padding: { x: 28, y: 28 },
              },
              column(
                { name: "s4-engine", width: fill, height: fill, gap: 18, justify: "center" },
                [
                  eyebrow("Core", "s4-engine-eyebrow"),
                  txt("Constraint-aware planning", {
                    name: "s4-engine-title",
                    fontFamily: FONT.display,
                    fontSize: 42,
                    color: C.ink,
                    bold: true,
                  }),
                  body("Assign → validate → simulate → govern", "s4-engine-body", fill, 26, C.blue),
                ],
              ),
            ),
            panel(
              {
                name: "s4-output-panel",
                width: fill,
                height: fill,
                fill: C.sand,
                borderRadius: 24,
                padding: { x: 24, y: 24 },
              },
              column(
                { name: "s4-outputs", width: fill, height: fill, gap: 18, justify: "between" },
                [
                  column(
                    { name: "s4-outputs-top", width: fill, height: hug, gap: 18 },
                    [
                      eyebrow("Outputs", "s4-out-eyebrow"),
                      body("Feasible schedule\nConflict list\nScenario comparison\nApproval chain\nPublished live plan", "s4-outputs-body", fill, 28),
                    ],
                  ),
                  body("What the planner changes", "s4-outputs-note", fill, 24, C.amber),
                ],
              ),
            ),
          ],
        ),
        body(
          "Planned  •  Observed  •  Confirmed  •  Derived  •  Recommended",
          "s4-state-row",
          fill,
          24,
          C.blue,
        ),
        panel(
          {
            name: "s4-bottom-panel",
            width: fill,
            height: hug,
            fill: C.sand,
            borderRadius: 20,
            padding: { x: 22, y: 16 },
          },
          body(
            "Product surfaces: demand board  •  assignment board  •  tide / bridge windows  •  simulation  •  approvals  •  published plan",
            "s4-bottom-note",
            fill,
            23,
            C.ink,
          ),
        ),
      ],
      4,
      "Source: project planning scope and data architecture docs.",
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// Slide 5 — current product demo bridge
{
  const s = presentation.slides.add();
  s.compose(
    slideRoot(
      [
        eyebrow("Bridge to the demo", "s5-eyebrow"),
        title("When we say “constraint-aware,” this is what users will see.", "s5-title"),
        body(
          "The current product already exposes the spine of the operating model you just saw.",
          "s5-body",
          wrap(1100),
        ),
        thinAccent("s5-rule"),
        grid(
          {
            name: "s5-grid",
            width: fill,
            height: fixed(570),
            columns: [fr(0.95), fr(1.05)],
            columnGap: 32,
          },
          [
            column(
              { name: "s5-left", width: fill, height: fill, gap: 18 },
              [
                body("1. What demand must be served?", "s5-q1", fill, 27, C.ink),
                body("2. Which windows constrain movement?", "s5-q2", fill, 27, C.ink),
                body("3. What plan is safe to publish?", "s5-q3", fill, 27, C.ink),
                body("4. Who approved the version now in force?", "s5-q4", fill, 27, C.ink),
                rule({ name: "s5-left-rule", width: fill, stroke: C.mist, weight: 2 }),
                body(
                  "The live demo follows the same story:\nOGV demand → constraints → approvals → published plan.",
                  "s5-left-note",
                  fill,
                  25,
                  C.blue,
                ),
              ],
            ),
            grid(
              {
                name: "s5-screens",
                width: fill,
                height: fill,
                columns: [fr(1), fr(1)],
                rows: [fr(1), fr(1)],
                columnGap: 18,
                rowGap: 18,
              },
              [
                screenCard(
                  "OGV Demand & Laycan",
                  SCREENSHOT.demand,
                  "a",
                ),
                screenCard(
                  "Tide & Bridge Window",
                  SCREENSHOT.tide,
                  "b",
                ),
                screenCard(
                  "Approvals",
                  SCREENSHOT.approvals,
                  "c",
                ),
                screenCard(
                  "Published Plan",
                  SCREENSHOT.published,
                  "d",
                ),
              ],
            ),
          ],
        ),
      ],
      5,
      "Source: current Coalflow Tower product evidence.",
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// Slide 6 — asset + constraint logic
{
  const s = presentation.slides.add();
  s.compose(
    slideRoot(
      [
        eyebrow("Solution approach", "s6-eyebrow"),
        title("Manage the asset chain, not just the asset list.", "s6-title"),
        body(
          "A plan is only feasible when every resource handoff survives both operational and environmental constraints.",
          "s6-body",
          wrap(1200),
        ),
        thinAccent("s6-rule"),
        grid(
          {
            name: "s6-grid",
            width: fill,
            height: fixed(450),
            columns: [fr(1), fr(1), fr(1), fr(1), fr(1)],
            columnGap: 16,
          },
          [
            panel(
              {
                name: "s6-panel1",
                width: fill,
                height: fill,
                fill: C.soft,
                borderRadius: 24,
                padding: { x: 20, y: 20 },
              },
              column(
              { name: "s6-step1", width: fill, height: fill, gap: 16, justify: "between" },
              [
                column(
                  { name: "s6-step1-top", width: fill, height: hug, gap: 16 },
                  [
                    eyebrow("01", "s6a"),
                    txt("Tug + barge", { name: "s6-title1", fontSize: 30, bold: true }),
                  ],
                ),
                body("Availability\nCompatibility\nLoaded / empty speed", "s6-body1", fill, 25),
              ],
            ),
            ),
            panel(
              {
                name: "s6-panel2",
                width: fill,
                height: fill,
                fill: C.white,
                borderRadius: 24,
                padding: { x: 20, y: 20 },
              },
              column(
              { name: "s6-step2", width: fill, height: fill, gap: 16, justify: "between" },
              [
                column(
                  { name: "s6-step2-top", width: fill, height: hug, gap: 16 },
                  [
                    eyebrow("02", "s6b"),
                    txt("Jetty", { name: "s6-title2", fontSize: 30, bold: true }),
                  ],
                ),
                column(
                  { name: "s6-step2-bottom", width: fill, height: hug, gap: 14 },
                  [
                    body("Queue\nLoading rate\nGrade readiness", "s6-body2", fill, 25),
                    body("1.5–3.5k MT/h", "s6-stat2", fill, 25, C.blue),
                  ],
                ),
              ],
            ),
            ),
            panel(
              {
                name: "s6-panel3",
                width: fill,
                height: fill,
                fill: C.sand,
                borderRadius: 24,
                padding: { x: 20, y: 20 },
              },
              column(
              { name: "s6-step3", width: fill, height: fill, gap: 16, justify: "between" },
              [
                column(
                  { name: "s6-step3-top", width: fill, height: hug, gap: 16 },
                  [
                    eyebrow("03", "s6c"),
                    txt("River route", { name: "s6-title3", fontSize: 30, bold: true }),
                  ],
                ),
                body("Tide\nBridge window\nDraft / weather", "s6-body3", fill, 25),
              ],
            ),
            ),
            panel(
              {
                name: "s6-panel4",
                width: fill,
                height: fill,
                fill: C.soft,
                borderRadius: 24,
                padding: { x: 20, y: 20 },
              },
              column(
              { name: "s6-step4", width: fill, height: fill, gap: 16, justify: "between" },
              [
                column(
                  { name: "s6-step4-top", width: fill, height: hug, gap: 16 },
                  [
                    eyebrow("04", "s6d"),
                    txt("CTS / FC", { name: "s6-title4", fontSize: 30, bold: true }),
                  ],
                ),
                column(
                  { name: "s6-step4-bottom", width: fill, height: hug, gap: 14 },
                  [
                    body("Rate\nQueue\nDowntime", "s6-body4", fill, 25),
                    body("20–55 kt/day", "s6-stat4", fill, 25, C.blue),
                  ],
                ),
              ],
            ),
            ),
            panel(
              {
                name: "s6-panel5",
                width: fill,
                height: fill,
                fill: C.white,
                borderRadius: 24,
                padding: { x: 20, y: 20 },
              },
              column(
              { name: "s6-step5", width: fill, height: fill, gap: 16, justify: "between" },
              [
                column(
                  { name: "s6-step5-top", width: fill, height: hug, gap: 16 },
                  [
                    eyebrow("05", "s6e"),
                    txt("OGV", { name: "s6-title5", fontSize: 30, bold: true }),
                  ],
                ),
                column(
                  { name: "s6-step5-bottom", width: fill, height: hug, gap: 14 },
                  [
                    body("Laycan\nLayer sequence\nDemurrage risk", "s6-body5", fill, 25),
                    body("≈76k DWT class", "s6-stat5", fill, 25, C.blue),
                  ],
                ),
              ],
            ),
            ),
          ],
        ),
        panel(
          {
            name: "s6-quant-band",
            width: fill,
            height: hug,
            fill: C.sand,
            borderRadius: 20,
            padding: { x: 22, y: 16 },
          },
          body(
            "Capacity is distributed across the chain. A fast CTS cannot recover a missed tide; a ready tug cannot compensate for a wrong grade sequence.",
            "s6-quant-note",
            fill,
            24,
            C.ink,
          ),
        ),
        panel(
          {
            name: "s6-bottom-panel",
            width: fill,
            height: hug,
            fill: C.soft,
            borderRadius: 22,
            padding: { x: 24, y: 18 },
          },
          body(
            "The planner’s job is not “where is the vessel?” but “which next move keeps the whole chain feasible?”",
            "s6-bottom-note",
            fill,
            26,
            C.ink,
          ),
        ),
      ],
      6,
      "Source: project operating-model and planning-scope docs.",
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// Slide 7 — roadmap near term
{
  const s = presentation.slides.add();
  s.compose(
    slideRoot(
      [
        eyebrow("Roadmap — near term", "s7-eyebrow"),
        title("First build the planner’s spine.", "s7-title"),
        body(
          "The product matures in layers: structured planning first, consequence modeling next, then live evidence.",
          "s7-body",
          wrap(1180),
        ),
        thinAccent("s7-rule"),
        grid(
          {
            name: "s7-grid",
            width: fill,
            height: fixed(480),
            columns: [fr(1), fr(1), fr(1)],
            columnGap: 26,
          },
          [
            panel(
              {
                name: "s7-panel1",
                width: fill,
                height: fill,
                fill: C.soft,
                borderRadius: 24,
                padding: { x: 24, y: 22 },
              },
              column(
                { name: "s7-col1", width: fill, height: fill, gap: 16, justify: "between" },
                [
                  column(
                    { name: "s7-col1-top", width: fill, height: hug, gap: 16 },
                    [
                      eyebrow("Now", "s7a"),
                      txt("1. Digital scheduling model", { name: "s7-title1", fontSize: 33, bold: true }),
                      body("Replace Excel with structured demand, manual availability, conflicts, approvals, and a published plan.", "s7-body1", fill, 25),
                    ],
                  ),
                  column(
                    { name: "s7-col1-bottom", width: fill, height: hug, gap: 12 },
                    [
                      smallCaps("User sees", "s7-kicker1", C.blue),
                      body("OGV demand • constraints • approvals", "s7-note1", fill, 23, C.blue),
                      smallCaps("Planning maturity", "s7-maturity1", C.muted),
                      body("Manual → governed", "s7-maturity-body1", fill, 23, C.ink),
                    ],
                  ),
                ],
              ),
            ),
            panel(
              {
                name: "s7-panel2",
                width: fill,
                height: fill,
                fill: C.white,
                borderRadius: 24,
                padding: { x: 24, y: 22 },
              },
              column(
                { name: "s7-col2", width: fill, height: fill, gap: 16, justify: "between" },
                [
                  column(
                    { name: "s7-col2-top", width: fill, height: hug, gap: 16 },
                    [
                      eyebrow("Next", "s7b"),
                      txt("2. Simulation + scenarios", { name: "s7-title2", fontSize: 33, bold: true }),
                      body("Test delays, outages, and window changes before committing a new version.", "s7-body2", fill, 25),
                    ],
                  ),
                  column(
                    { name: "s7-col2-bottom", width: fill, height: hug, gap: 12 },
                    [
                      smallCaps("User sees", "s7-kicker2", C.teal),
                      body("Baseline vs revised plan", "s7-note2", fill, 23, C.teal),
                      smallCaps("Planning maturity", "s7-maturity2", C.muted),
                      body("Reactive → comparative", "s7-maturity-body2", fill, 23, C.ink),
                    ],
                  ),
                ],
              ),
            ),
            panel(
              {
                name: "s7-panel3",
                width: fill,
                height: fill,
                fill: C.sand,
                borderRadius: 24,
                padding: { x: 24, y: 22 },
              },
              column(
                { name: "s7-col3", width: fill, height: fill, gap: 16, justify: "between" },
                [
                  column(
                    { name: "s7-col3-top", width: fill, height: hug, gap: 16 },
                    [
                      eyebrow("Then", "s7c"),
                      txt("3. GPS / AIS tracking", { name: "s7-title3", fontSize: 33, bold: true }),
                      body("Connect planned schedules to live movement, geofences, and ETA variance.", "s7-body3", fill, 25),
                    ],
                  ),
                  column(
                    { name: "s7-col3-bottom", width: fill, height: hug, gap: 12 },
                    [
                      smallCaps("User sees", "s7-kicker3", C.amber),
                      body("Plan vs actual movement", "s7-note3", fill, 23, C.amber),
                      smallCaps("Planning maturity", "s7-maturity3", C.muted),
                      body("Planned → observable", "s7-maturity-body3", fill, 23, C.ink),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
        panel(
          {
            name: "s7-bottom-panel",
            width: fill,
            height: hug,
            fill: C.soft,
            borderRadius: 20,
            padding: { x: 24, y: 18 },
          },
          body(
            "The current demo sits at the first milestone: the governed planning spine is already visible.",
            "s7-bottom-note",
            fill,
            24,
            C.ink,
          ),
        ),
      ],
      7,
      "Source: project roadmap docs.",
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// Slide 8 — roadmap mature product
{
  const s = presentation.slides.add();
  s.compose(
    slideRoot(
      [
        eyebrow("Roadmap — mature product", "s8-eyebrow"),
        title("Then let the field speak back.", "s8-title"),
        body(
          "The mature product does not stop at visibility; it turns trusted events into better decisions.",
          "s8-body",
          wrap(1200),
        ),
        thinAccent("s8-rule"),
        grid(
          {
            name: "s8-grid",
            width: fill,
            height: fixed(480),
            columns: [fr(1), fr(1), fr(1)],
            columnGap: 26,
          },
          [
            panel(
              {
                name: "s8-panel1",
                width: fill,
                height: fill,
                fill: C.white,
                borderRadius: 24,
                padding: { x: 24, y: 22 },
              },
              column(
                { name: "s8-col1", width: fill, height: fill, gap: 16, justify: "between" },
                [
                  column(
                    { name: "s8-col1-top", width: fill, height: hug, gap: 16 },
                    [
                      eyebrow("04", "s8a"),
                      txt("IoT operations", { name: "s8-title1", fontSize: 33, bold: true }),
                      body("Jetty events, CTS discharge, device health, edge buffering, and sensor-backed status.", "s8-body1", fill, 25),
                    ],
                  ),
                  column(
                    { name: "s8-col1-bottom", width: fill, height: hug, gap: 12 },
                    [
                      smallCaps("From", "s8-kicker1a", C.coral),
                      body("Manual status", "s8-note1a", fill, 23, C.coral),
                      smallCaps("To", "s8-kicker1b", C.blue),
                      body("Trusted field events", "s8-note1b", fill, 23, C.blue),
                    ],
                  ),
                ],
              ),
            ),
            panel(
              {
                name: "s8-panel2",
                width: fill,
                height: fill,
                fill: C.soft,
                borderRadius: 24,
                padding: { x: 24, y: 22 },
              },
              column(
                { name: "s8-col2", width: fill, height: fill, gap: 16, justify: "between" },
                [
                  column(
                    { name: "s8-col2-top", width: fill, height: hug, gap: 16 },
                    [
                      eyebrow("05", "s8b"),
                      txt("Optimization", { name: "s8-title2", fontSize: 33, bold: true }),
                      body("Recovery recommendations, resequencing, and conflict repair with human approval.", "s8-body2", fill, 25),
                    ],
                  ),
                  column(
                    { name: "s8-col2-bottom", width: fill, height: hug, gap: 12 },
                    [
                      smallCaps("From", "s8-kicker2a", C.teal),
                      body("Scenario outputs", "s8-note2a", fill, 23, C.teal),
                      smallCaps("To", "s8-kicker2b", C.blue),
                      body("Recommended action", "s8-note2b", fill, 23, C.blue),
                    ],
                  ),
                ],
              ),
            ),
            panel(
              {
                name: "s8-panel3",
                width: fill,
                height: fill,
                fill: C.sand,
                borderRadius: 24,
                padding: { x: 24, y: 22 },
              },
              column(
                { name: "s8-col3", width: fill, height: fill, gap: 16, justify: "between" },
                [
                  column(
                    { name: "s8-col3-top", width: fill, height: hug, gap: 16 },
                    [
                      eyebrow("06", "s8c"),
                      txt("Control tower", { name: "s8-title3", fontSize: 33, bold: true }),
                      body("Role-based visibility for ABL, Berau, management, and eventually customers.", "s8-body3", fill, 25),
                    ],
                  ),
                  column(
                    { name: "s8-col3-bottom", width: fill, height: hug, gap: 12 },
                    [
                      smallCaps("From", "s8-kicker3a", C.amber),
                      body("Shared tool", "s8-note3a", fill, 23, C.amber),
                      smallCaps("To", "s8-kicker3b", C.blue),
                      body("Shared operating system", "s8-note3b", fill, 23, C.blue),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
        panel(
          {
            name: "s8-bottom-panel",
            width: fill,
            height: hug,
            fill: C.soft,
            borderRadius: 22,
            padding: { x: 24, y: 18 },
          },
          body(
            "Manual inputs → live evidence → trusted events → recommended actions.",
            "s8-bottom-note",
            fill,
            26,
            C.blue,
          ),
        ),
      ],
      8,
      "Source: project IoT and roadmap docs.",
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

// Slide 9 — open questions
{
  const s = presentation.slides.add();
  s.compose(
    slideRoot(
      [
        eyebrow("Open questions", "s9-eyebrow"),
        title("The minute nuances are where the tool earns trust.", "s9-title"),
        body(
          "We can build a strong first version from generic operating knowledge. The best version will come from the tacit rules only operators know.",
          "s9-body",
          wrap(1320),
        ),
        thinAccent("s9-rule"),
        grid(
          {
            name: "s9-grid",
            width: fill,
            height: fixed(560),
            columns: [fr(1), fr(1)],
            rows: [fr(1), fr(1), fr(1)],
            columnGap: 28,
            rowGap: 18,
          },
          [
            panel(
              { name: "s9-panel1", width: fill, height: fill, fill: C.soft, borderRadius: 22, padding: { x: 22, y: 20 } },
              column({ name: "s9-panel1-col", width: fill, height: fill, gap: 12, justify: "between" }, [
                smallCaps("Constraints", "s9-k1"),
                body("Which constraints are truly hard\n—and which are negotiable in practice?", "s9-q1", fill, 28, C.ink),
              ]),
            ),
            panel(
              { name: "s9-panel2", width: fill, height: fill, fill: C.white, borderRadius: 22, padding: { x: 22, y: 20 } },
              column({ name: "s9-panel2-col", width: fill, height: fill, gap: 12, justify: "between" }, [
                smallCaps("Overrides", "s9-k2", C.teal),
                body("What operator overrides recur often enough\nto become product logic?", "s9-q2", fill, 28, C.ink),
              ]),
            ),
            panel(
              { name: "s9-panel3", width: fill, height: fill, fill: C.white, borderRadius: 22, padding: { x: 22, y: 20 } },
              column({ name: "s9-panel3-col", width: fill, height: fill, gap: 12, justify: "between" }, [
                smallCaps("Evidence", "s9-k3", C.teal),
                body("How fresh must AIS / GPS evidence be\nbefore dispatch trusts it?", "s9-q3", fill, 28, C.ink),
              ]),
            ),
            panel(
              { name: "s9-panel4", width: fill, height: fill, fill: C.sand, borderRadius: 22, padding: { x: 22, y: 20 } },
              column({ name: "s9-panel4-col", width: fill, height: fill, gap: 12, justify: "between" }, [
                smallCaps("Signals", "s9-k4", C.amber),
                body("Which environmental or safety signals\nchange the plan, not just the ETA?", "s9-q4", fill, 28, C.ink),
              ]),
            ),
            panel(
              { name: "s9-panel5", width: fill, height: fill, fill: C.sand, borderRadius: 22, padding: { x: 22, y: 20 } },
              column({ name: "s9-panel5-col", width: fill, height: fill, gap: 12, justify: "between" }, [
                smallCaps("Governance", "s9-k5", C.amber),
                body("Where must human approval remain explicit,\neven if the system recommends a move?", "s9-q5", fill, 28, C.ink),
              ]),
            ),
            panel(
              { name: "s9-panel6", width: fill, height: fill, fill: C.soft, borderRadius: 22, padding: { x: 22, y: 20 } },
              column({ name: "s9-panel6-col", width: fill, height: fill, gap: 12, justify: "between" }, [
                smallCaps("Trust", "s9-k6"),
                body("What would make this feel indispensable\non a difficult day—not just elegant on a normal one?", "s9-q6", fill, 28, C.blue),
              ]),
            ),
          ],
        ),
      ],
      9,
      "Source: project assumptions and current build scope.",
    ),
    { frame: { left: 0, top: 0, width: W, height: H }, baseUnit: 8 },
  );
}

const pptxPath = path.join(OUT, "coalflow_tower_solution_overview.pptx");
const pptxBlob = await PresentationFile.exportPptx(presentation);
await pptxBlob.save(pptxPath);

for (let i = 0; i < presentation.slides.count; i++) {
  const slide = presentation.slides.getItem(i);
  const png = await slide.export({ format: "png" });
  await saveBlob(png, path.join(RENDERS, `slide-${String(i + 1).padStart(2, "0")}.png`));
  const layout = await slide.export({ format: "layout" });
  await saveBlob(layout, path.join(RENDERS, `slide-${String(i + 1).padStart(2, "0")}.layout.json`));
}

const savedBlob = await FileBlob.load(pptxPath);
const reimported = await PresentationFile.importPptx(savedBlob);
for (let i = 0; i < reimported.slides.count; i++) {
  const slide = reimported.slides.getItem(i);
  const png = await slide.export({ format: "png" });
  await saveBlob(png, path.join(PPTX_RENDERS, `slide-${String(i + 1).padStart(2, "0")}.png`));
  const layout = await slide.export({ format: "layout" });
  await saveBlob(layout, path.join(PPTX_RENDERS, `slide-${String(i + 1).padStart(2, "0")}.layout.json`));
}

console.log(JSON.stringify({
  pptxPath,
  sourceRenderDir: RENDERS,
  pptxRenderDir: PPTX_RENDERS,
  slideCount: presentation.slides.count,
}, null, 2));

process.exit(0);
