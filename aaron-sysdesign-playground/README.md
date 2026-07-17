At the end of the year, we discussed doing a system design overhaul to start the new year fresh, free of spaghetti code.
In this folder, I will be trying out some tools that could be useful for this redesign to encourage software engineering best practices.

This repo is a small mock-up of that redesign: a fake robot pipeline (camera to object detection to decision algorithm) wired together by a single orchestrator, with each stage split into its own package. It's meant to be read end to end as a reference for the patterns, not as a real application.

## Setup

This project uses [uv](https://docs.astral.sh/uv/) to manage the Python version and dependencies.

Sync your environment to match `pyproject.toml` / `uv.lock` (installs Python 3.13.12 if needed):

```
uv sync
```

Run the pipeline using that environment:

```
uv run main.py
```

Run it with detailed timing info:
```
uv run viztracer main.py
```

View that detailed timing info:
```
uv run vizviewer result.json
```

Add a package to the environment:
```
uv add <package>
```

If VS Code is showing errors, be sure to set your python interpreter (via cmd shift P) to aaron-sysdesign-playground/.venv/bin/python

## Repo structure

```
aaron-sysdesign-playground/
├── main.py                  # orchestrator: constructs services, runs the hot loop
├── pyproject.toml           # dependencies + Python version requirement (uv-managed)
├── uv.lock                  # locked, reproducible dependency versions
├── .python-version          # pinned interpreter version (3.13.12)
├── algorithm/
│   ├── algorithm.py         # Algorithm: turns detections into decisions
│   ├── __init__.py          # re-exports Algorithm
│   ├── log_config.toml      # this service's default console/logfile levels
│   └── README.md
├── camera/
│   ├── camera.py            # Camera: mock frame capture, produces Frame
│   ├── __init__.py          # re-exports Camera
│   ├── log_config.toml
│   └── README.md
├── object_detection/
│   ├── object_detection.py  # ObjectDetector: turns a Frame into a DetectionResult
│   ├── __init__.py          # re-exports ObjectDetector
│   ├── log_config.toml
│   └── README.md
├── datatypes/
│   ├── datatypes.py         # shared dataclasses passed between stages: Frame, Detection, DetectionResult
│   ├── __init__.py          # re-exports the dataclasses
│   └── README.md
├── logging_config/
│   ├── logging_config.py    # loguru setup: CLI flags, console + per-service file sinks
│   ├── __init__.py          # re-exports configure_logging, parse_args
│   └── README.md            # logging usage and design in detail
└── logs/                    # generated on run, gitignored
    ├── main.log             # everything, filtered like the console
    ├── camera.log           # just camera's logs
    ├── algorithm.log        # just algorithm's logs
    └── ...                  # one file per service, auto-discovered
```

## Design decisions

### Folder-per-service packages with repo-root imports

Every stage of the pipeline lives in its own folder at the repo root: `<name>/<name>.py` holds the logic, `<name>/__init__.py` re-exports the public class(es), and `<name>/README.md` documents it. Because `main.py` sits at the repo root, Python puts the root on `sys.path` automatically, so any module can import any service directly:

```python
from camera import Camera
from object_detection import ObjectDetector
```

This also means services can import each other where that makes sense (a future `algorithm` feature could `from object_detection import ObjectDetector` directly), without any special setup.

Two alternatives were deliberately not used:

- **`sys.path.append` hacks.** Fragile and required per-file boilerplate at the top of every entry point. This repo used to do this; it's been removed now that everything lives under the repo root.
- **uv workspace editable packages.** The right tool when components are versioned and deployed independently, but pure overhead here — this is one app deployed as a unit, not a set of separately released libraries.

Net effect: adding a service requires zero registration anywhere. Make the folder, add the files, done — no `pyproject.toml` edits, no `uv sync`. See "Adding a new service" below.

### Orchestrator pattern

`main.py` is the only place services get wired together. Services never call each other in the hot loop — `main` hands each stage's output to the next as a typed, `slots=True` dataclass owned by `datatypes/` (`Frame` -> `DetectionResult`). That keeps every service testable alone: construct its input dataclass, call its one hot-path method, check the output. Each service also exposes read-only state accessors (e.g. `camera.frames_captured`) for logging and debugging without exposing mutable internals.

### Logging

Logging is handled by `logging_config/`, built on [loguru](https://loguru.readthedocs.io/). Console and log-file verbosity are controlled independently (`--console`/`--logfile`, or the `--debug`/`--trace` shortcuts for both at once). Per-service default levels live in each service's own `log_config.toml` rather than being passed on the command line — CLI flags, when given, override those files. Log files are written to `logs/` at the repo root, with one file per service that opts in via `log_config.toml`. See [logging_config/README.md](logging_config/README.md) for the full design and CLI reference.

### Profiling

[viztracer](https://github.com/gaogaotiantian/viztracer) is a dev dependency, useful for seeing exactly where time goes in a run:

```
uv run viztracer main.py
uv run vizviewer result.json
```

## Adding a new service

1. `mkdir foo`
2. `foo/foo.py` — write the service's logic (a class with one hot-path method plus read-only state accessors, following the existing services as a template).
3. `foo/__init__.py` — re-export the public class, e.g. `from .foo import Foo`.
4. `foo/README.md` — document what it does, its hot-path method, and its queryable state.
5. `foo/log_config.toml` — only if `foo` actually calls `logger.*`: `console = "INFO"` / `logfile = "INFO"` (or whatever default level makes sense). Skip this file entirely for folders that don't log (like `datatypes/`).
6. In `main.py`, `from foo import Foo`, construct it alongside the other services, and wire its input/output into the pipeline.
7. Nothing else to do. `logging_config` discovers services by scanning the repo root for folders containing `log_config.toml`, so `logs/foo.log` appears automatically on the next run.

## CLI flags

`main.py` parses its arguments via `logging_config.parse_args()`. All flags configure logging; there's no other CLI surface yet.

| Flag | Effect |
| --- | --- |
| *(none)* | Console and log files at each service's own `log_config.toml` level (default `INFO`). |
| `--no-logs` | Disable logging entirely: no console output, no log files. |
| `--debug` | Log at `DEBUG` in both console and log files, globally. |
| `--trace` | Log at `TRACE` in both console and log files, globally. |
| `--console {NONE,INFO,DEBUG,TRACE}` | Set the console level explicitly. `NONE` disables console output only. |
| `--logfile {NONE,INFO,DEBUG,TRACE}` | Set the log file level explicitly. `NONE` disables all log files only. |
| `--clear-logs` | Wipe `logs/` before this run instead of appending to it. Combines with any other flag. |
| `--simple-logs` | Format every sink as just the raw message (no timestamp/level/name). |

`--no-logs`, `--debug`, `--trace`, and `--console`/`--logfile` are mutually exclusive with each other (pick one way to control verbosity); `--console` and `--logfile` may be combined with each other. Examples:

```
uv run main.py --trace
uv run main.py --console NONE --logfile TRACE
uv run main.py --console DEBUG --logfile NONE
```

Full detail — the per-service `log_config.toml` mechanism, how filtering resolves per module, log file locations, rotation, and performance notes — lives in [logging_config/README.md](logging_config/README.md).
