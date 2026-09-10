"""
DSL available inside render().

All functions and constants defined here are injected into the
scope where render() is executed. The render code does not need
to import anything: everything is already in scope.

Public entry point: DSL_EXPORTS — a dict of names to objects.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

# ─────────────────────────────────────────────────────────────
# PALETTE
# ─────────────────────────────────────────────────────────────

PALETTE = [
    "#0d0221",  # deep dark
    "#1b1b3a",  # dark accent
    "#ff2a6d",  # hot pink
    "#05d9e8",  # cyan
    "#f9f871",  # yellow
]

PALETTE_WARM = ["#2b1a12", "#7a2e1a", "#d96b2b", "#f2b950", "#fceec4"]
PALETTE_COOL = ["#0a1a2a", "#1e3a5a", "#4a7aa8", "#a8c8e8", "#eef6ff"]
PALETTE_MONO = ["#0a0a0a", "#3a3a3a", "#7a7a7a", "#b8b8b8", "#f0f0f0"]

# ─────────────────────────────────────────────────────────────
# ID COUNTER (for gradients, filters, masks)
# ─────────────────────────────────────────────────────────────

_id_counter = 0


def _next_id(prefix: str) -> str:
    global _id_counter
    _id_counter += 1
    return f"{prefix}{_id_counter}"


# ─────────────────────────────────────────────────────────────
# COLOR HELPERS
# ─────────────────────────────────────────────────────────────

def _hex_to_rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    return f"#{r:02x}{g:02x}{b:02x}"


def lighten(color: str, amount: float) -> str:
    """amount 0..1, mix toward white."""
    r, g, b = _hex_to_rgb(color)
    return _rgb_to_hex(r + (255 - r) * amount,
                       g + (255 - g) * amount,
                       b + (255 - b) * amount)


def darken(color: str, amount: float) -> str:
    """amount 0..1, mix toward black."""
    r, g, b = _hex_to_rgb(color)
    return _rgb_to_hex(r * (1 - amount), g * (1 - amount), b * (1 - amount))


def mix(c1: str, c2: str, t: float) -> str:
    """Linear blend between two hex colors. t=0 -> c1, t=1 -> c2."""
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex(r1 + (r2 - r1) * t,
                       g1 + (g2 - g1) * t,
                       b1 + (b2 - b1) * t)


def hsl(h: float, s: float, l: float) -> str: # noqa: E741
    """h in degrees, s and l in 0..1."""
    import colorsys
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, l, s)
    return _rgb_to_hex(r * 255, g * 255, b * 255)


def palette_lerp(t: float, palette: list[str] | None = None) -> str:
    """Return a color interpolated along the palette. t in 0..1."""
    pal = palette or PALETTE
    t = max(0.0, min(1.0, t))
    n = len(pal) - 1
    i = min(int(t * n), n - 1)
    local = t * n - i
    return mix(pal[i], pal[i + 1], local)


def _color(value) -> str:
    """Normalize a color-ish value to an SVG string."""
    if value is None:
        return "none"
    if isinstance(value, str):
        return value
    if isinstance(value, (Gradient, Pattern)):
        return f"url(#{value.id})"
    raise TypeError(f"Not a color: {value!r}")


# ─────────────────────────────────────────────────────────────
# GRADIENTS
# ─────────────────────────────────────────────────────────────

@dataclass
class Gradient:
    id: str
    kind: str          # "linear" | "radial" | "conic"
    stops: list[tuple[float, str]]
    attrs: dict

    def to_svg(self) -> str:
        stops_xml = "".join(
            f'<stop offset="{off}" stop-color="{col}"/>'
            for off, col in self.stops
        )
        attrs = " ".join(f'{k}="{v}"' for k, v in self.attrs.items())
        return (f'<{self.kind}Gradient id="{self.id}" {attrs}>'
                f'{stops_xml}</{self.kind}Gradient>')


def grad_lin(stops, angle: float = 0) -> Gradient:
    """Linear gradient. angle in degrees, 0 = left-to-right, 90 = top-to-bottom."""
    a = math.radians(angle)
    x1 = 0.5 - math.cos(a) * 0.5
    y1 = 0.5 - math.sin(a) * 0.5
    x2 = 0.5 + math.cos(a) * 0.5
    y2 = 0.5 + math.sin(a) * 0.5
    return Gradient(_next_id("lg"), "linear", list(stops),
                    {"x1": x1, "y1": y1, "x2": x2, "y2": y2})


def grad_rad(stops, cx: float = 0.5, cy: float = 0.5, r: float = 0.5) -> Gradient:
    """Radial gradient. cx, cy, r in 0..1 of bounding box."""
    return Gradient(_next_id("rg"), "radial", list(stops),
                    {"cx": cx, "cy": cy, "r": r})


def grad_conic(stops, cx: float = 0.5, cy: float = 0.5) -> Gradient:
    """Conic gradient (SVG 2). Supported by modern browsers."""
    return Gradient(_next_id("cg"), "conic", list(stops),
                    {"cx": cx, "cy": cy})


# ─────────────────────────────────────────────────────────────
# PATTERN (simple repeating fill)
# ─────────────────────────────────────────────────────────────

@dataclass
class Pattern:
    id: str
    element: Element
    width: float
    height: float

    def to_svg(self) -> str:
        return (f'<pattern id="{self.id}" width="{self.width}" '
                f'height="{self.height}" patternUnits="userSpaceOnUse">'
                f'{self.element.to_svg()}</pattern>')


def pattern(element: Element, width: float, height: float) -> Pattern:
    """Tile the element as a fill pattern."""
    return Pattern(_next_id("pat"), element, width, height)


# ─────────────────────────────────────────────────────────────
# ELEMENTS
# ─────────────────────────────────────────────────────────────

@dataclass
class Element:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list[Element] = field(default_factory=list)
    text: str | None = None
    filters: list[str] = field(default_factory=list)
    opacity_value: float | None = None

    def to_svg(self) -> str:
        a = dict(self.attrs)
        if self.filters:
            a["filter"] = f"url(#{self.filters[0]})"
        if self.opacity_value is not None:
            a["opacity"] = self.opacity_value
        attrs = " ".join(
            f'{k.replace("_", "-")}="{v}"'
            for k, v in a.items()
            if v is not None
        )
        if self.children:
            inner = "".join(c.to_svg() for c in self.children)
            return f"<{self.tag} {attrs}>{inner}</{self.tag}>"
        if self.text is not None:
            return f"<{self.tag} {attrs}>{self.text}</{self.tag}>"
        return f"<{self.tag} {attrs}/>"


def _common(fill, stroke, sw) -> dict:
    return {
        "fill": _color(fill) if fill is not None else "none",
        "stroke": _color(stroke) if stroke is not None else None,
        "stroke_width": sw if stroke else None,
    }


# ─────────────────────────────────────────────────────────────
# PRIMITIVES
# ─────────────────────────────────────────────────────────────

def rect(x, y, w, h, fill=None, stroke=None, sw=0, rx=0) -> Element:
    a = {"x": x, "y": y, "width": w, "height": h, **_common(fill, stroke, sw)}
    if rx:
        a["rx"] = rx
    return Element("rect", a)


def circle(cx, cy, r, fill=None, stroke=None, sw=0) -> Element:
    return Element("circle",
                   {"cx": cx, "cy": cy, "r": r, **_common(fill, stroke, sw)})


def ellipse(cx, cy, rx, ry, fill=None, stroke=None, sw=0) -> Element:
    return Element("ellipse",
                   {"cx": cx, "cy": cy, "rx": rx, "ry": ry,
                    **_common(fill, stroke, sw)})


def line(x1, y1, x2, y2, stroke, sw=1) -> Element:
    return Element("line",
                   {"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "stroke": _color(stroke), "stroke_width": sw, "fill": "none"})


def polygon(points, fill=None, stroke=None, sw=0) -> Element:
    pts = " ".join(f"{x},{y}" for x, y in points)
    return Element("polygon", {"points": pts, **_common(fill, stroke, sw)})


def polyline(points, stroke, sw=1, fill=None) -> Element:
    pts = " ".join(f"{x},{y}" for x, y in points)
    a = {"points": pts, **_common(fill, stroke, sw)}
    a["fill"] = _color(fill) if fill is not None else "none"
    return Element("polyline", a)


def path(d, fill=None, stroke=None, sw=0) -> Element:
    return Element("path", {"d": d, **_common(fill, stroke, sw)})


def arc(cx, cy, r, a0, a1, stroke, sw=1) -> Element:
    """Arc from angle a0 to a1 (degrees, clockwise, 0 = right)."""
    x0, y0 = polar(cx, cy, r, a0)
    x1, y1 = polar(cx, cy, r, a1)
    large = 1 if abs(a1 - a0) > 180 else 0
    sweep = 1 if a1 > a0 else 0
    d = f"M {x0} {y0} A {r} {r} 0 {large} {sweep} {x1} {y1}"
    return path(d, fill=None, stroke=stroke, sw=sw)


def star(cx, cy, r_out, r_in, points=5, fill=None, stroke=None, sw=0) -> Element:
    """Regular star with alternating outer/inner radii."""
    pts = []
    step = math.pi / points
    start = -math.pi / 2
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = start + i * step
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return polygon(pts, fill=fill, stroke=stroke, sw=sw)


def ring(cx, cy, r, w, fill=None, stroke=None) -> Element:
    """Ring (annulus) as a stroked circle with no fill by default."""
    return circle(cx, cy, r, fill=fill, stroke=stroke or fill, sw=w)


def grid(x, y, w, h, cols, rows, fill=None, stroke=None, sw=1) -> Element:
    """Grid of cells as a group of lines."""
    children = []
    for i in range(cols + 1):
        cx = x + w * i / cols
        children.append(line(cx, y, cx, y + h, stroke=stroke or "#000", sw=sw))
    for j in range(rows + 1):
        cy = y + h * j / rows
        children.append(line(x, cy, x + w, cy, stroke=stroke or "#000", sw=sw))
    return group(children)


def text(x, y, s, size=16, fill="#000", family="sans-serif",
         anchor="middle", weight="normal") -> Element:
    e = Element("text",
                {"x": x, "y": y, "font_size": size, "font_family": family,
                 "text_anchor": anchor, "font_weight": weight,
                 "fill": _color(fill)})
    e.text = str(s)
    return e


# ─────────────────────────────────────────────────────────────
# CURVES & ORGANIC SHAPES
# ─────────────────────────────────────────────────────────────

def smooth(points, closed=False) -> str:
    """Catmull-Rom smooth path through points. Returns a path 'd' string."""
    pts = list(points)
    if len(pts) < 2:
        return ""
    if closed:
        pts = pts + [pts[0], pts[1]]
    else:
        pts = [pts[0]] + pts + [pts[-1]]

    def p(i):
        return pts[i]

    d = f"M {p(1)[0]} {p(1)[1]}"
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = p(i - 1), p(i), p(i + 1), p(i + 2)
        c1x = p1[0] + (p2[0] - p0[0]) / 6
        c1y = p1[1] + (p2[1] - p0[1]) / 6
        c2x = p2[0] - (p3[0] - p1[0]) / 6
        c2y = p2[1] - (p3[1] - p1[1]) / 6
        d += f" C {c1x} {c1y} {c2x} {c2y} {p2[0]} {p2[1]}"
    if closed:
        d += " Z"
    return d


def blob(cx, cy, r, wobble=0.2, points=12, fill=None, stroke=None, sw=0,
         seed=None) -> Element:
    """Organic roundish shape — useful for clouds, bushes, rocks."""
    rng = random.Random(seed)
    pts = []
    for i in range(points):
        a = 2 * math.pi * i / points
        rr = r * (1 + rng.uniform(-wobble, wobble))
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return path(smooth(pts, closed=True), fill=fill, stroke=stroke, sw=sw)


def wave(x0, y0, x1, y1, amp=20, periods=3, fill=None, stroke=None,
         sw=2, steps=40) -> Element:
    """Sine wave from (x0,y0) to (x1,y1)."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t + amp * math.sin(2 * math.pi * periods * t)
        pts.append((x, y))
    return path(smooth(pts), fill=fill, stroke=stroke, sw=sw)


