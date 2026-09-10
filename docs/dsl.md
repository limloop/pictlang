# The pictlang drawing DSL

<details>
<summary>🇷🇺 Русский</summary>

# DSL для рисования в pictlang

`pictlang` не просит модель писать SVG напрямую. Вместо этого модель
пишет Python-функцию `render()`, которая использует небольшой DSL
для рисования. Этот документ — справочник по этому DSL.

## Зачем нужен DSL?

Писать SVG напрямую — многословно, чревато ошибками и тратит токены.
Сравните:

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512">
  <circle cx="256" cy="256" r="80" fill="#ff2a6d"/>
  <circle cx="256" cy="256" r="40" fill="#05d9e8"/>
</svg>
```

```python
def render():
    c = new_canvas(512, 512)
    add(c, circle(256, 256, 80, fill="#ff2a6d"))
    add(c, circle(256, 256, 40, fill="#05d9e8"))
    return to_svg(c)
```

Версия на DSL:

- примерно в 3 раза короче по токенам;
- использует циклы, функции и арифметику вместо повторения координат;
- проверяется до запуска (никаких импортов, никаких side effects);
- исполняется в песочнице (таймаут, лимит памяти, изолированный процесс);
- по построению даёт валидный SVG — невозможно сломать тег.

## Как работает render()

Модель пишет ровно это:

```python
def render():
    ...
    return to_svg(canvas)
```

Правила:

- Без аргументов.
- Без импортов. Всё уже в области видимости.
- Ничего на верхнем уровне.
- Возвращает `str` с валидным SVG-документом.
- Должна завершиться за несколько секунд.

Если любое из этих правил нарушено, код отклоняется **до**
исполнения. Полная модель валидации и песочницы — в
`docs/architecture.md`.

## Canvas

```python
new_canvas(width=512, height=512) -> Canvas
add(canvas, element) -> None
to_svg(canvas) -> str
bg(canvas, color_or_gradient) -> None
```

- `new_canvas` создаёт новый canvas.
- `add` принимает один элемент, список элементов, gradient или pattern.
- `to_svg` сериализует canvas в строку.
- `bg` — сокращение для заливки всего canvas сплошным цветом или gradient.

## Примитивы

Все примитивы возвращают элемент, который вы `add()` на canvas.

```python
rect(x, y, w, h, fill=None, stroke=None, sw=0, rx=0)
circle(cx, cy, r, fill=None, stroke=None, sw=0)
ellipse(cx, cy, rx, ry, fill=None, stroke=None, sw=0)
line(x1, y1, x2, y2, stroke, sw=1)
polygon(points, fill=None, stroke=None, sw=0)
polyline(points, stroke, sw=1, fill=None)
path(d, fill=None, stroke=None, sw=0)
arc(cx, cy, r, a0, a1, stroke, sw=1)
star(cx, cy, r_out, r_in, points=5, fill=None, stroke=None, sw=0)
ring(cx, cy, r, w, fill=None, stroke=None)
grid(x, y, w, h, cols, rows, fill=None, stroke=None, sw=1)
text(x, y, s, size=16, fill="#000", family="sans-serif", anchor="middle")
```

Замечания:

- `fill=None` означает «не заливать». `stroke=None` — «не обводить».
- `sw` — толщина обводки (stroke width).
- `points` — список кортежей `(x, y)`.
- `d` — строка SVG path, например `"M 10 10 L 20 20 Z"`.
- У `arc` углы в градусах, `0` указывает вправо, положительное
  направление — по часовой стрелке (соглашение SVG).
- `star` чередует `r_out` и `r_in`.
- `ring` — это окружность с обводкой и без заливки.

## Текст

```python
text(x, y, s, size=16, fill="#000", family="sans-serif", anchor="middle")
```

`text` рисует одну строку текста. Параметры:

- `x`, `y` — позиция. Интерпретация зависит от `anchor`:
  - `"start"` — `x` это левый край текста;
  - `"middle"` — `x` это центр текста;
  - `"end"` — `x` это правый край.
  `y` — baseline, а не верх и не центр строки.
- `s` — сама строка.
- `size` — размер шрифта в пикселях.
- `family` — CSS font-family. Значение по умолчанию `"sans-serif"`
  безопасно: оно есть везде.
- `anchor` — выравнивание по горизонтали.

```python
def render():
    c = new_canvas(512, 512)
    bg(c, "#f5f5f0")
    add(c, text(256, 256, "HELLO", size=64, fill="#1a1a1a"))
    return to_svg(c)
