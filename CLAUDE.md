# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

Cornell Combat Robotics autonomous subteam, 2026-2027. The team is doing a system-design
overhaul, so this repo is mid-rewrite:

- **Root** (`pyproject.toml`, `src/autonomous_26_27/`) — a near-empty uv package skeleton for the
  real 2026-27 codebase. It holds the authoritative `[tool.ruff]` config and a `main()` stub.
- **`aaron-sysdesign-playground/`** — a **separate uv project** (own `pyproject.toml`, own
  `uv.lock`, own `.venv`) that is the working reference architecture for that rewrite: a mock
  camera → object detection → algorithm pipeline plus real, working `warp/` and `scripts/` code.
  Read it end to end before adding structure to the root project; new services should follow its
  patterns.
- `STYLE_GUIDE.md` at the root is binding for all code in the repo (see "Conventions" below).
- `main` currently contains only `README.md`/`.gitignore`; the code lives on `develop` and feature
  branches. There are no tests and no CI yet.

Because the two projects are independent uv environments, **run commands from the directory that
owns the code you're touching** — `uv run` at the root resolves the root venv, which has only ruff.

## Git

Claude must not run any git commands (`git add`, `commit`, `push`, `branch`, `checkout`, `merge`,
`rebase`, `reset`, etc.) or use GitHub tooling (`gh`) on this repo unless the user explicitly asks
for that specific action in that turn. Making code changes is not implicit permission to commit or
push them — leave changes unstaged/uncommitted and say so, and let the user decide when to commit.

## Commands

Root project:

```
uv sync                                # create/refresh .venv from pyproject.toml + uv.lock
uv run ruff check .                    # lint (authoritative config lives in root pyproject.toml)
uv run ruff format .                   # format; ruff format is authoritative, never hand-format
uv run ruff check --fix .
uv run ruff format --check --diff .    # preview formatting without writing
```

Playground project (`cd aaron-sysdesign-playground` first):

```
uv sync
uv run main.py                         # run the mock pipeline
uv run main.py --trace                 # see logging CLI flags below
uv run viztracer main.py               # profile a run
uv run vizviewer result.json           # view the profile
```

Playground utility scripts (all from `aaron-sysdesign-playground/`):

```
uv run scripts/download_videos.py [--dir huey]   # pull testing videos from the team's Box folder
uv run scripts/upload_videos.py   [--dir huey]   # push new local testing videos to Box
uv run scripts/warp_video.py                     # warp one video (set VIDEO_URL at top of file)
uv run scripts/brettzone_frames.py [--upload|--dry-run|--recalibrate|--robot huey|--redo KEY]
uv run scripts/upload_frames.py [--batch-name NAME|--dry-run]
```

Videos live in the team's Box folder (mounted by Box Drive), not git; override the location with
`BOX_VIDEOS_DIR` if auto-detection fails. `videos/`, `frames/`, and `logs/` are gitignored.

There is no test runner configured yet. `pyproject.toml` already carries `tests/**` ruff
per-file-ignores, so `tests/` at the root is the expected home when tests are added.

## Architecture (the playground pattern)

**Folder-per-service, imported from the repo root.** Each pipeline stage is `<name>/<name>.py` +
`<name>/__init__.py` (re-exports the public class) + `<name>/README.md` + optionally
`<name>/log_config.toml`. `main.py` sits at the project root, so the root is on `sys.path` and any
module can `from camera import Camera`. Deliberately *not* used: `sys.path.append` hacks, or uv
workspace editable packages (this ships as one app, not separately versioned libraries).

**Orchestrator pattern.** `main.py` is the only place services are wired together. Services never
call each other in the hot loop — `main` constructs everything once up front, then passes each
stage's output to the next. Each service exposes exactly one hot-path method (`camera.read()`,
`detector.detect(frame)`, `algorithm.decide(result)`) plus read-only `@property` state accessors
over private `_`-prefixed attributes. That makes a service testable alone: build its input
dataclass, call the one method, check the output.