def flame(cx, cy, w, h, fill=None, stroke=None, sw=0, flip=False) -> Element:
    """Teardrop/flame shape, pointing up by default."""
    s = -1 if flip else 1
    pts = [
        (cx, cy - h * s),
        (cx + w * 0.5, cy - h * 0.2 * s),
        (cx + w * 0.35, cy + h * 0.5 * s),
        (cx, cy + h * s),
        (cx - w * 0.35, cy + h * 0.5 * s),
        (cx - w * 0.5, cy - h * 0.2 * s),
    ]
    return path(smooth(pts, closed=True), fill=fill, stroke=stroke, sw=sw)


# ─────────────────────────────────────────────────────────────
# PATH BUILDER
# ─────────────────────────────────────────────────────────────

class PathBuilder:
    def __init__(self):
        self._parts: list[str] = []

    def move(self, x, y):
        self._parts.append(f"M {x} {y}")
        return self

    def line(self, x, y):
        self._parts.append(f"L {x} {y}")
        return self

    def curve(self, x1, y1, x2, y2, x, y):
        self._parts.append(f"C {x1} {y1} {x2} {y2} {x} {y}")
        return self

    def quad(self, x1, y1, x, y):
        self._parts.append(f"Q {x1} {y1} {x} {y}")
        return self

    def arc(self, rx, ry, rot, large, sweep, x, y):
        self._parts.append(f"A {rx} {ry} {rot} {large} {sweep} {x} {y}")
        return self

    def close(self):
        self._parts.append("Z")
        return self

    def d(self) -> str:
        return " ".join(self._parts)


