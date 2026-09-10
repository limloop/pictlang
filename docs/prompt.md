# Writing custom prompts

<details>
<summary>🇷🇺 Русский</summary>

# Как писать свои промпты

`pictlang` поставляется с промптом по умолчанию
(`pictlang/prompts/default.md`), который объясняет модели DSL и
просит написать функцию `render()`.

Вы можете заменить его через `--prompt-file path/to/your.md`.

## Формат

Шаблон промпта — это Markdown-файл с двумя опциональными секциями,
разделёнными строкой, содержащей только `---`:

```
Всё, что выше разделителя — system prompt.
Здесь описываются правила, доступные функции и ограничения.

---

Всё, что ниже — user prompt.
Он обязательно должен содержать {THEME} и {STYLE}.
```

Если `---` нет, весь файл становится user prompt'ом, а system
prompt пустой.

## Обязательные плейсхолдеры

User-секция должна содержать оба:

- `{THEME}` — подставляется значением аргумента theme.
- `{STYLE}` — подставляется значением `--style`.

Если хотя бы одного нет, `pictlang` отказывается запускаться
**до** любого запроса к API.

## Посторонние фигурные скобки

Шаблон форматируется через `str.format_map` с кастомным mapping,
который оставляет неизвестные плейсхолдеры как есть. Это значит,
что вы можете включать JSON-примеры или сниппеты кода с фигурными
скобками без экранирования:

```
Example response shape:
{"uuid": "...", "svg": "..."}

Theme: {THEME}
Style: {STYLE}
```

`{THEME}` и `{STYLE}` заменятся; `{"uuid": "..."}` не тронется.

## Что содержит промпт по умолчанию

Промпт по умолчанию — примерно 1500 токенов. В нём три части:

1. **Правила** — один верхнеуровневый `render()`, без импортов,
   без комментариев, возвращает `str`.
2. **Справочник по DSL** — каждая доступная функция и константа,
   сгруппированные по смыслу.
3. **Стилевые правила** — цвета, эффекты, размер canvas, бюджет
   времени на выполнение.

Справочник по DSL в промпте по умолчанию написан вручную и
синхронизируется с `pictlang/dsl.py`. Если вы добавляете новую
функцию в DSL, добавьте её и в промпт — иначе модель не узнает,
что она существует.

## Когда писать свой промпт

Большинству пользователей это не нужно. Промпт по умолчанию
работает с OpenAI, OpenRouter, LocalAI, Ollama и другими
OpenAI-совместимыми endpoints.

Пишите свой промпт, если хотите:

- ограничить DSL подмножеством (например, без фильтров, ради
  скорости);
- потребовать конкретную палитру или композицию;
- добавить стилевые инструкции («плоско, без градиентов»);
- подстроиться под модель, которой нужна другая формулировка.

## Пример: минимальный промпт

```markdown
You write a Python function render() that returns an SVG string.

Allowed functions: new_canvas, add, to_svg, rect, circle, path.
No imports. No comments.

---

Theme: {THEME}
Style: {STYLE}

Return only the code.
```

Этого достаточно для простых плоских иконок. Такой промпт даст
меньший SVG и более быстрый рендер, чем промпт по умолчанию, но
ценой выразительности.

## Пример: промпт с ограничением стиля

```markdown
You write a Python function render() that returns an SVG string.

Use only these colors: #0d0221, #ff2a6d, #05d9e8.
Use at most 12 elements on the canvas.
No gradients. No filters.

---

Theme: {THEME}
Style: {STYLE}

Return only the code.
```

Полезно, когда нужна консистентная серия изображений, например
набор постеров.

## Пример: промпт с композиционным правилом

```markdown
You write a Python function render() that returns an SVG string.

The canvas is 512x512.
Place the main subject in the lower third.
Leave the upper third mostly empty.
Use no more than three colors.

---

Theme: {THEME}
Style: {STYLE}

Return only the code.
```

Такое ограничение часто даёт более «спокойные» композиции, чем
промпт по умолчанию, который не диктует расположение.

## Частые ошибки

- **Забыли `{STYLE}`.** `pictlang` откажется запускаться. Это
  защита от опечаток.

- **Написали `{theme}` строчными.** Плейсхолдеры
  регистрозависимы. Нужно `{THEME}`.