```

**Замечания:**

- **Шрифты.** Используйте только обобщённые семейства: `sans-serif`,
  `serif`, `monospace`. Конкретные шрифты (`Helvetica`, `Roboto`)
  могут отсутствовать у зрителя, и рендер изменится.
- **Кириллица и Unicode.** Работают, если шрифт их поддерживает.
  `sans-serif` обычно покрывает основные алфавиты.
- **Baseline, а не центр.** `y` — это baseline. Чтобы визуально
  центрировать строку по вертикали, добавьте примерно `size * 0.35`
  к желаемому центру.
- **Никаких переносов.** `text` рисует одну строку. Для нескольких
  строк вызывайте `text` несколько раз с разными `y`.
- **Для декоративных надписей** (постеры, обложки) текст работает
  хорошо. Для длинных абзацев — плохо: нет автоматической разметки,
  нет переносов, легко получить обрезку.

## Кривые и органические формы

```python
smooth(points, closed=False) -> str
blob(cx, cy, r, wobble=0.2, points=12, fill=None, stroke=None, sw=0, seed=None)
wave(x0, y0, x1, y1, amp=20, periods=3, fill=None, stroke=None, sw=2, steps=40)
flame(cx, cy, w, h, fill=None, stroke=None, sw=0, flip=False)
PathBuilder()
```

`smooth` возвращает строку path, а не элемент. Используйте её
внутри `path()`:

```python
d = smooth([(100, 100), (200, 80), (300, 120), (400, 100)])
add(c, path(d, stroke="#000", sw=2))
```

`blob` создаёт органическую округлую форму — полезно для облаков,
кустов, камней.

`wave` создаёт синусоиду между двумя точками.

`flame` создаёт каплевидную форму, направленную вверх (или вниз,
если `flip=True`).

`PathBuilder` собирает path постепенно:

```python
p = PathBuilder()
p.move(100, 100).line(200, 200).curve(250, 250, 300, 200, 350, 150).close()
add(c, path(p.d(), fill="#ccc"))
```

## Gradients и patterns

```python
grad_lin(stops, angle=0) -> Gradient
grad_rad(stops, cx=0.5, cy=0.5, r=0.5) -> Gradient
grad_conic(stops, cx=0.5, cy=0.5) -> Gradient
pattern(element, width, height) -> Pattern
```

- `stops` — список пар `(offset, color)`, где offset от `0` до `1`.
- `angle` в `grad_lin` в градусах: `0` = слева → направо,
  `90` = сверху → вниз.
- `cx`, `cy`, `r` относительны bounding box элемента, который они
  заливают.

**Важно:** gradient нужно добавить на canvas **до** того, как его
использовать:

```python
sky = grad_lin([(0, "#1a2a4a"), (1, "#4a6a9a")], angle=90)
add(c, sky)
add(c, rect(0, 0, 512, 512, fill=sky))
```

`pattern` тайлит элемент как заливку. То же правило: сначала `add`.

## Эффекты

Эффекты оборачивают элемент и возвращают новый элемент с
применённым SVG filter.

```python
shadow(el, dx=4, dy=4, blur=6, color="#000", opacity=0.3)
glow(el, blur=8, color="#fff", opacity=0.8)
blur(el, amount=4)
reflect(el, axis="x", origin=256, fade=0.4)
vignette(canvas, strength=0.5, color="#000")
```

- `shadow` добавляет drop shadow.
- `glow` добавляет внешнее свечение (хорошо для neon, ламп, магии).
- `blur` применяет Gaussian blur.
- `reflect` зеркалит элемент с затуханием — полезно для отражений
  в воде.
- `vignette` затемняет края canvas; вызывайте один раз, в конце.

**Замечание о производительности:** фильтры дорогие. Используйте их
умеренно, особенно `glow` и `blur`. Несколько обёрнутых элементов —
нормально; сотни — замедлят рендер и раздуют размер SVG.

## Помощники повтора

```python
repeat(el, count, dx=0, dy=0)
radial_repeat(el, count, cx, cy)
scatter(el, count, area=(x, y, w, h), seed=0)
```

- `repeat` размещает `count` копий, каждая со смещением `(dx, dy)`.
- `radial_repeat` размещает `count` копий, равномерно повёрнутых
  вокруг `(cx, cy)`.
- `scatter` размещает `count` копий в случайных позициях внутри `area`.

`scatter` использует seeded RNG, так что один и тот же `seed` даёт
тот же результат. Меняйте seed, чтобы получить другое расположение.

## Помощники цвета

```python
lighten(color, amount) -> str
darken(color, amount) -> str
mix(c1, c2, t) -> str
hsl(h, s, l) -> str
palette_lerp(t, palette=None) -> str
```

- `lighten` / `darken` смешивают с белым / чёрным. `amount` от `0` до `1`.
- `mix` линейно смешивает два цвета. `t=0` даёт `c1`, `t=1` даёт `c2`.
- `hsl` строит цвет из hue (градусы), saturation и lightness (`0..1`).
- `palette_lerp` возвращает цвет, выбранный вдоль палитры. `t` от `0` до `1`.

Доступные палитры:

```python
PALETTE        # тёмная, нейтральная, с акцентами hot pink и cyan
PALETTE_WARM   # тёплые коричневые, оранжевые, кремовые
PALETTE_COOL   # холодные синие, от почти чёрного до почти белого
PALETTE_MONO   # оттенки серого
```

Каждая — список из 5 hex-строк.

## Трансформации

```python
group(children, translate=(0, 0), rotate=0, scale=1, origin=None)
transform(el, translate=(0, 0), rotate=0, scale=1)
rotate(el, angle, cx=None, cy=None)
scale(el, factor, cx=None, cy=None)
mirror_x(el, axis)
mirror_y(el, axis)
opacity(el, value)
clip(el, mask_el)
```

- `group` оборачивает список детей с трансформацией.
- `transform`, `rotate`, `scale` — сокращения для одного элемента.
- `origin=(cx, cy)` заставляет поворот и масштабирование происходить
  вокруг этой точки.
- `mirror_x` / `mirror_y` отражают относительно вертикальной /
  горизонтальной оси.
- `opacity` задаёт прозрачность `0..1` элементу (и его детям).
- `clip` обрезает элемент по форме другого элемента.

## Утилиты

```python
polar(cx, cy, r, angle_deg) -> (x, y)
lerp(a, b, t)
math, random
```

- `polar` переводит полярные координаты в декартовы. Полезно вместе
  с циклами для радиальных узоров.
- `lerp` — линейная интерполяция.
- `math` и `random` — стандартные модули. `random` засеян pipeline'ом,
  так что результаты воспроизводимы между запусками с тем же входом.

## Рецепты

Несколько коротких паттернов, которые встречаются часто.

### Радиальный всплеск

```python
def render():
    c = new_canvas(512, 512)
    bg(c, "#0d0221")
    for i in range(24):
        x, y = polar(256, 256, 300, i * 15)
        add(c, line(256, 256, x, y, stroke="#05d9e8", sw=1))
    add(c, circle(256, 256, 40, fill="#ff2a6d"))
    return to_svg(c)