# ─────────────────────────────────────────────────────────────
# GROUPS & TRANSFORMS
# ─────────────────────────────────────────────────────────────

def group(children, translate=(0, 0), rotate=0, scale=1,
          origin: tuple[float, float] | None = None) -> Element:
    transforms = []
    tx, ty = translate
    if tx or ty:
        transforms.append(f"translate({tx},{ty})")
    if rotate:
        if origin:
            transforms.append(f"rotate({rotate} {origin[0]} {origin[1]})")
        else:
            transforms.append(f"rotate({rotate})")
    if scale != 1:
        if origin:
            transforms.append(
                f"translate({origin[0]} {origin[1]}) scale({scale}) "
                f"translate({-origin[0]} {-origin[1]})"
            )
        else:
            transforms.append(f"scale({scale})")
    return Element("g",
                   {"transform": " ".join(transforms) if transforms else None},
                   children=list(children))


def transform(element, translate=(0, 0), rotate=0, scale=1) -> Element:
    return group([element], translate=translate, rotate=rotate, scale=scale)


def rotate(element, angle, cx=None, cy=None) -> Element:
    return group([element], rotate=angle,
                 origin=(cx, cy) if cx is not None else None)


def scale(element, factor, cx=None, cy=None) -> Element:
    return group([element], scale=factor,
                 origin=(cx, cy) if cx is not None else None)