- **Пытаетесь использовать `{{` для экранирования.** Не нужно.
  Кастомный mapping оставляет посторонние скобки как есть.

- **Пишете слишком абстрактный system prompt.** Модель не знает,
  какие функции ей доступны. Лучше явно перечислить DSL.

- **Даёте слишком много стилевых правил.** После ~10 строк
  ограничений модель начинает путаться. Держите список коротким.

</details>

---

<details open>
<summary>🇬🇧 English</summary>

# Writing custom prompts

`pictlang` ships with a default prompt (`pictlang/prompts/default.md`)
that explains the DSL to the model and asks for a `render()` function.

You can override it with `--prompt-file path/to/your.md`.

## Format

A prompt template is a Markdown file with two optional sections
separated by a line containing only `---`:

```
Everything above the separator is the system prompt.
It should describe rules, available functions, and constraints.

---

Everything below is the user prompt.
It must contain {THEME} and {STYLE}.
```

If there is no `---`, the whole file becomes the user prompt and the
system prompt is empty.

## Required placeholders

The user section must contain both:

- `{THEME}` — substituted with the value of the theme argument.
- `{STYLE}` — substituted with the value of `--style`.

If either is missing, `pictlang` refuses to run before making any API
call.

## Stray braces

The template is formatted with `str.format_map` and a custom mapping
that leaves unknown placeholders untouched. This means you can include
JSON examples or code snippets with braces without escaping them:

```
Example response shape:
{"uuid": "...", "svg": "..."}

Theme: {THEME}
Style: {STYLE}
```

`{THEME}` and `{STYLE}` will be replaced; `{"uuid": "..."}` will not be
touched.

## What the default prompt contains

The default prompt is roughly 1500 tokens. It has three parts:

1. **Rules** — one top-level `render()`, no imports, no comments,
   return `str`.
2. **DSL reference** — every available function and constant, grouped
   by purpose.
3. **Style rules** — colors, effects, canvas size, runtime budget.

The DSL reference in the default prompt is generated by hand and kept
in sync with `pictlang/dsl.py`. If you add a new function to the DSL,
add it to the prompt too — otherwise the model will not know it exists.

## When to write a custom prompt

Most users never need to. The default prompt works across OpenAI,
OpenRouter, LocalAI, Ollama, and other OpenAI-compatible endpoints.

Write a custom prompt if you want to:

- restrict the DSL to a subset (e.g. no filters, for speed);
- require a specific palette or composition;
- add style-specific instructions ("flat, no gradients");
- target a model that needs a different phrasing.

## Example: a minimal prompt

```markdown
You write a Python function render() that returns an SVG string.

Allowed functions: new_canvas, add, to_svg, rect, circle, path.
No imports. No comments.

---

Theme: {THEME}
Style: {STYLE}

Return only the code.
```

This is enough for simple, flat icons. It will produce smaller SVG
and faster renders than the default, at the cost of expressiveness.

## Example: a style-constrained prompt

```markdown
You write a Python function render() that returns an SVG string.

Use only these colors: #0d0221, #ff2a6d, #05d9e8.
Use at most 12 elements on the canvas.
No gradients. No filters.

---

Theme: {THEME}
Style: {STYLE}

Return only the code.
```

Useful when you want a consistent series of images, like a poster set.

## Example: a composition-constrained prompt

```markdown
You write a Python function render() that returns an SVG string.

The canvas is 512x512.
Place the main subject in the lower third.
Leave the upper third mostly empty.
Use no more than three colors.

---

Theme: {THEME}
Style: {STYLE}

Return only the code.
```

This kind of constraint often produces calmer compositions than the
default prompt, which does not dictate placement.

## Common mistakes

- **Forgetting `{STYLE}`.** `pictlang` refuses to run. This is a guard
  against typos.

- **Writing `{theme}` in lowercase.** Placeholders are case-sensitive.
  It must be `{THEME}`.

- **Trying to escape with `{{`.** Not needed. The custom mapping
  leaves unknown braces untouched.

- **Writing too abstract a system prompt.** The model does not know
  which functions are available. Better to list the DSL explicitly.

- **Giving too many style rules.** After roughly 10 lines of
  constraints the model starts to get confused. Keep the list short.

</details>