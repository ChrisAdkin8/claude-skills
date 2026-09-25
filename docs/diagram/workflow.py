#!/usr/bin/env python3
"""Draw the README's workflow diagram: docs/workflow*.png.

Writes four PNGs, a wide and a narrow layout, each in light and dark:
  docs/workflow.png, docs/workflow-dark.png            wide, for viewing full size
  docs/workflow-narrow.png, docs/workflow-narrow-dark.png  narrow, stays readable at README width
and a fifth, docs/social-preview.png: the repo's 1280x640 social media preview, uploaded by hand in
the repo's Settings > General > Social preview.

    cd docs/diagram && npm install        # once: installs the resvg renderer
    python3 docs/diagram/workflow.py      # add --svg to keep the SVGs in docs/diagram/build/

The text is laid out by estimated character widths, so after changing any wording, look at the
PNGs for lines that wrap badly or run out of their boxes.
"""

import math
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent
SANS = "Helvetica Neue, Helvetica, Arial, sans-serif"
MONO = "Menlo, Monaco, monospace"

# ------------------------------------------------------------------ content
# (number, title, colour key, command or None for a new session, what happens, output)
STAGES = [
    (1, "Capture", "notes", "/idea", "Save the idea as a note", "~/notes/ideas/"),
    (
        2,
        "Research",
        "notes",
        "/research",
        "An agent researches it, citing every claim",
        "~/notes/research/",
    ),
    (3, "Plan", "repo", "/spec", "A spec in the repo, citing the code", "docs/specs/"),
    (
        4,
        "Spike",
        "repo",
        "/spec spike",
        "Sandboxed tests settle what reading can't",
        "docs/specs/spikes/",
    ),
    (
        5,
        "Build",
        "session",
        None,
        "Implement the spec, W1 first; tests, then a PR",
        "code + pull request",
    ),
    (
        6,
        "Close out",
        "repo",
        "/spec done",
        "Log where the build left the plan",
        "docs/specs/records/",
    ),
]
CHECKS = {
    2: [("research-verifier", "checks every source")],
    3: [
        ("check-spec.py", "citations, criteria"),
        ("spec-verifier", "every claim"),
        ("cold-reviewer", "fresh-eyes read"),
    ],
}
LOOP_BACK = "Build overturned the research? Update the note"
QUICK = [("/spec quick", True), (" skips review and spikes", False)]
DELTA_HEAD = "Spec edited after its review?"
DELTA_BODY = [
    ("/cold-review <spec>", True),
    (" re-checks the changes before Build starts", False),
]
REVIEW_STEPS = [
    ("1 Frame", "works out the doc's job"),
    ("2 Review", "a fresh agent reads it"),
    ("3 Relay", "findings, worst first"),
    ("4 You decide", "fix only what you pick"),
    ("5 Delta review", "one re-check of the fixes"),
]
GUARDS = [
    ("Own session", "a headless claude -p run"),
    ("OS sandbox", "no credentials; allowlisted network"),
    ("Guard hook", "checks shell, file and fetch calls"),
    ("Cost caps", "$5–10 per agent, $2 per spike"),
]
LEGEND = [
    ("~/notes", "notes"),
    ("Your code repo", "repo"),
    ("New Claude session", "session"),
    ("Checking agent or script", "check"),
]

# Each colour is (header fill, accent for text and strokes, tint for box fills).
THEMES = {
    "light": dict(
        bg="#FFFFFF",
        card="#FFFFFF",
        ink="#111827",
        muted="#4B5563",
        line="#D1D5DB",
        panel="#F3F4F6", pill="#111827",
        loop="#6B7280",
        loop_ink="#374151",
        shadow=True,
        notes=("#B45309", "#B45309", "#FEF3C7"),
        repo=("#1D4ED8", "#1D4ED8", "#DBEAFE"),
        session=("#047857", "#047857", "#D1FAE5"),
        check=("#6D28D9", "#6D28D9", "#EDE9FE"),
        review=("#BE123C", "#BE123C", "#FFE4E6"),
    ),
    "dark": dict(
        bg="#0D1117",
        card="#161B22",
        ink="#E6EDF3",
        muted="#9DA7B3",
        line="#30363D",
        panel="#11161D", pill="#30363D",
        loop="#8B949E",
        loop_ink="#C9D1D9",
        shadow=False,
        notes=("#B45309", "#F59E0B", "#2B1E0C"),
        repo=("#1D4ED8", "#60A5FA", "#0F1E3D"),
        session=("#047857", "#34D399", "#062A22"),
        check=("#6D28D9", "#A78BFA", "#1F1640"),
        review=("#BE123C", "#FB7185", "#2D0F18"),
    ),
}
PILL_INK = "#FFFFFF"