def mirror_x(element, axis) -> Element:
    """Mirror across a vertical line x=axis."""
    return group([element],
                 translate=(2 * axis, 0), scale=1,
                 origin=None) if False else _mirror_impl(element, axis, "x")


def mirror_y(element, axis) -> Element:
    return _mirror_impl(element, axis, "y")


def _mirror_impl(element, axis, kind: str) -> Element:
    sx = -1 if kind == "x" else 1
    sy = -1 if kind == "y" else 1
    e = group([element],
              translate=(axis * (1 - sx), axis * (1 - sy)),
              scale=1)

    e.attrs["transform"] = (
        f"translate({axis * (1 - sx)} {axis * (1 - sy)}) "
        f"scale({sx} {sy}) translate({-axis * (1 - sx)} {-axis * (1 - sy)})"
    )
    e.children = [element]
    return e


def opacity(element, value) -> Element:
    element.opacity_value = value
    return element


def clip(element, mask_element) -> Element:
    """Clip element by another element's shape (uses clipPath)."""
    cid = _next_id("clip")
    cp = Element("clipPath", {"id": cid}, children=[mask_element])
    wrapped = group([cp, element])
    wrapped.attrs["clip_path"] = f"url(#{cid})"
    return wrapped


# ─────────────────────────────────────────────────────────────
# EFFECTS (filters)
# ─────────────────────────────────────────────────────────────

