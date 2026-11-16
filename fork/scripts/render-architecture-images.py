"""Draw the README hero and architecture diagrams in a friendly cartoon style.

    uv run --frozen --with fonttools==4.68.0 python -I fork/scripts/render-architecture-images.py

Writes docs/images/architecture/{hero,scan-flow,fork-sync,dev-loop}.svg.

- Cartoon shapes, plain type: cut-out cards with a hard shadow and a lightly
  sketched outline, set in Nunito, a rounded sans-serif that stays easy to read.
- Each image is a sheet of grid paper with its own background, so one file
  reads well on both light and dark GitHub.
- The wobble in the lines comes from a seeded random generator: re-running
  writes byte-identical files, so the fork patches don't churn.
- Nunito (SIL Open Font License 1.1, kept in fork/assets/fonts) is embedded as
  a subset of the characters each image uses, because README images can't load
  web fonts.
- Label widths are measured from the font. If a label doesn't fit its card,
  the script lists every such label and writes nothing.

Change a drawing below and re-run. Don't edit the SVGs by hand.
"""

# Standalone script: long SVG lines, progress output, seeded (non-crypto) randomness.
# ruff: noqa: E501, T201, INP001, S311

from __future__ import annotations

import base64
import io
import itertools
import math
import random
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "images" / "architecture"
FONT_PATH = ROOT / "fork" / "assets" / "fonts" / "Nunito-wght.ttf"
FONT_STACK = "Nunito, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"

INK = "#28243a"
SOFT = "#5f5a6b"
PAPER = "#fdf9ef"
GRID = "#f1e8d2"
MARKER = "#ffd75e"
TAPE = "#ecd796"

# One color per role, the same in every image.
FILLS = {
    "ours": "#c9ddff",  # our code, our agents' work
    "record": "#ffe39b",  # the sync record, and proof
    "upstream": "#e8e2d4",  # upstream Strix
    "done": "#c6eed0",  # people, approvals, results
    "app": "#ffd0c7",  # the app being tested
    "white": "#fffdf7",
}

# Type: size and weight for each kind of text.
TITLE = (19, 800)
NOTE = (15, 600)
LABEL = (14, 700)
HEADING = (26, 800)

# 24x24 line icons.
ICONS = {
    "terminal": "M4 5h16v14H4z M7 9l3 3-3 3 M13 15h4",
    "spark": "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
    "browser": "M4 6h16v12H4z M4 9.5h16 M6.5 7.7h.1 M8.5 7.7h.1",
    "shield": "M12 3l7 3v5c0 4-3 7-7 8-4-1-7-4-7-8V6z M9 12l2 2 4-4",
    "target": "M12 12m-8 0a8 8 0 1 0 16 0a8 8 0 1 0-16 0 M12 12m-4 0a4 4 0 1 0 8 0a4 4 0 1 0-8 0 M12 12h.1",
    "search": "M10.5 10.5m-6 0a6 6 0 1 0 12 0a6 6 0 1 0-12 0 M15 15l5 5",
    "doc": "M6 3h8l4 4v14H6z M14 3v4h4 M9 12h6 M9 16h6",
    "eye": "M2 12s4-6 10-6 10 6 10 6-4 6-10 6-10-6-10-6z M12 12m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0",
    "sync": "M4 10a8 8 0 0 1 13-3l3 3 M20 14a8 8 0 0 1-13 3l-3-3 M17 4v6h-6 M7 20v-6h6",
    "pin": "M12 3l6 6-3 1-4 8-1-7-6-3 8-4z",
    "stack": "M12 3l9 5-9 5-9-5z M3 13l9 5 9-5 M3 17l9 5 9-5",
    "check": "M4 12l5 5L20 6",
    "users": "M8 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z M2 20c0-3.3 2.7-6 6-6s6 2.7 6 6 M17 11a3 3 0 1 0 0-6 M16 14c3 0 6 2.4 6 6",
    "gear": "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M12 2v3 M12 19v3 M2 12h3 M19 12h3 M4.9 4.9l2.1 2.1 M17 17l2.1 2.1 M4.9 19.1l2.1-2.1 M17 7l2.1-2.1",
    "chip": "M7 7h10v10H7z M10 10h4v4h-4z M9 2v3 M15 2v3 M9 19v3 M15 19v3 M2 9h3 M2 15h3 M19 9h3 M19 15h3",
    "merge": "M7 4v8a4 4 0 0 0 4 4h6 M7 4m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0 M7 20m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0 M19 16m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0",
}
SHIELD = "M12 3l7 3v5c0 4-3 7-7 8-4-1-7-4-7-8V6z"

