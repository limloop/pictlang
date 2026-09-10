# Architecture

<details>
<summary>🇷🇺 Русский</summary>

# Архитектура

`pictlang` превращает пару `(theme, style)` в SVG-файл за семь шагов.
Этот документ объясняет, что происходит на каждом шаге и почему.

## Pipeline

```
    theme + style
         │
         ▼
    ┌──────────┐
    │  prompt  │  загрузить шаблон, подставить {THEME} и {STYLE}
    └────┬─────┘
         │
         ▼
    ┌──────────┐
    │   api    │  отправить на OpenAI-совместимый endpoint
    └────┬─────┘
         │  сырой текст (может быть обёрнут в ```python)
         ▼
    ┌──────────┐
    │ cleanup  │  убрать markdown-обёртки
    └────┬─────┘
         │  python-исходник
         ▼
    ┌──────────┐
    │validator │  AST-проверка: ровно один render(), без импортов
    └────┬─────┘
         │
         ▼
    ┌──────────┐
    │ sandbox  │  запуск в subprocess с таймаутом и лимитом памяти
    └────┬─────┘
         │  str — SVG-документ
         ▼
    ┌──────────┐
    │validator │  парсинг как XML, проверка <svg>, размера
    └────┬─────┘
         │
         ▼
    ┌──────────┐
    │optimizer │  опционально: scour или svgo
    └────┬─────┘
         │
         ▼
    ┌──────────┐
    │ storage  │  записать .py, .svg, .json под UUID
    └──────────┘
