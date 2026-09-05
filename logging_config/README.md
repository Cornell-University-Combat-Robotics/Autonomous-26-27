# logging_config

Repo-wide logging package. **Status: pseudocode skeleton — no executable code yet.**
Every `.py` file here is comments describing what the implementation should do and,
more importantly, *why*. Nothing imports this package yet.

Built on the **stdlib `logging`** module (see [Open decisions](#open-decisions) —
this conflicts with `STYLE_GUIDE.md`, which currently says loguru only).

## Why this exists

Three requirements drove the design:

1. A `TRACE` level below `DEBUG`, callable as a real method: `logger.trace(...)`.
2. Log destinations chosen by a **method call**, not a static config table.
3. On `TRACE`, the message is built from **where it was called** — the call site,
   the variables in scope there, and a handful of other per-record factors.

## File map

| File | Owns |
|---|---|
| `__init__.py` | Public surface, and the **import-order contract** that makes `.trace()` exist |
| `levels.py` | The `TRACE = 5` constant and `addLevelName` registration |
| `logger.py` | `TraceLogger(logging.Logger)` — the `.trace()` method and `makeRecord` override |
| `capture.py` | Frame walking, locals capture, safe repr, redaction. The risky one |
| `handlers.py` | `RoutingHandler` — destination resolved per record. Queue/rotation notes |
| `formatters.py` | Rendering the captured payload, human and JSON |
| `config.py` | `configure_logging()`, `parse_args()`, `get_logger()` |

## The shape of it

`get_logger(__name__)` is the only sanctioned way to obtain a logger. It returns a
`TraceLogger`, typed, so editors and type checkers see `.trace()`.

A trace call flows: **guard** (`isEnabledFor`, one integer compare when disabled) →
**capture** (`capture.py`, eager, stringified, redacted) → **emit** (`_log` with a
corrected `stacklevel`) → **route** (`handlers.py` picks the file) → **render**
(`formatters.py`).

Two invariants hold the whole thing together:

- **`trace()` stays dumb.** It builds a record. It does no I/O and knows nothing
  about destinations. That is what lets one call site behave differently per
  environment without editing the call site.
- **Capture is eager, rendering is lazy.** Values are turned into safe strings at
  the call site, never later. Frames die, values mutate, and with a `QueueListener`
  formatting happens on another thread minutes later.

## Landmines, in rough order of how fast they'll bite

- **`setLoggerClass` ordering.** `getLogger` caches by name. Any logger built before
  the class is registered is a plain `Logger` forever and `AttributeError`s on
  `.trace()`. The root logger *always* predates us and can never be a `TraceLogger`.
- **`stacklevel`.** Without correction every trace record reports `logger.py`'s own
  line number instead of the caller's. Add to a caller-supplied `stacklevel`, never
  overwrite. Test it by asserting `record.funcName`.
- **Handler levels are floors, not equality.** `TRACE` is the *lowest* level, so a
  handler set to `TRACE` receives everything in the system. Level-exact routing
  needs a `Filter`.
- **Root logger level gates before handlers see anything.** Root at `INFO` silently
  kills every `TRACE` no matter how the handlers are set up.
- **`repr()` is arbitrary user code** running inside a log call. It can raise, block,
  or dump a whole ndarray. Needs try/except, truncation, and type-aware summaries.
- **Locals are where credentials live.** Name-based redaction is a hard default.
  Trace logs still shouldn't be pasted publicly.

## Open decisions

These are real forks, not TODOs. Each needs a human call before implementation.

1. **Brace-form messages don't work on stdlib.** `STYLE_GUIDE.md` mandates
   `logger.debug("camera: frame {} captured", frame.frame_id)`. That is loguru
   syntax; stdlib does `msg % args` and renders the literal `{}` while **silently
   dropping the argument**. Options in `logger.py` → *BRACE-STYLE MESSAGES*. This
   one blocks everything else — every call site in the playground is written this way.
2. **stdlib vs loguru.** `STYLE_GUIDE.md` and `CLAUDE.md` both say loguru only, and
   the playground is entirely loguru. This package is stdlib. Either the style guide
   gets amended or the playground gets ported; right now the repo says both.
3. **Arguments or all locals?** Arguments (`co_varnames[:co_argcount]`) are bounded
   and stable. All of `f_locals` is unbounded and grows as the function runs, so the
   same trace line yields different fields depending where it sits.
4. **The "other factors" list.** `capture.py` §6 has candidates — `frame_id` via a
   `ContextVar` looks like the highest-value one for this pipeline. That list is a
   design conversation, not something to accept as written.
5. **Per-record routing, or resolved once?** If the destination depends only on the
   level, N plain `FileHandler`s with filters beat a custom `RoutingHandler`.
   `RoutingHandler` earns its keep only for per-run / per-match / per-frame paths.
6. **Multi-line trace output** reads much better and breaks line-oriented grep.
7. **Is `TRACE` ever on outside dev?** If it can be flipped on in the field, the
   capture cost budget gets much tighter and `QueueHandler` stops being optional.

## Working on this

There is nothing to run yet — the package is comments. What you *can* do:

```
uv sync                                    # root project venv
uv run ruff check logging_config/          # passes trivially; keep it that way
uv run ruff format --check --diff .        # preview formatting, writes nothing
```

Reference implementation to read before writing any of this — the loguru version of
the same job, including the per-service `log_config.toml` discovery this package
should copy:

```
aaron-sysdesign-playground/logging_config/logging_config.py
aaron-sysdesign-playground/logging_config/README.md
```

Suggested implementation order, because each step is testable alone:

1. `levels.py` + `__init__.py` registration → assert `logging.getLevelName(5) == "TRACE"`
2. `logger.py` `.trace()` with the guard and `stacklevel` → assert `record.funcName`
3. `formatters.py` human formatter → eyeball the output
4. `handlers.py` resolved-once handlers with `ExactLevel` filters → check files land right
5. `capture.py` → arguments only, then safe_repr, then redaction, then the extras
6. `handlers.py` `RoutingHandler` + `QueueHandler`, only if steps 4–5 prove insufficient

Per `CLAUDE.md`, `tests/` at the repo root is the expected home for tests. There is
no test runner configured yet — step 2 above is a good reason to add one.

## Note on the old `logging.py`

The repo root previously held a `logging.py`. Under the folder-per-service pattern
the project root is on `sys.path`, so that filename **shadowed the stdlib `logging`
module** for every import in the repo — including `logging`'s own consumers. It also
imported itself. Its intent is absorbed here. It has been moved to `_to_delete/` and
should be deleted.