Point = tuple[float, float]


# ---------------------------------------------------------------- the font


class Weight:
    """Nunito at one fixed weight: measures text, and embeds the glyphs an image uses."""

    def __init__(self, weight: int) -> None:
        self.weight = weight
        static = instancer.instantiateVariableFont(
            TTFont(FONT_PATH, recalcTimestamp=False), {"wght": weight}
        )
        buffer = io.BytesIO()
        static.save(buffer)
        self.data = buffer.getvalue()
        self.cmap = static.getBestCmap()
        self.advances = static["hmtx"].metrics
        self.em = static["head"].unitsPerEm

    def width(self, text: str, size: float) -> float:
        missing = sorted({c for c in text if ord(c) not in self.cmap})
        if missing:
            raise SystemExit(f"Nunito has no glyph for {missing} in {text!r}")
        return sum(self.advances[self.cmap[ord(c)]][0] for c in text) * size / self.em

    def face(self, text: str) -> str:
        font = TTFont(io.BytesIO(self.data), recalcTimestamp=False)
        options = subset.Options()
        options.hinting = False
        subsetter = subset.Subsetter(options)
        subsetter.populate(text=text)
        subsetter.subset(font)
        font.flavor = "woff"
        buffer = io.BytesIO()
        font.save(buffer)
        data = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"@font-face{{font-family:Nunito;font-weight:{self.weight};src:url(data:font/woff;base64,{data}) format('woff')}}"


WEIGHTS = {w: Weight(w) for w in (600, 700, 800)}


def text_width(text: str, size: float, weight: int) -> float:
    return WEIGHTS[weight].width(text, size)


# ---------------------------------------------------------------- geometry


def midpoint(a: Point, b: Point) -> Point:
    return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2


def closed_curve(points: list[Point]) -> str:
    """A smooth closed path through the midpoints of the points."""
    start = midpoint(points[-1], points[0])
    parts = [f"M{start[0]:.1f} {start[1]:.1f}"]
    for i, p in enumerate(points):
        m = midpoint(p, points[(i + 1) % len(points)])
        parts.append(f"Q{p[0]:.1f} {p[1]:.1f} {m[0]:.1f} {m[1]:.1f}")
    return "".join(parts) + "Z"


def open_curve(points: list[Point]) -> str:
    parts = [f"M{points[0][0]:.1f} {points[0][1]:.1f}"]
    for a, b in itertools.pairwise(points[1:]):
        m = midpoint(a, b)
        parts.append(f"Q{a[0]:.1f} {a[1]:.1f} {m[0]:.1f} {m[1]:.1f}")
    parts.append(f"L{points[-1][0]:.1f} {points[-1][1]:.1f}")
    return "".join(parts)


def rounded_rect(
    x: float, y: float, w: float, h: float, r: float, step: float = 14.0
) -> list[Point]:
    """Points around a rounded rectangle, clockwise from the top-right corner."""

    def edge(a: Point, b: Point) -> list[Point]:
        n = max(1, round(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
        return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n)]

    corners = [
        (x + w - r, y + r, -90),
        (x + w - r, y + h - r, 0),
        (x + r, y + h - r, 90),
        (x + r, y + r, 180),
    ]
    arcs = []
    for cx, cy, start in corners:
        n = max(2, round(math.pi * r / 2 / step) + 1)
        arcs.append(
            [
                (
                    cx + r * math.cos(math.radians(start + 90 * i / n)),
                    cy + r * math.sin(math.radians(start + 90 * i / n)),
                )
                for i in range(n + 1)
            ]
        )
    points: list[Point] = []
    for i, arc in enumerate(arcs):
        points += arc[:-1]
        points += edge(arc[-1], arcs[(i + 1) % 4][0])
    return points


