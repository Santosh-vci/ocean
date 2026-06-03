from pathlib import Path
from html import escape

from PIL import Image, ImageDraw, ImageFont


OUT_DIR = Path(__file__).resolve().parent
PNG_PATH = OUT_DIR / "ABL_Program_Delivery_Timeline_Gantt_v2.png"
SVG_PATH = OUT_DIR / "ABL_Program_Delivery_Timeline_Gantt_v2.svg"

W, H = 2600, 1500

COLORS = {
    "navy": "#0B2948",
    "blue": "#2F7DBD",
    "blue_bar": "#1E70C7",
    "blue_light": "#45A4E3",
    "green": "#2E7D32",
    "green_dark": "#21652A",
    "orange": "#E96500",
    "orange_dark": "#C95200",
    "amber": "#A9781A",
    "text": "#10233F",
    "muted": "#4A5F78",
    "grid": "#D9E2EC",
    "grid_major": "#B8C7D6",
    "row": "#F6F9FC",
    "white": "#FFFFFF",
    "blue_zone": "#EAF4FD",
    "green_zone": "#F0FAF0",
    "orange_zone": "#FFF3E4",
    "label_bg": "#F8FAFC",
}

MARGIN_X = 84
RIGHT = 84
HEADER_H = 130
SUBHEADER_H = 48
AXIS_Y = HEADER_H + SUBHEADER_H + 22
AXIS_H = 38
PHASE_Y = AXIS_Y + AXIS_H
PHASE_H = 48
ROW_H = 55
LABEL_W = 520
CHART_X = MARGIN_X
TIMELINE_X = CHART_X + LABEL_W
TIMELINE_W = W - TIMELINE_X - RIGHT
WEEK_W = TIMELINE_W / 36
GRID_TOP = PHASE_Y

TASKS = [
    ("Blueprinting", 1, 3, "blue"),
    ("Sprint 0 - Foundation", 4, 5, "blue"),
    ("Sprint 1 - Master Data & Governance", 6, 7, "blue"),
    ("Sprint 2 - OGV Demand & Cargo Layer", 8, 9, "blue"),
    ("Sprint 3 - Schedule Entity & Trips", 10, 11, "blue"),
    ("Sprint 4 - Capacity & Feasibility", 12, 14, "blue_light"),
    ("Sprint 5 - Approval & Publish", 15, 16, "blue_light"),
    ("Release 1 Review & Adoption", 17, 18, "green_dark"),
    ("Sprint 6 - Exception & Scenario", 19, 21, "orange"),
    ("Sprint 7 - Live Evidence & Telemetry", 22, 24, "orange"),
    ("Sprint 8 - Confirmed Ops & Events", 25, 27, "orange"),
    ("Sprint 9 - Recovery Recommendations", 28, 30, "orange"),
    ("Sprint 10 - Guided Recovery & Hardening", 31, 33, "orange"),
    ("Final UAT & Pilot Hardening", 34, 36, "amber"),
]

PHASES = [
    ("BLUEPRINTING", 1, 3, "blue"),
    ("RELEASE 1 - GOVERNED SCHEDULING SPINE", 4, 18, "green"),
    ("RELEASE 2 - SCENARIO, EVIDENCE, RECOVERY, PILOT", 19, 36, "orange_dark"),
]

MILESTONES = [
    ("Blueprint\nComplete", 3, "blue", 0),
    ("Release 1\nValidated", 18, "green", 0),
    ("Pilot-ready\nPlatform", 36, "amber", 0),
]