def wrap(s, width, size, mono=False):
    maxc = max(6, int(width / (size * (0.61 if mono else 0.48))))
    ls, cur = [], ""
    for w in s.split():
        t = f"{cur} {w}".strip()
        if len(t) > maxc and cur:
            ls.append(cur)
            cur = w
        else:
            cur = t
    return ls + [cur] if cur else ls


def width_of(s, size, mono=False):
    return len(s) * size * (0.61 if mono else 0.5)


class Canvas:
    def __init__(self, theme):
        self.t = theme
        self.out = []

    def col(self, key, part):
        return self.t[key][{"head": 0, "accent": 1, "tint": 2}[part]]

    def text(
        self,
        x,
        y,
        s,
        size=19.0,
        fill=None,
        weight="normal",
        mono=False,
        anchor="start",
        rotate=None,
    ):
        tr = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate else ""
        self.out.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{MONO if mono else SANS}" '
            f'font-size="{size}" fill="{fill or self.t["ink"]}" font-weight="{weight}" '
            f'text-anchor="{anchor}"{tr}>{escape(s)}</text>'
        )

    def mixed(
        self,
        x,
        y,
        parts,
        size=18.0,
        fill=None,
        weight="normal",
        anchor="start",
        rotate=None,
    ):
        """One line of text whose (text, is_mono) parts switch to a bold monospace font."""
        tr = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate else ""
        spans = "".join(
            f'<tspan font-family="{MONO}" font-weight="bold">{escape(s)}</tspan>'
            if mono
            else f"<tspan>{escape(s)}</tspan>"
            for s, mono in parts
        )
        self.out.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{SANS}" font-size="{size}" '
            f'fill="{fill or self.t["ink"]}" font-weight="{weight}" text-anchor="{anchor}"{tr}>'
            f"{spans}</text>"
        )

    def lines(self, x, y, ls, size=19.0, lh=None, **kw):
        lh = lh or size * 1.3
        for i, s in enumerate(ls):
            self.text(x, y + i * lh, s, size=size, **kw)
        return y + len(ls) * lh

    def rect(
        self, x, y, w, h, fill, stroke="none", r=10, sw=1.5, dash=None, shadow=False
    ):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        f = ' filter="url(#sh)"' if shadow and self.t["shadow"] else ""
        self.out.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}{f}/>'
        )

    def arrow(self, pts, color, dash=None, width=2.5, head=True):
        """A polyline through pts, with its head drawn at the last point along the last segment."""
        pts = [tuple(p) for p in pts]
        tip = None
        if head:
            (x1, y1), (x2, y2) = pts[-2], pts[-1]
            n = math.hypot(x2 - x1, y2 - y1)
            dx, dy = (x2 - x1) / n, (y2 - y1) / n
            ln, hw = 4.4 * width, 2.4 * width
            bx, by = x2 - dx * ln, y2 - dy * ln
            tip = (f'<path d="M{x2:.1f},{y2:.1f} L{bx - dy * hw:.1f},{by + dx * hw:.1f} '
                   f'L{bx + dy * hw:.1f},{by - dx * hw:.1f} Z" fill="{color}"/>')
            pts[-1] = (x2 - dx * (ln - 1), y2 - dy * (ln - 1))
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
        ds = f' stroke-dasharray="{dash}"' if dash else ""
        self.out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{ds}/>')
        if tip:
            self.out.append(tip)

    def svg(self, w, h):
        head = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
            f'viewBox="0 0 {w:.0f} {h:.0f}">',
            '<defs><filter id="sh" x="-5%" y="-5%" width="110%" height="115%"><feDropShadow '
            'dx="0" dy="2" stdDeviation="3" flood-color="#000" flood-opacity="0.08"/></filter>'
            "</defs>",
            f'<rect x="0" y="0" width="{w:.0f}" height="{h:.0f}" fill="{self.t["bg"]}"/>',
        ]
        return "\n".join(head + self.out + ["</svg>"])

    # shared pieces
    def pill(self, x, y, w, h, stage, key, size=19.0):
        if stage[3]:
            self.rect(x, y, w, h, "#111827" if key == "block" else self.t["pill"], r=8)
            self.text(
                x + 14,
                y + h / 2 + size * 0.35,
                stage[3],
                size=size,
                fill=PILL_INK,
                mono=True,
                weight="bold",
            )
        else:
            self.rect(
                x,
                y,
                w,
                h,
                "none",
                stroke="#FFFFFF" if key == "block" else self.col("session", "accent"),
                r=8,
                sw=2,
                dash="6 5",
            )
            self.text(
                x + w / 2,
                y + h / 2 + size * 0.33,
                "New session",
                size=size - 1,
                fill="#FFFFFF" if key == "block" else self.col("session", "accent"),
                weight="bold",
                anchor="middle",
            )

    def output(self, x, y, w, h, key, path, size=16.0):
        self.rect(
            x, y, w, h, self.col(key, "tint"), stroke=self.col(key, "accent"), r=8, sw=1
        )
        self.text(
            x + 12,
            y + 22,
            "OUTPUT",
            size=13,
            fill=self.col(key, "accent"),
            weight="bold",
        )
        self.text(x + 12, y + 47, path, size=size, mono=True)

    def check_chip(self, x, y, w, h, name, what, size=18.0):
        self.rect(
            x,
            y,
            w,
            h,
            self.col("check", "tint"),
            stroke=self.col("check", "accent"),
            r=10,
        )
        self.text(
            x + 14,
            y + 29,
            name,
            size=size,
            fill=self.col("check", "accent"),
            weight="bold",
            mono=True,
        )
        self.text(x + 14, y + 56, what, size=size)

    def number(self, cx, cy, n, key):
        self.out.append(f'<circle cx="{cx}" cy="{cy}" r="15" fill="#FFFFFF"/>')
        self.text(
            cx,
            cy + 7,
            str(n),
            size=18,
            fill=self.col(key, "head"),
            weight="bold",
            anchor="middle",
        )