```

### Слоистый пейзаж

```python
def render():
    c = new_canvas(512, 512)
    sky = grad_lin([(0, "#f2b950"), (1, "#2b1a12")], angle=90)
    add(c, sky)
    bg(c, sky)
    for i, y in enumerate([300, 340, 380, 420]):
        shade = darken("#7a2e1a", i * 0.15)
        add(c, blob(256, y, 200, wobble=0.15, fill=shade, seed=i))
    return to_svg(c)
```

### Светящаяся сфера

```python
def render():
    c = new_canvas(512, 512)
    bg(c, "#0a0a0a")
    orb = circle(256, 256, 60, fill="#05d9e8")
    add(c, glow(orb, blur=20, color="#05d9e8", opacity=0.9))
    add(c, orb)
    return to_svg(c)
```

## Подводные камни

- **Всегда делайте `add()` для gradients и patterns перед тем, как
  использовать их как fill.** Иначе SVG будет содержать `url(#lg1)`
  без соответствующего определения.

- **`smooth` возвращает строку**, не элемент. Оборачивайте в `path()`.

- **Фильтры (`glow`, `shadow`, `blur`) дорогие.** Несколько — нормально;
  сотни — замедлят работу и раздуют размер SVG.

- **`render()` не должна импортировать ничего.** `math`, `random` и
  все функции DSL уже в области видимости.

- **Canvas не обрезается.** Элементы за пределами `0..512`
  рендерятся, но могут быть обрезаны просмотрщиком. Используйте
  `clip()`, если нужна жёсткая граница.

- **Никаких `while True`.** Песочница убивает процесс через несколько
  секунд.

</details>

---

<details open>
<summary>🇬🇧 English</summary>

# The pictlang drawing DSL

`pictlang` does not ask the model to write SVG directly. Instead, the
model writes a Python function `render()` that uses a small
drawing DSL. This document is the reference for that DSL.

## Why a DSL?

Writing SVG directly is verbose, error-prone, and wastes tokens.
Compare:

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512">
  <circle cx="256" cy="256" r="80" fill="#ff2a6d"/>
  <circle cx="256" cy="256" r="40" fill="#05d9e8"/>
</svg>
```

```python
def render():
    c = new_canvas(512, 512)
    add(c, circle(256, 256, 80, fill="#ff2a6d"))
    add(c, circle(256, 256, 40, fill="#05d9e8"))
    return to_svg(c)
```

The DSL version:

- is ~3x shorter in tokens;
- uses loops, functions, and arithmetic instead of repeated coordinates;
- is validated before it runs (no imports, no side effects);
- is sandboxed (timeout, memory limit, isolated process);
- produces valid SVG by construction — no risk of malformed tags.

## How render() works

The model writes exactly this:

```python
def render():
    ...
    return to_svg(canvas)
```

Rules:

- No arguments.
- No imports. Everything is already in scope.
- Nothing at the top level.
- Returns a `str` with a valid SVG document.
- Must finish in a few seconds.

If any of these rules is violated, the code is rejected before
execution. See `docs/architecture.md` for the full validation and
sandbox model.

## Canvas

```python
new_canvas(width=512, height=512) -> Canvas
add(canvas, element) -> None
to_svg(canvas) -> str
bg(canvas, color_or_gradient) -> None
```

- `new_canvas` creates a fresh canvas.
- `add` accepts a single element, a list of elements, a gradient, or a pattern.
- `to_svg` serializes the canvas to a string.
- `bg` is shorthand for filling the whole canvas with a solid color or gradient.

## Primitives

All primitives return an element that you `add()` to the canvas.

```python
rect(x, y, w, h, fill=None, stroke=None, sw=0, rx=0)
circle(cx, cy, r, fill=None, stroke=None, sw=0)
ellipse(cx, cy, rx, ry, fill=None, stroke=None, sw=0)
line(x1, y1, x2, y2, stroke, sw=1)
polygon(points, fill=None, stroke=None, sw=0)
polyline(points, stroke, sw=1, fill=None)
path(d, fill=None, stroke=None, sw=0)
arc(cx, cy, r, a0, a1, stroke, sw=1)
star(cx, cy, r_out, r_in, points=5, fill=None, stroke=None, sw=0)
ring(cx, cy, r, w, fill=None, stroke=None)
grid(x, y, w, h, cols, rows, fill=None, stroke=None, sw=1)
text(x, y, s, size=16, fill="#000", family="sans-serif", anchor="middle")
```

Notes:

- `fill=None` means "no fill". `stroke=None` means "no stroke".
- `sw` is stroke width.
- `points` is a list of `(x, y)` tuples.
- `d` is an SVG path string like `"M 10 10 L 20 20 Z"`.
- `arc` angles are in degrees, `0` points to the right, positive goes clockwise (SVG convention).
- `star` alternates between `r_out` and `r_in`.
- `ring` is a stroked circle with no fill.

## Text

```python
text(x, y, s, size=16, fill="#000", family="sans-serif", anchor="middle")
```

`text` draws a single line of text. Parameters:

- `x`, `y` — position. Interpretation depends on `anchor`:
  - `"start"` — `x` is the left edge of the text;
  - `"middle"` — `x` is the center of the text;
  - `"end"` — `x` is the right edge.
  `y` is the baseline, not the top or the center of the line.
- `s` — the string itself.
- `size` — font size in pixels.
- `family` — CSS font-family. The default `"sans-serif"` is safe:
  it is available everywhere.
- `anchor` — horizontal alignment.

```python
def render():
    c = new_canvas(512, 512)
    bg(c, "#f5f5f0")
    add(c, text(256, 256, "HELLO", size=64, fill="#1a1a1a"))
    return to_svg(c)
```

**Notes:**

- **Fonts.** Use only generic families: `sans-serif`, `serif`,
  `monospace`. Specific fonts (`Helvetica`, `Roboto`) may be missing
  on the viewer's machine, and the render will change.
- **Cyrillic and Unicode.** Work if the font supports them.
  `sans-serif` usually covers the common alphabets.
- **Baseline, not center.** `y` is the baseline. To visually center a
  line vertically, add roughly `size * 0.35` to the desired center.
- **No line breaks.** `text` draws one line. For multiple lines, call
  `text` several times with different `y`.
- **For decorative labels** (posters, covers) text works well. For long
  paragraphs it does not: there is no auto-layout, no wrapping, and
  easy overflow.

## Curves and organic shapes

```python
smooth(points, closed=False) -> str
blob(cx, cy, r, wobble=0.2, points=12, fill=None, stroke=None, sw=0, seed=None)
wave(x0, y0, x1, y1, amp=20, periods=3, fill=None, stroke=None, sw=2, steps=40)
flame(cx, cy, w, h, fill=None, stroke=None, sw=0, flip=False)
PathBuilder()
```

`smooth` returns a path string, not an element. Use it inside `path()`:

```python
d = smooth([(100, 100), (200, 80), (300, 120), (400, 100)])
add(c, path(d, stroke="#000", sw=2))
```

`blob` produces an organic roundish shape — useful for clouds, bushes, rocks.

`wave` produces a sine wave between two points.

`flame` produces a teardrop shape pointing up (or down if `flip=True`).

`PathBuilder` builds a path incrementally:

```python
p = PathBuilder()
p.move(100, 100).line(200, 200).curve(250, 250, 300, 200, 350, 150).close()
add(c, path(p.d(), fill="#ccc"))
```

## Gradients and patterns

```python
grad_lin(stops, angle=0) -> Gradient
grad_rad(stops, cx=0.5, cy=0.5, r=0.5) -> Gradient
grad_conic(stops, cx=0.5, cy=0.5) -> Gradient
pattern(element, width, height) -> Pattern
```

- `stops` is a list of `(offset, color)` pairs, where offset is `0..1`.
- `angle` in `grad_lin` is in degrees: `0` = left → right, `90` = top → bottom.
- `cx`, `cy`, `r` are relative to the bounding box of the element they fill.

**Important:** a gradient must be added to the canvas before it can be used:

```python
sky = grad_lin([(0, "#1a2a4a"), (1, "#4a6a9a")], angle=90)
add(c, sky)
add(c, rect(0, 0, 512, 512, fill=sky))
```

`pattern` tiles the element as a fill. Same rule: add it first.

## Effects

Effects wrap an element and return a new element with an SVG filter applied.

```python
shadow(el, dx=4, dy=4, blur=6, color="#000", opacity=0.3)
glow(el, blur=8, color="#fff", opacity=0.8)
blur(el, amount=4)
reflect(el, axis="x", origin=256, fade=0.4)
vignette(canvas, strength=0.5, color="#000")
```

- `shadow` adds a drop shadow.
- `glow` adds an outer glow (good for neon, lamps, magic).
- `blur` applies Gaussian blur.
- `reflect` mirrors the element with a fade — useful for water reflections.
- `vignette` darkens the canvas edges; call it once, at the end.

**Performance note:** filters are expensive. Use them sparingly,
especially `glow` and `blur`. A few wrapped elements are fine; hundreds
will slow down rendering and increase the SVG size.

## Repeat helpers

```python
repeat(el, count, dx=0, dy=0)
radial_repeat(el, count, cx, cy)
scatter(el, count, area=(x, y, w, h), seed=0)
```

- `repeat` places `count` copies, each offset by `(dx, dy)`.
- `radial_repeat` places `count` copies rotated evenly around `(cx, cy)`.
- `scatter` places `count` copies at random positions inside `area`.

`scatter` uses a seeded RNG, so the same `seed` gives the same result.
Change the seed to get a different arrangement.

## Color helpers

```python
lighten(color, amount) -> str
darken(color, amount) -> str
mix(c1, c2, t) -> str
hsl(h, s, l) -> str
palette_lerp(t, palette=None) -> str
```

- `lighten` / `darken` mix toward white / black. `amount` is `0..1`.
- `mix` linearly blends two colors. `t=0` gives `c1`, `t=1` gives `c2`.
- `hsl` builds a color from hue (degrees), saturation and lightness (`0..1`).
- `palette_lerp` returns a color sampled along a palette. `t` is `0..1`.

Available palettes:

```python
PALETTE        # dark, neutral, with a hot pink and cyan accent
PALETTE_WARM   # warm browns, oranges, cream
PALETTE_COOL   # cool blues, from near-black to near-white
PALETTE_MONO   # grayscale
```

Each is a list of 5 hex strings.

## Transforms

```python
group(children, translate=(0, 0), rotate=0, scale=1, origin=None)
transform(el, translate=(0, 0), rotate=0, scale=1)
rotate(el, angle, cx=None, cy=None)
scale(el, factor, cx=None, cy=None)
mirror_x(el, axis)
mirror_y(el, axis)
opacity(el, value)
clip(el, mask_el)
```

- `group` wraps a list of children with a transform.
- `transform`, `rotate`, `scale` are shorthands for one element.
- `origin=(cx, cy)` makes rotation and scaling happen around that point.
- `mirror_x` / `mirror_y` reflect across a vertical / horizontal axis.
- `opacity` sets `0..1` transparency on an element (and its children).
- `clip` clips the element by another element's shape.

## Utilities

```python
polar(cx, cy, r, angle_deg) -> (x, y)
lerp(a, b, t)
math, random
```

- `polar` converts polar coordinates to Cartesian. Useful together with
  loops for radial patterns.
- `lerp` is linear interpolation.
- `math` and `random` are the standard modules. `random` is seeded by
  the pipeline, so results are reproducible across runs with the same input.

## Recipes

A few short patterns that show up often.

### Radial burst

```python
def render():
    c = new_canvas(512, 512)
    bg(c, "#0d0221")
    for i in range(24):
        x, y = polar(256, 256, 300, i * 15)
        add(c, line(256, 256, x, y, stroke="#05d9e8", sw=1))
    add(c, circle(256, 256, 40, fill="#ff2a6d"))
    return to_svg(c)
```

### Layered landscape

```python
def render():
    c = new_canvas(512, 512)
    sky = grad_lin([(0, "#f2b950"), (1, "#2b1a12")], angle=90)
    add(c, sky)
    bg(c, sky)
    for i, y in enumerate([300, 340, 380, 420]):
        shade = darken("#7a2e1a", i * 0.15)
        add(c, blob(256, y, 200, wobble=0.15, fill=shade, seed=i))
    return to_svg(c)
```

### Glowing orb

```python
def render():
    c = new_canvas(512, 512)
    bg(c, "#0a0a0a")
    orb = circle(256, 256, 60, fill="#05d9e8")
    add(c, glow(orb, blur=20, color="#05d9e8", opacity=0.9))
    add(c, orb)
    return to_svg(c)
```

## Gotchas

- **Always `add()` gradients and patterns before using them as fills.**
  Otherwise the SVG will contain `url(#lg1)` with no matching definition.

- **`smooth` returns a string**, not an element. Wrap it in `path()`.

- **Filters (`glow`, `shadow`, `blur`) are expensive.** A handful is
  fine; hundreds will slow things down and blow up the SVG size.

- **`render()` must not import anything.** `math`, `random`, and every
  DSL function are already in scope.

- **The canvas is not clipped.** Elements outside `0..512` are rendered
  but may be cut off by the viewer. Use `clip()` if you need a hard
  boundary.

- **No `while True`.** The sandbox kills the process after a few seconds.

</details>