_FILTER_DEFS: list[str] = []


def _register_filter(fid: str, body: str) -> None:
    _FILTER_DEFS.append(f'<filter id="{fid}" x="-50%" y="-50%" '
                        f'width="200%" height="200%">{body}</filter>')


def shadow(element, dx=4, dy=4, blur=6, color="#000", opacity=0.3) -> Element:
    """Drop shadow via feGaussianBlur + feOffset."""
    fid = _next_id("sh")
    body = (
        f'<feDropShadow dx="{dx}" dy="{dy}" stdDeviation="{blur}" '
        f'flood-color="{color}" flood-opacity="{opacity}"/>'
    )
    _register_filter(fid, body)
    e = group([element])
    e.filters = [fid]
    return e


def glow(element, blur=8, color="#fff", opacity=0.8) -> Element:
    """Outer glow via feGaussianBlur + feMerge."""
    fid = _next_id("gl")
    body = (
        f'<feGaussianBlur stdDeviation="{blur}" result="b"/>'
        f'<feFlood flood-color="{color}" flood-opacity="{opacity}" result="c"/>'
        f'<feComposite in="c" in2="b" operator="in" result="g"/>'
        f'<feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge>'
    )
    _register_filter(fid, body)
    e = group([element])
    e.filters = [fid]
    return e


def blur(element, amount=4) -> Element:
    fid = _next_id("bl")
    body = f'<feGaussianBlur stdDeviation="{amount}"/>'
    _register_filter(fid, body)
    e = group([element])
    e.filters = [fid]
    return e


def reflect(element, axis="x", origin=256, fade=0.4) -> Element:
    """Mirror element across axis with optional fade (for water reflections)."""
    flipped = _mirror_impl(element, origin, axis)
    if fade is not None:
        flipped = opacity(flipped, fade)
    return flipped


def vignette(canvas: Canvas, strength=0.5, color="#000") -> None:
    """Add radial darkening at edges directly to canvas."""
    grad = grad_rad(
        [(0.55, mix(color, "#000000", 0) or color), (1.0, color)],
        cx=0.5, cy=0.5, r=0.75,
    )
    grad.stops = [(0.55, "rgba(0,0,0,0)"), (1.0, color)]
    grad.attrs = {"cx": 0.5, "cy": 0.5, "r": 0.75}
    add(canvas, grad)
    add(canvas, rect(0, 0, canvas.width, canvas.height, fill=grad))
    canvas.children[-1].opacity_value = strength


# ─────────────────────────────────────────────────────────────
# REPEAT HELPERS
# ─────────────────────────────────────────────────────────────

def repeat(element, count, dx=0, dy=0) -> Element:
    """Repeat element count times with step (dx, dy)."""
    return group([transform(element, translate=(dx * i, dy * i))
                  for i in range(count)])


def radial_repeat(element, count, cx, cy) -> Element:
    """Repeat element count times around (cx, cy)."""
    children = []
    for i in range(count):
        angle = 360 * i / count
        children.append(group([element], rotate=angle, origin=(cx, cy)))
    return group(children)


def scatter(element, count, area, seed=0) -> Element:
    """Randomly place element count times within area=(x,y,w,h)."""
    rng = random.Random(seed)
    x, y, w, h = area
    return group([transform(element,
                            translate=(x + rng.random() * w,
                                       y + rng.random() * h))
                  for _ in range(count)])