# ---------------------------------------------------------------- the sheet


@dataclass
class Sheet:
    """One image: a sheet of grid paper and everything drawn on it."""

    width: int
    height: int
    label: str
    seed: int
    shapes: list[str] = field(default_factory=list)
    used: dict[int, set[str]] = field(default_factory=lambda: {w: set() for w in WEIGHTS})
    problems: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)

    def add(self, svg: str) -> None:
        self.shapes.append(svg)

    def shake(self, amount: float) -> float:
        return self.rng.uniform(-amount, amount)

    # -- pen strokes

    def outline(
        self, points: list[Point], *, color: str = INK, dash: str = "", passes: int = 2
    ) -> None:
        """Trace a closed shape with a slightly shaky hand: a firm pass, then a faint one."""
        dashes = f' stroke-dasharray="{dash}"' if dash else ""
        for i in range(passes):
            wobble = 0.9 if i == 0 else 1.2
            shaky = [(x + self.shake(wobble), y + self.shake(wobble)) for x, y in points]
            width, opacity = (2.0, 1.0) if i == 0 else (1.0, 0.4)
            self.add(
                f'<path d="{closed_curve(shaky)}" fill="none" stroke="{color}" stroke-width="{width}" stroke-opacity="{opacity}" stroke-linecap="round" stroke-linejoin="round"{dashes}/>'
            )

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        color: str = INK,
        width: float = 2.2,
        bow: float = 0.0,
        dash: str = "",
    ) -> Point:
        """A slightly bowed stroke. Returns its control point."""
        length = math.hypot(x2 - x1, y2 - y1) or 1.0
        nx, ny = (y1 - y2) / length, (x2 - x1) / length
        bend = bow * length + self.shake(1.2)
        cx, cy = (x1 + x2) / 2 + nx * bend, (y1 + y2) / 2 + ny * bend
        dashes = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(
            f'<path d="M{x1:.1f} {y1:.1f}Q{cx:.1f} {cy:.1f} {x2:.1f} {y2:.1f}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round"{dashes}/>'
        )
        return cx, cy

    def arrow(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        bow: float = 0.0,
        dash: str = "",
        both: bool = False,
    ) -> None:
        cx, cy = self.line(x1, y1, x2, y2, bow=bow, dash=dash)
        self.head(x2, y2, math.atan2(y2 - cy, x2 - cx))
        if both:
            self.head(x1, y1, math.atan2(y1 - cy, x1 - cx))

    def head(self, x: float, y: float, angle: float) -> None:
        (ax, ay), (bx, by) = (
            (x - 12 * math.cos(angle + s), y - 12 * math.sin(angle + s)) for s in (-0.45, 0.45)
        )
        self.add(
            f'<path d="M{ax:.1f} {ay:.1f}L{x:.1f} {y:.1f}L{bx:.1f} {by:.1f}" fill="none" stroke="{INK}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    def circle(self, cx: float, cy: float, r: float) -> None:
        for i in range(2):
            start = self.rng.uniform(0, 2 * math.pi)
            sweep = 2 * math.pi + self.rng.uniform(0.2, 0.45)
            n = max(14, round(r / 2.5))
            points = [
                (
                    cx + (r + self.shake(r * 0.02)) * math.cos(start + sweep * k / n),
                    cy + (r + self.shake(r * 0.02)) * math.sin(start + sweep * k / n),
                )
                for k in range(n + 1)
            ]
            width, opacity = (2.0, 1.0) if i == 0 else (1.0, 0.4)
            self.add(
                f'<path d="{open_curve(points)}" fill="none" stroke="{INK}" stroke-width="{width}" stroke-opacity="{opacity}" stroke-linecap="round"/>'
            )

    def write(
        self,
        x: float,
        y: float,
        text: str,
        style: tuple[float, int],
        *,
        color: str = INK,
        anchor: str = "start",
        room: float | None = None,
    ) -> float:
        size, weight = style
        width = text_width(text, size, weight)
        if room is not None and width > room:
            self.problems.append(f"{text!r} is {width:.0f}px wide, with room for {room:.0f}px")
        self.used[weight].update(text)
        self.add(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT_STACK}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{escape(text)}</text>'
        )
        return width

    def icon(self, name: str, cx: float, cy: float, size: float = 24) -> None:
        scale = size / 24
        self.add(
            f'<g transform="translate({cx - size / 2:.1f} {cy - size / 2:.1f}) scale({scale:.3f})" fill="none" stroke="{INK}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="{ICONS[name]}"/></g>'
        )

    # -- building blocks

    def box(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill: str,
        *,
        radius: float = 10,
        shadow: bool = True,
    ) -> None:
        """A paper cut-out: a hard shadow, a flat fill and a sketched outline."""
        if shadow:
            self.add(
                f'<rect x="{x + 5}" y="{y + 6}" width="{w}" height="{h}" rx="{radius}" fill="{INK}" opacity="0.9"/>'
            )
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}"/>')
        self.outline(rounded_rect(x, y, w, h, radius))

    def card(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        notes: str | tuple[str, ...] = (),
        role: str = "upstream",
        icon: str = "",
    ) -> None:
        """A card: icon on the left, a bold title and optional notes."""
        lines = (notes,) if isinstance(notes, str) else notes
        self.box(x, y, w, h, FILLS[role])
        left = x + 18
        if icon:
            self.icon(icon, x + 31, y + h / 2)
            left = x + 54
        room = x + w - left - 10
        top = y + (h - TITLE[0] - 20 * len(lines)) / 2
        self.write(left, top + 15, title, TITLE, room=room)
        for i, line in enumerate(lines):
            self.write(left, top + 35 + 20 * i, line, NOTE, color=SOFT, room=room)

    def chip(self, x: float, y: float, w: float, h: float, title: str, role: str) -> None:
        """A small card with just a centered title."""
        self.box(x, y, w, h, FILLS[role])
        self.write(x + w / 2, y + h / 2 + 7, title, TITLE, anchor="middle", room=w - 20)

    def tall_card(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        notes: tuple[str, ...],
        role: str,
        icon: str,
    ) -> None:
        """A narrow card with the icon on top and the text centered under it."""
        self.box(x, y, w, h, FILLS[role])
        total = 24 + 12 + TITLE[0] + 20 * len(notes)
        top = y + (h - total) / 2
        center = x + w / 2
        self.icon(icon, center, top + 12)
        self.write(center, top + 51, title, TITLE, anchor="middle", room=w - 24)
        for i, line in enumerate(notes):
            self.write(
                center, top + 71 + 20 * i, line, NOTE, color=SOFT, anchor="middle", room=w - 24
            )

    def group(self, x: float, y: float, w: float, h: float, label: str) -> None:
        self.outline(rounded_rect(x, y, w, h, 16, step=18), color=SOFT, dash="9 7", passes=1)
        self.write(x + 18, y + 26, label, (15, 700), color=SOFT, room=w - 30)

    def heading(self, x: float, y: float, text: str) -> None:
        width = text_width(text, *HEADING)
        lift = self.shake(1.5)
        self.add(
            f'<path d="M{x - 8:.1f} {y - 7:.1f}Q{x + width / 2:.1f} {y - 10 + lift:.1f} {x + width + 8:.1f} {y - 6:.1f}" fill="none" stroke="{MARKER}" stroke-width="16" stroke-linecap="round" opacity="0.85"/>'
        )
        self.write(x, y, text, HEADING)

    def tape(self, cx: float, cy: float, angle: float) -> None:
        self.add(
            f'<rect x="{cx - 60}" y="{cy - 15}" width="120" height="30" fill="{TAPE}" opacity="0.75" transform="rotate({angle} {cx} {cy})"/>'
        )

    def swatch(self, x: float, y: float, role: str, text: str) -> None:
        self.box(x, y - 14, 18, 18, FILLS[role], radius=4, shadow=False)
        self.write(x + 30, y, text, (16, 600))

    def svg(self) -> str:
        w, h = self.width, self.height
        faces = "".join(
            WEIGHTS[weight].face("".join(sorted(chars | {" "})))
            for weight, chars in self.used.items()
            if chars
        )
        grid = f'<pattern id="grid" width="22" height="22" patternUnits="userSpaceOnUse"><path d="M22 0H0V22" fill="none" stroke="{GRID}" stroke-width="1"/></pattern>'
        return "\n".join(
            [
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{escape(self.label)}">',
                f"<title>{escape(self.label)}</title>",
                f"<defs><style>{faces}</style>{grid}</defs>",
                f'<rect width="{w}" height="{h}" rx="18" fill="{PAPER}"/>',
                f'<rect width="{w}" height="{h}" rx="18" fill="url(#grid)"/>',
                *self.shapes,
                "</svg>",
                "",
            ]
        )