```

Оркестратор — `pictlang.pipeline.generate()`. Он никогда не бросает
исключение на ошибках модели или валидации — возвращает
`GenerateResult` со `status="invalid"` и причиной. Ошибки
программиста (плохой конфиг, отсутствующие файлы) всё ещё
пробрасываются.

## Зачем DSL?

Модель не пишет SVG напрямую. Она пишет Python-функцию `render()`,
которая использует небольшой DSL для рисования. Полный справочник —
в `docs/dsl.md`.

Три причины:

1. **Экономия токенов.** Сцена, выраженная в DSL, в 15–30 раз
   короче той же сцены в чистом SVG. Циклы и функции сворачивают
   сотни повторяющихся элементов в несколько строк.

2. **Валидация до исполнения.** DSL фиксирует форму вывода. Мы
   можем проверить AST на «ровно один `render()`, без импортов, без
   side effects» — до того, как что-то запустится.

3. **Безопасность.** DSL — закрытый набор функций. Модель не может
   выдать `<script>`, внешние ссылки или произвольный доступ к
   файлам. Поверхность атаки намного меньше, чем у чистого SVG.

## Зачем песочница?

Код, сгенерированный моделью, недоверенный. Даже если сам DSL
безопасен, Python-код вокруг него в принципе может содержать
`while True` или пожиратель памяти. Песочница обеспечивает:

- **Отдельный процесс.** Код запускается в дочернем процессе с
  `python -I` (изолированный режим, без `PYTHONPATH`, без
  user site-packages).

- **Wall-clock таймаут.** По умолчанию 10 секунд. Процесс
  убивается, если превысил.

- **Лимит памяти.** По умолчанию 512 МБ. Обеспечивается через
  `resource.setrlimit` на POSIX; игнорируется на Windows.

- **Лимит CPU-времени.** Чуть выше wall-clock таймаута, как
  вторая линия защиты.

- **Инъекция DSL.** Дочерний процесс импортирует `pictlang.dsl` и
  передаёт `DSL_EXPORTS` как globals для `exec`. Render-код видит
  только эти имена.

## Зачем UUID?

Каждый запуск получает свежий UUID4. `.py`, `.svg` и `.json` этого
запуска делят один UUID, так что вы можете найти их позже.

UUID печатается в stdout в конце запуска. Сохраните эту строку,
если хотите найти файлы позже.

Два запуска с одной и той же парой `(theme, style)` получают
**разные UUID**. Это намеренно: модель стохастична, и каждый запуск —
новый результат. Если нужна воспроизводимость, зафиксируйте модель
и поставьте `temperature=0`.

## Структура вывода

```
generated/
├── valid/
│   ├── py/<uuid>.py
│   ├── svg/<uuid>.svg
│   ├── svg/<uuid>.original.svg   (при --keep-original)
│   └── meta/<uuid>.json
├── invalid/
│   ├── <uuid>.py                 (только с --save all)
│   └── <uuid>.json
└── manifest.jsonl
```

`valid/py`, `valid/svg` и `valid/meta` разделены, чтобы большое
количество результатов не засоряло одну директорию.

`invalid/` заполняется только при `--save all`. Это отладочный
помощник, а не часть нормального workflow.

`manifest.jsonl` — append-only лог: один JSON-объект на строку,
одна строка на запуск. Его безопасно удалить; во время работы
ничего из него не читается.

## Режимы сохранения

Флаг `--save` управляет тем, что сохраняется:

| Режим   | `.py` | `.svg` | `.json` | invalid | optimizer |
|---------|:-----:|:------:|:-------:|:-------:|:---------:|
| `valid` |  да   |  да    |   да    |   нет   |    да     |
| `all`   |  да   |  да    |   да    |   да    |    да     |
| `py`    |  да   |  нет   |   нет   |   нет   |    нет    |
| `svg`   |  нет  |  да    |   нет   |   нет   |    да     |

`valid` — по умолчанию.

Optimizer никогда не запускается в режиме `py` — нет SVG, который
оптимизировать. `--keep-original` игнорируется в режиме `py` по
той же причине.

## Optimizer

Опционален. Два backend:

- **scour** — чистый Python, `pip install scour`.
- **svgo** — Node.js-инструмент, должен быть в `PATH`.

`--optimizer auto` (по умолчанию) сначала пробует `scour`, потом
`svgo`. Если ни один не доступен, оригинальный SVG сохраняется,
а в stderr печатается заметка.

Optimizer никогда не бросает исключение. При любой ошибке
оригинальный SVG возвращается без изменений.

## Конфигурация

`pictlang` читает конфигурацию в порядке:

1. Путь из `--config`, если задан.
2. `./pictlang.json` в текущей директории.
3. Пользовательская директория конфига:
   - Linux: `~/.config/pictlang/config.json`
   - macOS: `~/Library/Application Support/pictlang/config.json`
   - Windows: `%APPDATA%\limloop\pictlang\config.json`
4. Встроенные значения по умолчанию.

Первое совпадение выигрывает. Флаги CLI переопределяют то, что
говорит конфиг.

Файл не создаётся автоматически. Используйте `pictlang init`
(проектный) или `pictlang init --global` (пользовательский), чтобы
записать шаблон.

</details>

---

<details open>
<summary>🇬🇧 English</summary>

# Architecture

`pictlang` turns a `(theme, style)` pair into an SVG file in seven
steps. This document explains what happens at each step and why.

## Pipeline

```
    theme + style
         │
         ▼
    ┌──────────┐
    │  prompt  │  load template, substitute {THEME} and {STYLE}
    └────┬─────┘
         │
         ▼
    ┌──────────┐
    │   api    │  send to an OpenAI-compatible endpoint
    └────┬─────┘
         │  raw text (may be wrapped in ```python fences)
         ▼
    ┌──────────┐
    │  cleanup │  strip markdown fences
    └────┬─────┘
         │  python source
         ▼
    ┌──────────┐
    │ validator│  AST check: exactly one render(), no imports
    └────┬─────┘
         │
         ▼
    ┌──────────┐
    │  sandbox │  run in a subprocess with timeout and memory limit
    └────┬─────┘
         │  str — the SVG document
         ▼
    ┌──────────┐
    │ validator│  parse as XML, check <svg>, check size
    └────┬─────┘
         │
         ▼
    ┌──────────┐
    │optimizer │  optional: scour or svgo
    └────┬─────┘
         │
         ▼
    ┌──────────┐
    │ storage  │  write .py, .svg, .json under a UUID
    └──────────┘
```

The orchestrator is `pictlang.pipeline.generate()`. It never raises on
model or validation errors — it returns a `GenerateResult` with
`status="invalid"` and a reason. Programmer errors (bad config, missing
files) still raise.

## Why a DSL?

The model does not write SVG directly. It writes a Python function
`render()` that uses a small drawing DSL. See `docs/dsl.md` for the
full reference.

Three reasons:

1. **Token efficiency.** A scene expressed in the DSL is 15–30×
   shorter than the same scene in raw SVG. Loops and functions
   collapse hundreds of repeated elements into a few lines.

2. **Validation before execution.** The DSL fixes the shape of the
   output. We can check the AST for exactly one `render()`, no
   imports, no side effects — before running anything.

3. **Safety.** The DSL is a closed set of functions. The model cannot
   emit `<script>`, external references, or arbitrary file access.
   The surface of attack is much smaller than with raw SVG.

## Why a sandbox?

Model-generated code is untrusted. Even though the DSL is safe, the
Python code around it could in principle contain a `while True` or a
memory bomb. The sandbox enforces:

- **Separate process.** Code runs in a child process with `python -I`
  (isolated mode, no `PYTHONPATH`, no user site-packages).

- **Wall-clock timeout.** Default 10 seconds. The process is killed
  if it exceeds this.

- **Memory limit.** Default 512 MB. Enforced via `resource.setrlimit`
  on POSIX; ignored on Windows.

- **CPU time limit.** Slightly higher than the wall-clock timeout, as
  a second line of defense.

- **DSL injection.** The child process imports `pictlang.dsl` and
  passes `DSL_EXPORTS` as the globals for `exec`. The render code
  sees only those names.

## Why UUIDs?

Every run gets a fresh UUID4. The `.py`, `.svg`, and `.json` for that
run share the same UUID, so you can find them later.

UUIDs are printed to stdout at the end of the run. Save that line if
you want to find the files later.

Two runs with the same `(theme, style)` get **different UUIDs**. This
is intentional: the model is stochastic, and each run is a new result.
If you want reproducible output, pin the model and set
`temperature=0`.

## Output layout

```
generated/
├── valid/
│   ├── py/<uuid>.py
│   ├── svg/<uuid>.svg
│   ├── svg/<uuid>.original.svg   (if --keep-original)
│   └── meta/<uuid>.json
├── invalid/
│   ├── <uuid>.py                 (only with --save all)
│   └── <uuid>.json
└── manifest.jsonl
```

`valid/py`, `valid/svg`, and `valid/meta` are split so that a large
number of results does not clutter a single directory.

`invalid/` is only populated when `--save all` is used. It is a debug
aid, not part of the normal workflow.

`manifest.jsonl` is an append-only log: one JSON object per line, one
line per run. It is safe to delete; nothing reads it at runtime.

## Save modes

The `--save` flag controls what gets persisted:

| Mode    | `.py` | `.svg` | `.json` | invalid | optimizer |
|---------|:-----:|:------:|:-------:|:-------:|:---------:|
| `valid` |  yes  |  yes   |   yes   |   no    |    yes    |
| `all`   |  yes  |  yes   |   yes   |   yes   |    yes    |
| `py`    |  yes  |   no   |   no    |   no    |    no     |
| `svg`   |  no   |  yes   |   no    |   no    |    yes    |

`valid` is the default.

The optimizer never runs in `py` mode — there is no SVG to optimize.
`--keep-original` is ignored in `py` mode for the same reason.

## Optimizer

Optional. Two backends:

- **scour** — pure Python, `pip install scour`.
- **svgo** — Node.js tool, must be on `PATH`.

The `--optimizer auto` (default) tries `scour` first, then `svgo`. If
neither is available, the original SVG is kept and a note is printed
on stderr.

The optimizer never raises. On any failure the original SVG is
returned unchanged.

## Configuration

`pictlang` reads configuration from, in order:

1. The `--config` path, if given.
2. `./pictlang.json` in the current directory.
3. The platform user-config directory:
   - Linux: `~/.config/pictlang/config.json`
   - macOS: `~/Library/Application Support/pictlang/config.json`
   - Windows: `%APPDATA%\limloop\pictlang\config.json`
4. Built-in defaults.

The first match wins. CLI flags override whatever the config says.

No file is created automatically. Use `pictlang init` (project) or
`pictlang init --global` (user) to write a template.

</details>