# ------------------------------------------------------------------ wide layout
def wide(theme):
    c = Canvas(theme)
    t = theme
    W, X0, GAP, PAD = 1800, 40, 30, 18
    CW = (W - 2 * X0 - 5 * GAP) / 6
    IW = CW - 2 * PAD
    FEED_Y, TOP = 112, 158
    xs = [X0 + i * (CW + GAP) for i in range(6)]
    cxs = [x + CW / 2 for x in xs]
    bodies = [wrap(s[4], IW, 19) for s in STAGES]
    BODY_Y = TOP + 52 + 20 + 42 + 36
    CARD_H = BODY_Y + max(map(len, bodies)) * 25 - TOP + 12 + 64 + 18
    CARD_B = TOP + CARD_H
    QY = CARD_B + 26
    CHIP_H, CHIP_GAP = 76, 14
    CHK_Y = CARD_B + 60
    CHK_B = CHK_Y + 3 * CHIP_H + 2 * CHIP_GAP
    LANE_Y, LANE_H = CHK_B + 74, 140
    GUARD_Y, GUARD_H = LANE_Y + LANE_H + 26, 118
    H = GUARD_Y + GUARD_H + 40

    lx = X0
    for label, key in LEGEND:
        c.rect(lx, 36, 24, 24, c.col(key, "tint"), stroke=c.col(key, "accent"), r=5)
        c.text(lx + 34, 55, label, size=18)
        lx += 34 + width_of(label, 18) + 40

    a, b = cxs[5], cxs[1]
    c.arrow(
        [(a, TOP - 2), (a, FEED_Y), (b, FEED_Y), (b, TOP - 2)],
        t["loop"],
        dash="9 7",
        width=2.4,
    )
    m = (a + b) / 2
    c.rect(m - 225, FEED_Y - 17, 450, 34, t["bg"], r=6)
    c.text(
        m,
        FEED_Y + 7,
        LOOP_BACK,
        size=18,
        fill=t["loop_ink"],
        weight="bold",
        anchor="middle",
    )

    for i, st in enumerate(STAGES):
        x, key = xs[i], st[2]
        c.rect(x, TOP, CW, CARD_H, t["card"], stroke=t["line"], r=14, shadow=True)
        head = c.col(key, "head")
        c.out.append(
            f'<path d="M{x},{TOP + 52} L{x},{TOP + 14} Q{x},{TOP} {x + 14},{TOP} '
            f"L{x + CW - 14},{TOP} Q{x + CW},{TOP} {x + CW},{TOP + 14} "
            f'L{x + CW},{TOP + 52} Z" fill="{head}"/>'
        )
        c.number(x + 30, TOP + 26, st[0], key)
        c.text(x + 56, TOP + 35, st[1], size=24, fill="#FFFFFF", weight="bold")
        c.pill(x + PAD, TOP + 72, IW, 42, st, "card")
        c.lines(x + PAD, BODY_Y, bodies[i], size=19, lh=25)
        c.output(x + PAD, CARD_B - 64 - 18, IW, 64, key, st[5])
    for i in range(5):
        ax, ay = xs[i] + CW + 3, TOP + 26
        c.arrow([(ax, ay), (ax + GAP - 5, ay)], t["muted"], width=3)

    a, b = xs[2] + CW - 34, xs[4] + 34
    c.arrow(
        [(a, CARD_B + 2), (a, QY), (b, QY), (b, CARD_B + 2)],
        t["loop"],
        dash="9 7",
        width=2.4,
    )
    c.mixed(xs[3] + 4, QY + 30, QUICK, size=18, fill=t["loop_ink"], weight="bold")

    rv = "review"
    nx, nw, ny, nh = xs[3], 2 * CW + GAP, CHK_Y + 74, 112
    c.rect(nx, ny, nw, nh, c.col(rv, "tint"), stroke=c.col(rv, "accent"), r=12)
    c.text(
        nx + 20, ny + 38, DELTA_HEAD, size=20, fill=c.col(rv, "accent"), weight="bold"
    )
    c.mixed(
        nx + 20, ny + 72, DELTA_BODY[:1] + [(" re-checks the changes", False)], size=18
    )
    c.text(nx + 20, ny + 97, "before Build starts", size=18)
    gx = xs[4] + CW - 60
    c.arrow(
        [(gx, ny - 2), (gx, CARD_B + 2)], c.col(rv, "accent"), dash="7 6", width=2.4
    )

    for n, chips in CHECKS.items():
        i = n - 1
        last = CHK_Y + (len(chips) - 1) * (CHIP_H + CHIP_GAP)
        c.arrow(
            [(cxs[i], CARD_B), (cxs[i], last)],
            c.col("check", "accent"),
            width=2,
            head=False,
        )
        for k, (name, what) in enumerate(chips):
            c.check_chip(xs[i], CHK_Y + k * (CHIP_H + CHIP_GAP), CW, CHIP_H, name, what)
    c.text(
        xs[0],
        CHK_Y + 30,
        "Checked by",
        size=20,
        fill=c.col("check", "accent"),
        weight="bold",
    )
    c.text(xs[0], CHK_Y + 56, "agents that never", size=17, fill=t["muted"])
    c.text(xs[0], CHK_Y + 78, "saw the conversation", size=17, fill=t["muted"])

    cry = CHK_Y + 2 * (CHIP_H + CHIP_GAP) + CHIP_H
    c.arrow(
        [(cxs[2], cry + 2), (cxs[2], LANE_Y - 2)],
        c.col(rv, "accent"),
        dash="7 6",
        width=2.4,
    )
    c.text(
        cxs[2] + 14,
        (cry + LANE_Y) / 2 + 7,
        "the same review",
        size=17,
        fill=c.col(rv, "accent"),
        weight="bold",
    )

    c.rect(
        X0,
        LANE_Y,
        W - 2 * X0,
        LANE_H,
        c.col(rv, "tint"),
        stroke=c.col(rv, "accent"),
        r=14,
    )
    c.text(
        X0 + 24,
        LANE_Y + 50,
        "/cold-review",
        size=26,
        fill=c.col(rv, "accent"),
        weight="bold",
        mono=True,
    )
    c.lines(
        X0 + 24, LANE_Y + 90, ["Any markdown document,", "at any stage"], size=19, lh=25
    )
    sx = X0 + 300
    sw = (W - X0 - 24 - sx - 4 * 30) / 5
    for k, (head, body) in enumerate(REVIEW_STEPS):
        bx = sx + k * (sw + 30)
        c.rect(
            bx,
            LANE_Y + 24,
            sw,
            LANE_H - 48,
            t["card"],
            stroke=c.col(rv, "accent"),
            r=10,
            sw=1,
        )
        c.text(
            bx + 16, LANE_Y + 62, head, size=19, fill=c.col(rv, "accent"), weight="bold"
        )
        c.lines(bx + 16, LANE_Y + 94, wrap(body, sw - 32, 18), size=18, lh=24)
        if k < 4:
            c.arrow(
                [
                    (bx + sw + 3, LANE_Y + LANE_H / 2),
                    (bx + sw + 27, LANE_Y + LANE_H / 2),
                ],
                c.col(rv, "accent"),
                width=2.6,
            )

    c.rect(X0, GUARD_Y, W - 2 * X0, GUARD_H, t["panel"], stroke=t["line"], r=14)
    c.text(X0 + 24, GUARD_Y + 48, "Every agent", size=22, weight="bold")
    c.text(X0 + 24, GUARD_Y + 76, "is contained", size=22, weight="bold")
    gw4 = (W - X0 - 24 - sx - 3 * 20) / 4
    for k, (head, body) in enumerate(GUARDS):
        bx = sx + k * (gw4 + 20)
        c.rect(
            bx, GUARD_Y + 20, gw4, GUARD_H - 40, t["card"], stroke=t["line"], r=10, sw=1
        )
        c.text(bx + 16, GUARD_Y + 51, head, size=19, weight="bold")
        c.text(bx + 16, GUARD_Y + 79, body, size=18)
    return c.svg(W, H)