CARDS = [
    (
        "BLUEPRINTING",
        "W1-W3",
        "Operating rules, data assumptions, flow logic, and sprint backlog.",
        "blue",
    ),
    (
        "RELEASE 1",
        "W4-W18",
        "Governed scheduling spine, operating window logic, and pilot-user validation.",
        "green",
    ),
    (
        "RELEASE 2",
        "W19-W33",
        "Scenario handling, live evidence, confirmed operations, and recovery guidance.",
        "orange",
    ),
    (
        "PILOT READY",
        "W34-W36",
        "Full UAT, pilot hardening, platform sign-off. External risk: W40-W44.",
        "amber",
    ),
]


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def font_path(name):
    candidates = [
        Path(r"C:\Windows\Fonts") / name,
        Path(r"C:\Windows\Fonts") / name.lower(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def load_font(size, bold=False):
    file_name = "segoeuib.ttf" if bold else "segoeui.ttf"
    path = font_path(file_name)
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.truetype("arial.ttf", size)


def week_start(week):
    return TIMELINE_X + (week - 1) * WEEK_W


def week_end(week):
    return TIMELINE_X + week * WEEK_W


def week_range(start, end, pad=0):
    x1 = week_start(start) + pad
    x2 = week_end(end) - pad
    return x1, x2


def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_center_text(draw, xy, text, font, fill, line_gap=4):
    x, y, w, h = xy
    lines = text.split("\n")
    sizes = [text_size(draw, line, font) for line in lines]
    total_h = sum(s[1] for s in sizes) + line_gap * (len(lines) - 1)
    cursor = y + (h - total_h) / 2
    for line, (tw, th) in zip(lines, sizes):
        draw.text((x + (w - tw) / 2, cursor), line, font=font, fill=fill)
        cursor += th + line_gap


def wrap_lines(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if text_size(draw, candidate, font)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_wrapped_center(draw, xy, text, font, fill, line_gap=6):
    x, y, w, h = xy
    lines = wrap_lines(draw, text, font, w)
    sizes = [text_size(draw, line, font) for line in lines]
    total_h = sum(s[1] for s in sizes) + line_gap * (len(lines) - 1)
    cursor = y + (h - total_h) / 2
    for line, (tw, th) in zip(lines, sizes):
        draw.text((x + (w - tw) / 2, cursor), line, font=font, fill=fill)
        cursor += th + line_gap


def draw_diamond(draw, cx, cy, r, fill, outline=None):
    points = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    draw.polygon(points, fill=fill, outline=outline or fill)


def render_png():
    img = Image.new("RGB", (W, H), COLORS["white"])
    draw = ImageDraw.Draw(img)

    title_font = load_font(48, bold=True)
    subtitle_font = load_font(20)
    subheader_font = load_font(20, bold=True)
    axis_font = load_font(18, bold=True)
    phase_font = load_font(15, bold=True)
    row_font = load_font(20, bold=True)
    row_small_font = load_font(17, bold=True)
    card_title_font = load_font(24, bold=True)
    card_period_font = load_font(18, bold=True)
    card_body_font = load_font(18)
    milestone_font = load_font(13, bold=True)
    footer_font = load_font(13)

    # Header and subheader are deliberately separated from the axis labels.
    draw.rectangle((0, 0, W, HEADER_H), fill=COLORS["navy"])
    draw.text((MARGIN_X, 38), "Program Delivery Timeline", font=title_font, fill=COLORS["white"])
    right_text = "ABL | Dynamic Operational Synchronization Platform"
    rw, _ = text_size(draw, right_text, subtitle_font)
    draw.text((W - RIGHT - rw, 49), right_text, font=subtitle_font, fill="#D7E6F6")

    draw.rectangle((0, HEADER_H, W, HEADER_H + SUBHEADER_H), fill=COLORS["blue"])
    sub = (
        "Estimated delivery span: 34-36 weeks from kickoff  |  "
        "Blueprinting: W1-W3  |  Release 1 validation: W18  |  "
        "Pilot-ready platform: W36"
    )
    draw.text((MARGIN_X, HEADER_H + 14), sub, font=subheader_font, fill=COLORS["white"])

    # Axis label row.
    for week in range(2, 37, 2):
        x = (week_start(week) + week_end(week)) / 2
        label = f"WK{week}"
        tw, th = text_size(draw, label, axis_font)
        draw.text((x - tw / 2, AXIS_Y + 8), label, font=axis_font, fill=COLORS["navy"])

    grid_h = PHASE_H + len(TASKS) * ROW_H
    grid_bottom = GRID_TOP + grid_h
    rows_top = PHASE_Y + PHASE_H

    # Zone backgrounds.
    draw.rectangle((CHART_X, GRID_TOP, TIMELINE_X, grid_bottom), fill=COLORS["label_bg"])
    zones = [
        (1, 3, "blue_zone"),
        (4, 18, "green_zone"),
        (19, 36, "orange_zone"),
    ]
    for start, end, color in zones:
        x1, x2 = week_range(start, end)
        draw.rectangle((x1, GRID_TOP, x2, grid_bottom), fill=COLORS[color])

    # Row stripes.
    for idx in range(len(TASKS) + 1):
        y = GRID_TOP + idx * ROW_H if idx else GRID_TOP
        if idx == 0:
            continue
        if idx % 2 == 0:
            draw.rectangle((CHART_X, rows_top + (idx - 1) * ROW_H, W - RIGHT, rows_top + idx * ROW_H), fill="#FBFDFF")

    # Grid lines.
    draw.rectangle((CHART_X, GRID_TOP, W - RIGHT, grid_bottom), outline=COLORS["grid_major"], width=1)
    draw.line((TIMELINE_X, GRID_TOP, TIMELINE_X, grid_bottom), fill=COLORS["grid_major"], width=1)
    for week in range(1, 37):
        x = week_start(week)
        line_color = COLORS["grid_major"] if week % 2 == 0 else COLORS["grid"]
        draw.line((x, GRID_TOP, x, grid_bottom), fill=line_color, width=1)
    draw.line((week_start(19), GRID_TOP, week_start(19), grid_bottom), fill=COLORS["amber"], width=3)
    for i in range(len(TASKS) + 1):
        y = rows_top + i * ROW_H
        draw.line((CHART_X, y, W - RIGHT, y), fill="#E7EDF3", width=1)

    # Phase bars.
    draw_center_text(
        draw,
        (CHART_X, PHASE_Y, LABEL_W, PHASE_H),
        "Delivery phase",
        row_font,
        COLORS["text"],
    )
    for label, start, end, color in PHASES:
        x1, x2 = week_range(start, end, pad=3)
        draw.rounded_rectangle((x1, PHASE_Y + 7, x2, PHASE_Y + PHASE_H - 7), radius=4, fill=COLORS[color])
        draw_center_text(draw, (x1, PHASE_Y + 7, x2 - x1, PHASE_H - 14), label, phase_font, COLORS["white"])

    # Task labels and bars.
    for idx, (label, start, end, color) in enumerate(TASKS):
        row_y = rows_top + idx * ROW_H
        draw.text((CHART_X + 14, row_y + 15), label, font=row_font, fill=COLORS["text"])
        x1, x2 = week_range(start, end, pad=5)
        bar_y1 = row_y + 10
        bar_y2 = row_y + ROW_H - 10
        draw.rounded_rectangle((x1, bar_y1, x2, bar_y2), radius=5, fill=COLORS[color])
        bar_label = f"W{start}-W{end}" if start != end else f"W{start}"
        font = row_small_font if (x2 - x1) > 125 else axis_font
        draw_center_text(draw, (x1, bar_y1, x2 - x1, bar_y2 - bar_y1), bar_label, font, COLORS["white"])

    # Milestones.
    milestone_line_y = grid_bottom + 42
    draw.line((TIMELINE_X, milestone_line_y, W - RIGHT, milestone_line_y), fill=COLORS["grid_major"], width=2)
    for label, week, color, _ in MILESTONES:
        x = week_end(week)
        draw.line((x, grid_bottom, x, milestone_line_y - 12), fill=COLORS[color], width=2)
        draw_diamond(draw, x, milestone_line_y, 11, COLORS[color])
        draw_center_text(draw, (x - 92, milestone_line_y + 16, 184, 46), label, milestone_font, COLORS["text"], line_gap=2)

    # Deliverable blocks.
    cards_y = milestone_line_y + 98
    card_gap = 22
    card_w = (W - (2 * MARGIN_X) - (3 * card_gap)) / 4
    card_h = 162
    for idx, (title, period, body, color) in enumerate(CARDS):
        x = MARGIN_X + idx * (card_w + card_gap)
        draw.rounded_rectangle((x, cards_y, x + card_w, cards_y + card_h), radius=6, fill=COLORS[color])
        draw_center_text(draw, (x + 18, cards_y + 16, card_w - 36, 32), title, card_title_font, COLORS["white"])
        draw_center_text(draw, (x + 18, cards_y + 52, card_w - 36, 24), period, card_period_font, "#EAF4FF")
        draw_wrapped_center(draw, (x + 34, cards_y + 78, card_w - 68, 78), body, card_body_font, COLORS["white"], line_gap=5)

    # Footer.
    footer_y = H - 48
    draw.rectangle((0, footer_y, W, H), fill=COLORS["navy"])
    left_footer = "PT Vector Management Consulting  |  ABL Operational Blueprinting - Application Build Extension v4"
    right_footer = "Estimated: 34-36 weeks nominal  |  40-44 weeks with external integration risk"
    draw.text((MARGIN_X, footer_y + 16), left_footer, font=footer_font, fill="#DCE8F5")
    rw, _ = text_size(draw, right_footer, footer_font)
    draw.text((W - RIGHT - rw, footer_y + 16), right_footer, font=footer_font, fill="#DCE8F5")

    img.save(PNG_PATH, quality=95)


def svg_text(x, y, text, size=16, weight=400, color="#000000", anchor="start", extra=""):
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-family="Segoe UI, Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}" {extra}>'
        f"{escape(text)}</text>"
    )


def svg_rect(x, y, w, h, fill, stroke=None, rx=0, sw=1):
    stroke_attr = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{rx}" fill="{fill}"{stroke_attr}/>'


def svg_line(x1, y1, x2, y2, stroke, sw=1):
    return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{stroke}" stroke-width="{sw}"/>'


def approx_wrap(text, max_chars):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def svg_center_text(x, y, w, h, text, size, weight, color, line_gap=4):
    lines = text.split("\n")
    total_h = len(lines) * size + (len(lines) - 1) * line_gap
    first_y = y + (h - total_h) / 2 + size
    parts = []
    for i, line in enumerate(lines):
        parts.append(svg_text(x + w / 2, first_y + i * (size + line_gap), line, size, weight, color, anchor="middle"))
    return "\n".join(parts)


def render_svg():
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        svg_rect(0, 0, W, H, COLORS["white"]),
        svg_rect(0, 0, W, HEADER_H, COLORS["navy"]),
        svg_text(MARGIN_X, 78, "Program Delivery Timeline", 48, 700, COLORS["white"]),
        svg_text(W - RIGHT, 68, "ABL | Dynamic Operational Synchronization Platform", 20, 400, "#D7E6F6", anchor="end"),
        svg_rect(0, HEADER_H, W, SUBHEADER_H, COLORS["blue"]),
        svg_text(
            MARGIN_X,
            HEADER_H + 31,
            "Estimated delivery span: 34-36 weeks from kickoff  |  Blueprinting: W1-W3  |  Release 1 validation: W18  |  Pilot-ready platform: W36",
            20,
            700,
            COLORS["white"],
        ),
    ]

    for week in range(2, 37, 2):
        x = (week_start(week) + week_end(week)) / 2
        parts.append(svg_text(x, AXIS_Y + 27, f"WK{week}", 18, 700, COLORS["navy"], anchor="middle"))

    grid_h = PHASE_H + len(TASKS) * ROW_H
    grid_bottom = GRID_TOP + grid_h
    rows_top = PHASE_Y + PHASE_H

    parts.append(svg_rect(CHART_X, GRID_TOP, LABEL_W, grid_h, COLORS["label_bg"]))
    for start, end, color in [(1, 3, "blue_zone"), (4, 18, "green_zone"), (19, 36, "orange_zone")]:
        x1, x2 = week_range(start, end)
        parts.append(svg_rect(x1, GRID_TOP, x2 - x1, grid_h, COLORS[color]))

    for idx in range(1, len(TASKS) + 1):
        if idx % 2 == 0:
            parts.append(svg_rect(CHART_X, rows_top + (idx - 1) * ROW_H, W - RIGHT - CHART_X, ROW_H, "#FBFDFF"))

    parts.append(svg_rect(CHART_X, GRID_TOP, W - RIGHT - CHART_X, grid_h, "none", COLORS["grid_major"]))
    parts.append(svg_line(TIMELINE_X, GRID_TOP, TIMELINE_X, grid_bottom, COLORS["grid_major"]))
    for week in range(1, 37):
        x = week_start(week)
        color = COLORS["grid_major"] if week % 2 == 0 else COLORS["grid"]
        parts.append(svg_line(x, GRID_TOP, x, grid_bottom, color))
    parts.append(svg_line(week_start(19), GRID_TOP, week_start(19), grid_bottom, COLORS["amber"], 3))
    for i in range(len(TASKS) + 1):
        y = rows_top + i * ROW_H
        parts.append(svg_line(CHART_X, y, W - RIGHT, y, "#E7EDF3"))

    parts.append(svg_center_text(CHART_X, PHASE_Y, LABEL_W, PHASE_H, "Delivery phase", 16, 700, COLORS["text"]))
    for label, start, end, color in PHASES:
        x1, x2 = week_range(start, end, pad=3)
        parts.append(svg_rect(x1, PHASE_Y + 7, x2 - x1, PHASE_H - 14, COLORS[color], rx=4))
        parts.append(svg_center_text(x1, PHASE_Y + 7, x2 - x1, PHASE_H - 14, label, 15, 700, COLORS["white"]))

    for idx, (label, start, end, color) in enumerate(TASKS):
        row_y = rows_top + idx * ROW_H
        parts.append(svg_text(CHART_X + 14, row_y + 36, label, 20, 700, COLORS["text"]))
        x1, x2 = week_range(start, end, pad=5)
        parts.append(svg_rect(x1, row_y + 10, x2 - x1, ROW_H - 20, COLORS[color], rx=5))
        bar_label = f"W{start}-W{end}" if start != end else f"W{start}"
        parts.append(svg_center_text(x1, row_y + 10, x2 - x1, ROW_H - 20, bar_label, 17, 700, COLORS["white"]))

    milestone_line_y = grid_bottom + 42
    parts.append(svg_line(TIMELINE_X, milestone_line_y, W - RIGHT, milestone_line_y, COLORS["grid_major"], 2))
    for label, week, color, _ in MILESTONES:
        x = week_end(week)
        parts.append(svg_line(x, grid_bottom, x, milestone_line_y - 12, COLORS[color], 2))
        points = f"{x:.2f},{milestone_line_y - 11:.2f} {x + 11:.2f},{milestone_line_y:.2f} {x:.2f},{milestone_line_y + 11:.2f} {x - 11:.2f},{milestone_line_y:.2f}"
        parts.append(f'<polygon points="{points}" fill="{COLORS[color]}"/>')
        parts.append(svg_center_text(x - 92, milestone_line_y + 16, 184, 46, label, 13, 700, COLORS["text"], line_gap=2))

    cards_y = milestone_line_y + 98
    card_gap = 22
    card_w = (W - (2 * MARGIN_X) - (3 * card_gap)) / 4
    card_h = 162
    for idx, (title, period, body, color) in enumerate(CARDS):
        x = MARGIN_X + idx * (card_w + card_gap)
        parts.append(svg_rect(x, cards_y, card_w, card_h, COLORS[color], rx=6))
        parts.append(svg_center_text(x + 18, cards_y + 16, card_w - 36, 32, title, 24, 700, COLORS["white"]))
        parts.append(svg_center_text(x + 18, cards_y + 52, card_w - 36, 24, period, 18, 700, "#EAF4FF"))
        lines = approx_wrap(body, 42)
        total_h = len(lines) * 18 + (len(lines) - 1) * 6
        first_y = cards_y + 78 + (78 - total_h) / 2 + 18
        for line_i, line in enumerate(lines):
            parts.append(svg_text(x + card_w / 2, first_y + line_i * 24, line, 18, 400, COLORS["white"], anchor="middle"))

    footer_y = H - 48
    parts.append(svg_rect(0, footer_y, W, 48, COLORS["navy"]))
    parts.append(svg_text(MARGIN_X, footer_y + 30, "PT Vector Management Consulting  |  ABL Operational Blueprinting - Application Build Extension v4", 13, 400, "#DCE8F5"))
    parts.append(svg_text(W - RIGHT, footer_y + 30, "Estimated: 34-36 weeks nominal  |  40-44 weeks with external integration risk", 13, 400, "#DCE8F5", anchor="end"))

    parts.append("</svg>")
    SVG_PATH.write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    render_png()
    render_svg()
    print(PNG_PATH)
    print(SVG_PATH)