**Messages are `datatypes/` dataclasses.** `Frame` → `DetectionResult` etc. are
`@dataclass(slots=True)`, each produced by exactly one owning service and never mutated
downstream. `frame_id` is carried through every stage so results stay traceable to their frame.
Add new inter-service message types here rather than passing dicts or tuples.

**Logging is auto-discovered (playground implementation).** `logging_config/` configures loguru
process-wide for the playground specifically; entry points call `configure_logging(parse_args())`
once and every other module just does `from loguru import logger`. `_discover_services()` scans
the project root for folders containing `log_config.toml` (`console = "INFO"` / `logfile =
"INFO"`), and each one gets its own `logs/<service>.log` plus everything into `logs/main.log`.
Adding a service needs no edits to `logging_config.py`. CLI flags (`--no-logs`, `--debug`,
`--trace`, `--console LEVEL`, `--logfile LEVEL`, `--clear-logs`, `--simple-logs`) override the
per-service files; the first four are mutually exclusive.
See `logging_config/README.md` for the full design. loguru is this playground project's own
choice, not a repo-wide requirement — see "Conventions" below and `STYLE_GUIDE.md` for the
logging scheme new code should follow.

**Adding a service**: make the folder, write the class, re-export it in `__init__.py`, write
`README.md`, add `log_config.toml` if it logs, then wire it into `main.py`. Nothing else registers
it — no `pyproject.toml` edit, no `uv sync`.

`warp/` and `scripts/brettzone_frames.py` are the real (non-mock) code: hand-clicked arena-floor
corners → 640x640 top-down perspective warp, with per-camera calibration cached in `manifest.json`
and re-reviewed per match so a bumped camera doesn't silently reuse a stale warp.

## Conventions (from STYLE_GUIDE.md)

- **Logging levels** (see `STYLE_GUIDE.md` for the full scheme, which is library-agnostic — no
  logging library is mandated repo-wide): `INFO`/`ERROR`/`WARNING` are competition-visible —
  essential results, blocking issues, non-blocking faults. `DEBUG` marks major code points and is
  committed to git. `TRACE` is for hunting a specific bug (line #, containing function, call
  stack, in-scope vars) and should not be committed. Each run gets its own `logs/{time}_log/`
  folder, with entries additionally sorted by the nearest "major function" up the call stack. Log
  calls are not free on the hot path, so keep INFO-level logs few and short.
- **Ruff is the only linter/formatter.** Do not add black/isort/flake8/pylint. All config lives in
  the root `pyproject.toml` under `[tool.ruff]` — no per-service config, and don't widen `ignore`
  to silence one line. Suppress with a code and a reason: `# noqa: ARG002 - reason`, never a bare
  `# noqa`. Don't reformat unrelated files in a feature PR.
- **Docstrings**: Google convention (enforced by ruff `D`), summary line on the opening quotes,
  blank line before the body, `Args`/`Returns`/`Raises` sections.
- **Types**: every parameter and return annotated (ruff `ANN`), including third-party types
  (`np.ndarray`, `pd.DataFrame`). Prefer `int | str` over `Union`; avoid optional-`None` params
  where a non-optional design works. Prefer defined dataclasses over ad-hoc dicts.
- **Naming**: variables short but readable in context (`img`, `lcorner`, not `temp`); function
  names fully descriptive of purpose/output (`get_huey_corner_colors`, not `new_colors`).
- **Git**: conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`). PR required before
  merging to `develop` or `main`; unit tests must pass before `develop`, real-life robot testing
  before `main`; one human reviewer required.
- **AI policy**: AI must not be the only reviewer of a PR — a human reads, reviews, and approves.
  Humans lead ideation and design, and must understand and be able to defend every line, so any
  AI-written change has to be explained thoroughly enough for a human to defend it in depth.

Note: the ruff `target-version` is `py311` (matching the interpreter on the robot) even though the
projects require Python 3.13.12 for development.
