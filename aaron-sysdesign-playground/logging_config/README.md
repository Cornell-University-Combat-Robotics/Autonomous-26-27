# logging_config

This package configures [loguru](https://loguru.readthedocs.io/) for the whole repo: one console sink, one combined log file, and one log file per service.

When developing code, log things important to see on every run like "Object Detection initialized succesfully" at the INFO level.
Log things important for debugging why something might not be working generally like "Object Detection returned in 4.3 ms" at the DEBUG level.
Log things important for specifically debugging a file like "Line X starting...." "Line X done." at the TRACE level.

## Usage

Call `configure_logging(parse_args())` once, at the top of an entry point:

```python
from logging_config import configure_logging, parse_args

configure_logging(parse_args())
```

`main.py` does exactly this before constructing any services. Every other module just does `from loguru import logger` and logs normally — sinks are process-global, so configuring once at startup is enough.

## CLI flags

`parse_args()` recognizes:

| Flag | Effect |
| --- | --- |
| `--no-logs` | Disable logging entirely: no console output, no log files. |
| `--debug` | Log at `DEBUG` in both the console and log files, globally. |
| `--trace` | Log at `TRACE` in both the console and log files, globally. |
| `--console {NONE,INFO,DEBUG,TRACE}` | Set the console level explicitly. `NONE` disables console output only. |
| `--logfile {NONE,INFO,DEBUG,TRACE}` | Set the log file level explicitly. `NONE` disables all log files only. |
| `--clear-logs` | Empty `logs/` before this run instead of appending to it. Combines with anything. |
| `--simple-logs` | Format every sink as just `{message}`, skipping timestamp/level/name/line formatting. |

`--no-logs`, `--debug`, `--trace`, and `--console`/`--logfile` are mutually exclusive — pick exactly one way to control verbosity per run. `--console` and `--logfile` are the exception: they can be combined with each other (but not with `--no-logs`/`--debug`/`--trace`), letting console and file verbosity differ, e.g. a quiet terminal with a detailed log file:

```
uv run main.py --console NONE --logfile TRACE
```

Violating this (e.g. `--no-logs --trace`) prints a clear error and exits rather than silently picking one.

`--clear-logs` runs before the `--no-logs` check, so `--no-logs --clear-logs` still empties `logs/` even though the run itself produces nothing new.

## Per-service log levels: `log_config.toml`

Rather than passing per-service levels on the command line, each service folder that wants logging opts in with its own `log_config.toml`:

```toml
console = "INFO"
logfile = "INFO"
```

Both keys are optional and default to `INFO`. A service folder with no `log_config.toml` (e.g. `datatypes/`, which never calls `logger.*`) is invisible to `logging_config` entirely — it gets no dedicated log file, and any log calls it did make would only show up in `main.log` at the global default level.

These per-service levels are what apply when the CLI doesn't specify a level for that sink — **CLI flags always override every service's file-based level.** `--debug`/`--trace`/`--console`/`--logfile`, when given, apply the requested level to every service uniformly, ignoring `log_config.toml` for that sink. Only when neither `--debug`/`--trace` nor `--console`/`--logfile` is passed does each service's own file take effect (with `""`/unconfigured folders falling back to `INFO`).

This is implemented via loguru's dict `filter`: the sink's `filter` maps a module name to a minimum level, with `""` as the fallback for anything not explicitly listed. Loguru resolves a record's module name (e.g. `algorithm.algorithm`) to the closest matching key in that dict, so the bare service name `"algorithm"` governs every module inside that folder. See `_resolve_sink` in [logging_config.py](logging_config.py).

## Log files

Log files always land at `REPO_ROOT/logs`, where `REPO_ROOT` is derived from `logging_config.py`'s own location (`Path(__file__).resolve().parent.parent`) — not the current working directory, so it doesn't matter where a script is run from.

- `main.log` — everything that passes the resolved logfile level/filter.
- `<service>.log` — one file per service folder that has a `log_config.toml`, containing only that service's log records, at whatever level the logfile sink resolved for it.

The service list is generated each run by scanning the repo root for directories containing a `log_config.toml` (`_discover_services()` in [logging_config.py](logging_config.py)). Adding a new service folder gets it a log file automatically as soon as it has that file — no changes needed in `logging_config.py`.

All file sinks use 10 MB rotation, zip compression, and 7-day retention.

## Performance notes

- **`ENQUEUE`** is a module-level constant at the top of `logging_config.py`, currently `False`. Setting it `True` moves formatting and writing to a background thread for every sink, so `logger.*()` calls just enqueue the record and return immediately — keeping logging off the hot path. The trade-off is that queued-but-unwritten records can be lost if the process is killed abruptly.
- **Deferred formatting.** Log calls should pass arguments to loguru rather than pre-formatting with an f-string:

  ```python
  logger.debug("camera: frame {} captured", frame.frame_id)   # good
  logger.debug(f"camera: frame {frame.frame_id} captured")    # avoid
  ```

  With the first form, interpolation only happens if a sink actually accepts the record at its configured level; the f-string form pays the formatting cost every time regardless of whether anything will read it.
- **Formats** are module constants — `CONSOLE_FORMAT`, `LOGFILE_FORMAT`, and `SIMPLE_FORMAT` — so the look of every sink can be changed in one place. `--simple-logs` swaps every sink to `SIMPLE_FORMAT` (`{message}` only, skipping loguru's per-call datetime/markup formatting); otherwise the console and file sinks use `CONSOLE_FORMAT` / `LOGFILE_FORMAT` respectively. See loguru's [record fields](https://loguru.readthedocs.io/en/stable/api/logger.html#record) for what's available (`{time}`, `{level}`, `{name}`, `{function}`, `{line}`, `{message}`, etc.) when editing these.