# ---------------------------------------------------------------- the images

WIDTH = 1080


def hero() -> Sheet:
    s = Sheet(
        WIDTH,
        350,
        "jitera-pentest: AI penetration testing that finds attacks before they happen, and tests how your team detects and responds",
        seed=7,
    )
    s.tape(84, 14, -6)
    s.tape(WIDTH - 90, 16, 7)

    # the name, with a scribbled underline
    s.box(58, 58, 72, 72, FILLS["ours"], radius=14)
    s.write(94, 111, "J", (46, 800), anchor="middle")
    name = s.write(152, 112, "jitera-pentest", (56, 800))
    wave = [
        (154 + (name - 4) * i / 24, 130 + 2.5 * math.sin(i * 1.3) + s.shake(0.6)) for i in range(25)
    ]
    s.add(
        f'<path d="{open_curve(wave)}" fill="none" stroke="{INK}" stroke-width="2.4" stroke-linecap="round"/>'
    )

    s.write(
        60,
        186,
        "AI penetration testing that finds attacks before they happen,",
        (23, 600),
        room=670,
    )
    s.write(60, 218, "and tests how your team detects and responds.", (23, 600), room=670)

    x = 60
    for role, icon, text in (
        ("app", "search", "Find the attack first"),
        ("ours", "shield", "Rehearse the defense"),
    ):
        width = 58 + text_width(text, 18, 700) + 24
        s.box(x, 250, width, 48, FILLS[role], radius=24)
        s.icon(icon, x + 32, 274)
        s.write(x + 56, 280, text, (18, 700))
        x += width + 24
    s.write(62, 332, "Open source · built on Strix · Apache-2.0", (16, 600), color=SOFT)

    # doodle: a web page, a bug under a magnifying glass, a shield
    s.box(752, 58, 256, 190, FILLS["white"], radius=12)
    s.line(752, 86, 1008, 86, width=2)
    for i, role in enumerate(("app", "record", "done")):
        s.add(
            f'<circle cx="{770 + 14 * i}" cy="72" r="4.5" fill="{FILLS[role]}" stroke="{INK}" stroke-width="1.5"/>'
        )
    s.add(
        f'<rect x="818" y="65" width="172" height="14" rx="7" fill="none" stroke="{SOFT}" stroke-width="1.4"/>'
    )
    for i, length in enumerate((120, 84, 132, 70)):
        s.line(
            772,
            112 + 22 * i,
            772 + length,
            112 + 22 * i,
            color="#e9dfc6" if i % 2 else "#d9cfb6",
            width=6,
        )
    s.box(772, 204, 76, 28, FILLS["ours"], radius=8, shadow=False)
    s.add(f'<path d="M972 186L1022 240" stroke="{INK}" stroke-width="11" stroke-linecap="round"/>')
    s.add('<circle cx="934" cy="148" r="48" fill="#e2f0ff" opacity="0.92"/>')
    s.circle(934, 148, 48)
    for part in (
        f'<path d="M931 124L924 114 M937 124L944 114" stroke="{INK}" stroke-width="2" stroke-linecap="round"/>',
        f'<path d="M922 140L910 134 M921 150L907 150 M922 160L910 167 M946 140L958 134 M947 150L961 150 M946 160L958 167" stroke="{INK}" stroke-width="2" stroke-linecap="round"/>',
        f'<ellipse cx="934" cy="151" rx="13" ry="16" fill="#ff8f7d" stroke="{INK}" stroke-width="2"/>',
        f'<circle cx="934" cy="131" r="7" fill="{INK}"/>',
        f'<path d="M934 136V166" stroke="{INK}" stroke-width="1.6"/>',
        f'<circle cx="928" cy="146" r="2.4" fill="{INK}"/><circle cx="940" cy="149" r="2.4" fill="{INK}"/><circle cx="929" cy="158" r="2.2" fill="{INK}"/><circle cx="940" cy="160" r="2.2" fill="{INK}"/>',
    ):
        s.add(part)
    for dx, dy, fill in ((4, 5, INK), (0, 0, FILLS["done"])):
        s.add(
            f'<path transform="translate({720 + dx} {198 + dy}) scale(3)" d="{SHIELD}" fill="{fill}" stroke="{INK}" stroke-width="0.7" stroke-linejoin="round"/>'
        )
    s.add(
        f'<path transform="translate(720 198) scale(3)" d="M9 12l2 2 4-4" fill="none" stroke="{INK}" stroke-width="0.9" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    return s


def scan_flow() -> Sheet:
    s = Sheet(
        WIDTH,
        444,
        "How a scan runs: jitera-pentest starts a bootstrap, then AI agents in a Docker sandbox run a simulated attack against your authorized app; findings become reports and a local viewer",
        seed=21,
    )
    s.heading(40, 58, "How a scan runs")
    s.card(40, 100, 196, 72, "jitera-pentest", "your command", "ours", "terminal")
    s.card(270, 100, 202, 72, "bootstrap", "brand · .env · hooks", "ours", "gear")
    s.arrow(242, 136, 264, 136)
    s.arrow(478, 136, 498, 136)

    s.group(502, 78, 340, 226, "Docker sandbox")
    s.card(518, 118, 152, 64, "AI agents", role="upstream", icon="spark")
    s.card(680, 118, 150, 64, "browser", role="upstream", icon="browser")
    s.card(518, 200, 152, 64, "proxy", role="upstream", icon="eye")
    s.card(680, 200, 150, 64, "tools", role="upstream", icon="gear")

    s.tall_card(924, 108, 116, 156, "Your app", ("authorized", "target"), "app", "target")
    s.arrow(848, 190, 916, 190, bow=-0.08)
    s.write(883, 218, "simulated", LABEL, color=SOFT, anchor="middle", room=70)
    s.write(883, 236, "attack", LABEL, color=SOFT, anchor="middle")
    s.write(1040, 302, "every request carries", NOTE, color=SOFT, anchor="end")
    s.write(1040, 322, "a Jitera User-Agent", (15, 700), anchor="end")

    s.card(40, 350, 400, 68, "Reports", "Markdown · JSON · CSV · SARIF", "done", "doc")
    s.card(484, 350, 300, 68, "Local viewer", "jitera-pentest view", "done", "eye")
    s.arrow(570, 310, 380, 344, bow=-0.12)
    s.write(458, 318, "findings", LABEL, color=SOFT, anchor="middle")
    s.arrow(690, 310, 690, 344)
    return s


def fork_sync() -> Sheet:
    s = Sheet(
        WIDTH,
        474,
        "How we stay in sync with upstream: upstream code is edited in place, our code lives in strix/jitera, and fork/ keeps a checkpoint and one patch per changed file, which a sync replays onto the new upstream",
        seed=31,
    )
    s.heading(40, 58, "How we stay in sync with upstream")

    s.group(40, 86, 494, 214, "the repo")
    s.card(58, 126, 222, 70, "strix/ (upstream)", "edited in place", "upstream", "stack")
    s.card(296, 126, 220, 70, "strix/jitera/", "our code and tests", "ours", "spark")
    s.card(58, 212, 222, 70, "eval/", "the quality gate", "ours", "eye")
    s.card(296, 212, 220, 70, "docs/ · README", role="ours", icon="doc")

    s.group(40, 318, 494, 138, "fork/ — the sync record, never patched")
    s.card(58, 360, 222, 72, "CHECKPOINT", "upstream commit", "record", "pin")
    s.card(296, 360, 220, 72, "patches/", "one per changed file", "record", "stack")

    steps = [
        ("1. Upstream release", "fork/dev sync fetches it", "upstream", "sync"),
        (
            "2. Back to checkpoint, take upstream",
            "clean merge: the tree is pure upstream",
            "upstream",
            "merge",
        ),
        ("3. Re-apply our patches", "fix any that conflict", "record", "stack"),
        ("4. Move checkpoint · PR into main", (), "done", "check"),
    ]
    for i, (title, notes, role, icon) in enumerate(steps):
        y = 90 + 96 * i
        s.card(614, y, 426, 66, title, notes, role, icon)
        if i:
            s.arrow(827, y - 22, 827, y - 4)
    s.arrow(524, 404, 608, 318, bow=0.18)
    s.write(552, 440, "replay", LABEL, color=SOFT)
    return s


def dev_loop() -> Sheet:
    s = Sheet(
        WIDTH,
        380,
        "How a change ships: people set direction; an agent picks a plan item, implements it and proves it with verify, tests and the eval; the proof goes into a PR; people approve; it merges; the agent updates the plans and picks the next item",
        seed=41,
    )
    s.heading(40, 58, "How a change ships: agents build, the eval decides")
    columns = [40 + 261 * i for i in range(4)]
    width, height, top, bottom = 217, 70, 100, 228
    for x, (title, note, role, icon) in zip(
        columns,
        [
            ("People", "set direction", "done", "users"),
            ("Agent", "picks a plan item", "ours", "spark"),
            ("Implement", "/fork-change", "ours", "terminal"),
            ("Prove", "verify · test · eval", "record", "check"),
        ],
        strict=True,
    ):
        s.card(x, top, width, height, title, note, role, icon)
    for x, (title, note, role, icon) in zip(
        columns,
        [
            ("Update plans", "next item ready", "ours", "doc"),
            ("Merge", "a merge commit", "done", "merge"),
            ("People approve", "review the proof", "done", "users"),
            ("A PR", "proof pasted in", "record", "doc"),
        ],
        strict=True,
    ):
        s.card(x, bottom, width, height, title, note, role, icon)
    for left, right in itertools.pairwise(columns):
        s.arrow(left + width + 10, top + height / 2, right - 5, top + height / 2)
        s.arrow(right - 5, bottom + height / 2, left + width + 12, bottom + height / 2)
    s.arrow(columns[3] + width / 2, top + height + 9, columns[3] + width / 2, bottom - 5)
    s.arrow(
        columns[0] + width / 2, bottom - 5, columns[1] + 40, top + height + 9, bow=0.15, dash="7 6"
    )
    s.write(columns[0] + width / 2 + 62, top + height + 32, "next item", LABEL, color=SOFT)
    s.swatch(40, 348, "done", "People own direction, approvals, spending, merges.")
    s.swatch(560, 348, "ours", "Agents own code, tests, docs, syncs, the proof.")
    return s


def engine() -> Sheet:
    s = Sheet(
        WIDTH,
        536,
        "Inside a scan: targets and instructions go to a lead agent, which plans the work and creates specialist agents. They share memory and think with any LLM. Their tools run in a Docker sandbox against your authorized app. Findings need proof, get a CVSS score and a duplicate check, and become reports.",
        seed=51,
    )
    s.heading(40, 58, "Inside a scan: how the engine works")

    # what goes in
    s.card(40, 100, 200, 80, "Targets", ("code, repos,", "URLs, API specs"), "upstream", "doc")
    s.card(
        40,
        200,
        200,
        80,
        "Instructions",
        ("scope, rules and", "expert playbooks"),
        "record",
        "stack",
    )
    s.card(40, 300, 200, 80, "Any LLM", ("any provider,", "via LiteLLM"), "record", "chip")
    s.arrow(248, 140, 274, 140)
    s.arrow(248, 240, 274, 240)
    s.arrow(250, 340, 274, 340, both=True)

    # the agents
    s.group(280, 84, 356, 312, "Agent team")
    s.card(296, 124, 324, 66, "Lead agent", "plans the scan, splits the work", "ours", "spark")
    for x, name in ((296, "Recon"), (408, "Exploit"), (520, "Verify")):
        s.chip(x, 224, 100, 48, name, "ours")
        s.arrow(x + 50, 198, x + 50, 218)
    s.write(
        458,
        296,
        "created as needed; they message each other",
        LABEL,
        color=SOFT,
        anchor="middle",
        room=324,
    )
    s.card(
        296,
        306,
        324,
        76,
        "Shared memory",
        ("threat model, coverage, notes,", "read and written by every agent"),
        "record",
        "pin",
    )

    # the tools, in the sandbox
    s.arrow(642, 240, 670, 240)
    s.group(676, 84, 364, 312, "Tools, in a sandbox (Docker)")
    for i, (title, note, icon) in enumerate(
        (
            ("Shell", "nmap, ffuf, python and more", "terminal"),
            ("Browser", "a real Chromium browser", "browser"),
            ("HTTP proxy", "records and replays every request", "eye"),
            ("Workspace", "your code, to read and patch", "doc"),
        )
    ):
        s.card(692, 122 + 68 * i, 332, 56, title, note, "upstream", icon)

    # what comes out
    s.arrow(858, 402, 858, 426)
    s.card(676, 432, 364, 76, "Your app", "the authorized target", "app", "target")
    s.arrow(380, 402, 200, 426, bow=-0.1)
    s.card(
        40,
        432,
        262,
        76,
        "Findings",
        ("proof of concept + evidence,", "scored with CVSS"),
        "record",
        "check",
    )
    s.arrow(310, 470, 364, 470)
    s.write(339, 460, "deduped", LABEL, color=SOFT, anchor="middle")
    s.card(
        372,
        432,
        264,
        76,
        "Reports",
        ("Markdown, JSON, SARIF", "and CSV, plus a summary"),
        "done",
        "doc",
    )
    return s


IMAGES = {
    "hero": hero,
    "scan-flow": scan_flow,
    "engine": engine,
    "fork-sync": fork_sync,
    "dev-loop": dev_loop,
}


def main() -> None:
    sheets = {name: draw() for name, draw in IMAGES.items()}
    problems = [
        f"{name}: {problem}" for name, sheet in sheets.items() for problem in sheet.problems
    ]
    if problems:
        raise SystemExit("Labels that don't fit, nothing written:\n  " + "\n  ".join(problems))
    OUT.mkdir(parents=True, exist_ok=True)
    for name, sheet in sheets.items():
        path = OUT / f"{name}.svg"
        path.write_text(sheet.svg(), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
