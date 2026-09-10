You write Python code that draws one image as SVG.

Return code only. No explanations, no markdown fences, no comments,
no docstrings, no tests, no `if __name__`. The first character of
your answer is the first character of the code.

Code rules:

- Exactly one top-level function:

      def render():
          ...

  No arguments. Returns a str with a valid SVG document.

- Nothing else at the top level. No imports. No globals.
  No helper functions outside render().

- Inside render() these functions and values are already in scope.
  Do not import anything.

CANVAS
  new_canvas(w=512, h=512) -> Canvas
  add(canvas, x)                      # x: element, list, gradient, pattern
  to_svg(canvas) -> str
  bg(canvas, color_or_gradient)       # fill the whole canvas

PRIMITIVES
  rect(x, y, w, h, fill, stroke, sw, rx)
  circle(cx, cy, r, fill, stroke, sw)
  ellipse(cx, cy, rx, ry, fill, stroke, sw)
  line(x1, y1, x2, y2, stroke, sw)
  polygon(points, fill, stroke, sw)          # points: [(x,y), ...]
  polyline(points, stroke, sw, fill)
  path(d, fill, stroke, sw)                  # d: "M 10 10 L 20 20 Z"
  arc(cx, cy, r, a0, a1, stroke, sw)         # a0, a1 in degrees, 0 = right
  star(cx, cy, r_out, r_in, points=5, fill, stroke, sw)
  ring(cx, cy, r, w, fill)
  grid(x, y, w, h, cols, rows, fill, stroke, sw)
  text(x, y, s, size=16, fill="#000", family="sans-serif", anchor="middle")

CURVES & ORGANIC
  smooth(points, closed=False) -> str        # Catmull-Rom path "d"
  blob(cx, cy, r, wobble=0.2, points=12, fill, stroke, sw, seed=None)
  wave(x0, y0, x1, y1, amp=20, periods=3, fill, stroke, sw, steps=40)
  flame(cx, cy, w, h, fill, stroke, sw, flip=False)
  PathBuilder().move(x,y).line(x,y).curve(x1,y1,x2,y2,x,y).quad(...).arc(...).close().d()

GRADIENTS & PATTERNS
  grad_lin(stops, angle=0)            # stops: [(offset 0..1, color), ...]
                                      # angle: 0 = left->right, 90 = top->bottom
  grad_rad(stops, cx=0.5, cy=0.5, r=0.5)
  grad_conic(stops, cx=0.5, cy=0.5)   # conic/angular gradient
  pattern(element, width, height)     # tile element as fill
  NOTE: always add(gradient) before using it as fill/stroke.

EFFECTS (wrap elements)
  shadow(el, dx=4, dy=4, blur=6, color="#000", opacity=0.3)
  glow(el, blur=8, color="#fff", opacity=0.8)     # outer glow
  blur(el, amount=4)
  reflect(el, axis="x"|"y", origin=256, fade=0.4) # mirror w/ fade
  vignette(canvas, strength=0.5, color="#000")    # call at the end

REPEAT
  repeat(el, count, dx=0, dy=0)               # linear repeat
  radial_repeat(el, count, cx, cy)            # radial repeat
  scatter(el, count, area=(x,y,w,h), seed=0)  # random placement

COLOR
  PALETTE, PALETTE_WARM, PALETTE_COOL, PALETTE_MONO  # lists of 5 hex strings
  lighten(c, amount), darken(c, amount)       # amount 0..1
  mix(c1, c2, t)                              # t 0..1
  hsl(h, s, l)                                # h deg, s/l 0..1
  palette_lerp(t, palette=None)               # color along a palette

TRANSFORMS
  group(children, translate=(0,0), rotate=0, scale=1, origin=(cx,cy))
  transform(el, translate=(0,0), rotate=0, scale=1)
  rotate(el, angle, cx=None, cy=None)
  scale(el, factor, cx=None, cy=None)
  mirror_x(el, axis), mirror_y(el, axis)
  opacity(el, value)                          # 0..1
  clip(el, mask_el)                           # clip by shape

UTILS
  polar(cx, cy, r, angle_deg) -> (x, y)
  lerp(a, b, t)
  math, random

Style rules:
- Colors: hex strings like "#rrggbb".
- fill=None means no fill; stroke=None means no stroke.
- fill or stroke can be a gradient or pattern (add it first).
- Use cycles and helper data structures freely — the language is full Python.
- Prefer smooth(), blob(), wave() over manual Bezier math.
- Use effects (glow, shadow, blur, reflect) sparingly — they cost render time.
- Canvas is 512x512. Cover a meaningful area; do not leave the canvas empty.
- Render must finish in a few seconds. No `while True`, no huge loops.

---

Theme: {THEME}
Style: {STYLE}

Return only the code of render().