# ─────────────────────────────────────────────────────────────
# CANVAS
# ─────────────────────────────────────────────────────────────

@dataclass
class Canvas:
    width: int
    height: int
    children: list = field(default_factory=list)
    gradients: list = field(default_factory=list)
    patterns: list = field(default_factory=list)

    def to_svg(self) -> str:
        defs = []
        if _FILTER_DEFS:
            defs.extend(_FILTER_DEFS)
        if self.gradients:
            defs.extend(g.to_svg() for g in self.gradients)
        if self.patterns:
            defs.extend(p.to_svg() for p in self.patterns)
        defs_xml = f"<defs>{''.join(defs)}</defs>" if defs else ""
        body = "".join(c.to_svg() for c in self.children)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'width="{self.width}" height="{self.height}" '
                f'viewBox="0 0 {self.width} {self.height}">'
                f'{defs_xml}{body}</svg>')


def new_canvas(width=512, height=512) -> Canvas:
    # reset filter defs between runs
    _FILTER_DEFS.clear()
    return Canvas(width=width, height=height)


def add(canvas: Canvas, element) -> None:
    if isinstance(element, Gradient):
        canvas.gradients.append(element)
    elif isinstance(element, Pattern):
        canvas.patterns.append(element)
    elif isinstance(element, Element):
        canvas.children.append(element)
    elif isinstance(element, (list, tuple)):
        for e in element:
            add(canvas, e)
    else:
        raise TypeError(f"Cannot add: {element!r}")


def to_svg(canvas: Canvas) -> str:
    return canvas.to_svg()


def bg(canvas: Canvas, color) -> None:
    """Fill the whole canvas with a color or gradient."""
    if isinstance(color, Gradient):
        add(canvas, color)
    add(canvas, rect(0, 0, canvas.width, canvas.height, fill=color))


# ─────────────────────────────────────────────────────────────
# UTILS
# ─────────────────────────────────────────────────────────────

def lerp(a, b, t):
    return a + (b - a) * t


def polar(cx, cy, r, angle_deg):
    a = math.radians(angle_deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


# ─────────────────────────────────────────────────────────────
# EXPORTS
# ─────────────────────────────────────────────────────────────

DSL_EXPORTS = {
    # canvas
    "new_canvas": new_canvas,
    "add": add,
    "to_svg": to_svg,
    "bg": bg,
    # primitives
    "rect": rect,
    "circle": circle,
    "ellipse": ellipse,
    "line": line,
    "polygon": polygon,
    "polyline": polyline,
    "path": path,
    "arc": arc,
    "star": star,
    "ring": ring,
    "grid": grid,
    "text": text,
    # curves
    "smooth": smooth,
    "blob": blob,
    "wave": wave,
    "flame": flame,
    "PathBuilder": PathBuilder,
    # gradients & patterns
    "grad_lin": grad_lin,
    "grad_rad": grad_rad,
    "grad_conic": grad_conic,
    "pattern": pattern,
    # effects
    "shadow": shadow,
    "glow": glow,
    "blur": blur,
    "reflect": reflect,
    "vignette": vignette,
    # repeat
    "repeat": repeat,
    "radial_repeat": radial_repeat,
    "scatter": scatter,
    # color
    "lighten": lighten,
    "darken": darken,
    "mix": mix,
    "hsl": hsl,
    "palette_lerp": palette_lerp,
    # transforms
    "group": group,
    "transform": transform,
    "rotate": rotate,
    "scale": scale,
    "mirror_x": mirror_x,
    "mirror_y": mirror_y,
    "opacity": opacity,
    "clip": clip,
    # palettes
    "PALETTE": PALETTE,
    "PALETTE_WARM": PALETTE_WARM,
    "PALETTE_COOL": PALETTE_COOL,
    "PALETTE_MONO": PALETTE_MONO,
    # utils
    "lerp": lerp,
    "polar": polar,
    "math": math,
    "random": random,
}