# ------------------------------------------------------------------ narrow layout
def narrow(theme):
    """One stage per row, for README width: at GitHub's page width it shows near full size."""
    c = Canvas(theme)
    t = theme
    rv = "review"
    W, X0 = 1000, 40
    RX, RW = 110, 780  # rows; the gutters either side carry the two dashed loops
    LOOP_X, QUICK_X = 78, 922
    BW, OW = 232, 228  # coloured block on the left, output box on the right
    GAP_Y = 36
    DX = RX + BW + 20
    DW = RW - BW - 20 - OW - 32

    lx = X0
    for label, key in LEGEND:
        c.rect(lx, 34, 22, 22, c.col(key, "tint"), stroke=c.col(key, "accent"), r=5)
        c.text(lx + 30, 51, label, size=17)
        lx += 30 + width_of(label, 17) + 30

    y = 94
    rows = []
    for i, st in enumerate(STAGES):
        n, _, key = st[0], st[1], st[2]
        body = wrap(st[4], DW, 19)
        base = max(100, 30 + 25 * len(body))
        chips = CHECKS.get(n, [])
        h = base + (74 if chips else 0)
        rows.append((y, h))
        c.rect(RX, y, RW, h, t["card"], stroke=t["line"], r=14, shadow=True)
        head = c.col(key, "head")
        c.out.append(
            f'<path d="M{RX + 14},{y} L{RX + BW},{y} L{RX + BW},{y + h} L{RX + 14},{y + h} '
            f'Q{RX},{y + h} {RX},{y + h - 14} L{RX},{y + 14} Q{RX},{y} {RX + 14},{y} Z" '
            f'fill="{head}"/>'
        )
        c.number(RX + 30, y + 30, n, key)
        c.text(RX + 56, y + 38, st[1], size=22, fill="#FFFFFF", weight="bold")
        c.pill(RX + 16, y + 54, BW - 32, 34, st, "block", size=17)
        c.lines(DX, y + 40, body, size=19, lh=25)
        c.output(RX + RW - OW - 16, y + 18, OW, 64, key, st[5], size=15)
        if chips:
            cy = y + base - 6
            cw = (RW - BW - 36 - 12 * (len(chips) - 1)) / 3
            if len(chips) == 1:
                cw = 2 * cw + 12
            for k, (name, what) in enumerate(chips):
                c.check_chip(DX + k * (cw + 12), cy, cw, 66, name, what, size=16)
        y += h
        if n == 4:  # the delta-review gate sits between Spike and Build
            c.arrow(
                [(RX + BW / 2, y + 2), (RX + BW / 2, y + GAP_Y - 2)],
                t["muted"],
                width=3,
            )
            y += GAP_Y
            gh = 84
            c.rect(RX, y, RW, gh, c.col(rv, "tint"), stroke=c.col(rv, "accent"), r=12)
            c.text(
                RX + 20,
                y + 34,
                DELTA_HEAD,
                size=19,
                fill=c.col(rv, "accent"),
                weight="bold",
            )
            c.mixed(RX + 20, y + 64, DELTA_BODY, size=17)
            y += gh
        if n < 6:
            c.arrow(
                [(RX + BW / 2, y + 2), (RX + BW / 2, y + GAP_Y - 2)],
                t["muted"],
                width=3,
            )
            y += GAP_Y

    # loop back: close out -> research, in the left gutter
    (y2, _), (y6, _) = rows[1], rows[5]
    c.arrow(
        [(RX - 2, y6 + 40), (LOOP_X, y6 + 40), (LOOP_X, y2 + 40), (RX - 2, y2 + 40)],
        t["loop"],
        dash="9 7",
        width=2.4,
    )
    c.text(
        LOOP_X - 16,
        (y2 + y6) / 2 + 40,
        LOOP_BACK,
        size=17,
        fill=t["loop_ink"],
        weight="bold",
        anchor="middle",
        rotate=-90,
    )
    # shortcut: plan -> build, in the right gutter
    (y3, _), (y5, _) = rows[2], rows[4]
    c.arrow(
        [
            (RX + RW + 2, y3 + 40),
            (QUICK_X, y3 + 40),
            (QUICK_X, y5 + 40),
            (RX + RW + 2, y5 + 40),
        ],
        t["loop"],
        dash="9 7",
        width=2.4,
    )
    c.mixed(
        QUICK_X + 18,
        (y3 + y5) / 2 + 40,
        QUICK,
        size=17,
        fill=t["loop_ink"],
        weight="bold",
        anchor="middle",
        rotate=90,
    )

    # /cold-review
    y += 20
    ly, lh = y, 196
    c.rect(X0, ly, W - 2 * X0, lh, c.col(rv, "tint"), stroke=c.col(rv, "accent"), r=14)
    c.text(
        X0 + 22,
        ly + 40,
        "/cold-review",
        size=24,
        fill=c.col(rv, "accent"),
        weight="bold",
        mono=True,
    )
    c.text(
        X0 + 22 + width_of("/cold-review", 24, True) + 14,
        ly + 40,
        "any markdown document, at any stage",
        size=19,
    )
    c.text(
        X0 + 22,
        ly + 68,
        "/spec runs the same review as its cold-reviewer",
        size=17,
        fill=c.col(rv, "accent"),
    )
    gap = 22
    sw = (W - 2 * X0 - 44 - 4 * gap) / 5
    for k, (head, body) in enumerate(REVIEW_STEPS):
        bx = X0 + 22 + k * (sw + gap)
        by = ly + 88
        c.rect(bx, by, sw, 88, t["card"], stroke=c.col(rv, "accent"), r=10, sw=1)
        c.text(bx + 12, by + 28, head, size=17, fill=c.col(rv, "accent"), weight="bold")
        c.lines(bx + 12, by + 52, wrap(body, sw - 24, 16), size=16, lh=20)
        if k < 4:
            c.arrow(
                [(bx + sw + 2, by + 44), (bx + sw + gap - 2, by + 44)],
                c.col(rv, "accent"),
                width=2.2,
            )
    y = ly + lh + 20

    # containment
    gh = 222
    c.rect(X0, y, W - 2 * X0, gh, t["panel"], stroke=t["line"], r=14)
    c.text(X0 + 22, y + 40, "Every agent is contained", size=21, weight="bold")
    iw = (W - 2 * X0 - 44 - 16) / 2
    for k, (head, body) in enumerate(GUARDS):
        bx = X0 + 22 + (k % 2) * (iw + 16)
        by = y + 60 + (k // 2) * 80
        c.rect(bx, by, iw, 68, t["card"], stroke=t["line"], r=10, sw=1)
        c.text(bx + 14, by + 28, head, size=18, weight="bold")
        c.text(bx + 14, by + 54, body, size=17)
    return c.svg(W, y + gh + 36)


# ------------------------------------------------------------------ social preview
TITLE = "claude-skills"
TAGLINE = "Claude Code skills that take an idea to a checked implementation plan"
CHECKED = "Research and plans checked by agents that never saw the conversation"
REPO = "github.com/ChrisAdkin8/claude-skills"


def social(theme):
    """GitHub's 1280x640 card: a few large words that survive being shown ~500px wide. Sites that
    crop to 1.91:1 trim ~30px off each side, so nothing sits within 56px of an edge."""
    c = Canvas(theme)
    t = theme
    W, H, X0 = 1280, 640, 64
    c.text(X0, 150, TITLE, size=92, weight="bold")
    c.text(X0, 212, TAGLINE, size=31, fill=t["muted"])

    GAP = 18
    BW = (W - 2 * X0 - 5 * GAP) / 6
    TOP, BH = 268, 158
    for i, st in enumerate(STAGES):
        x, key = X0 + i * (BW + GAP), st[2]
        c.rect(x, TOP, BW, BH, c.col(key, "head"), r=16)
        c.number(x + 28, TOP + 36, st[0], key)
        c.text(x + 50, TOP + 45, st[1], size=24, fill="#FFFFFF", weight="bold")
        c.pill(x + 14, TOP + 84, BW - 28, 48, st, "block", size=19)
        if i < 5:
            ay = TOP + BH / 2
            c.arrow([(x + BW + 3, ay), (x + BW + GAP - 3, ay)], t["muted"], width=3)

    c.text(X0, 500, CHECKED, size=29, fill=c.col("check", "accent"), weight="bold")
    c.text(X0, 568, REPO, size=24, fill=t["muted"])
    return c.svg(W, H)


# ------------------------------------------------------------------ render
def main():
    if not (HERE / "node_modules" / "@resvg" / "resvg-js").exists():
        sys.exit(
            "run `npm install` in docs/diagram first: it installs the resvg renderer"
        )
    keep = "--svg" in sys.argv[1:]
    build = HERE / "build" if keep else Path(tempfile.mkdtemp())
    build.mkdir(exist_ok=True)
    jobs = [
        ("workflow", wide, "light", 2.5),
        ("workflow-dark", wide, "dark", 2.5),
        ("workflow-narrow", narrow, "light", 2),
        ("workflow-narrow-dark", narrow, "dark", 2),
        ("social-preview", social, "light", 1),
    ]
    for name, layout, theme, zoom in jobs:
        svg = build / f"{name}.svg"
        svg.write_text(layout(THEMES[theme]))
        png = DOCS / f"{name}.png"
        subprocess.run(
            [
                "node",
                str(HERE / "render.mjs"),
                str(svg),
                str(png),
                str(zoom),
                THEMES[theme]["bg"],
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
