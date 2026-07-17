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

Default console level is `INFO`. `parse_args()` recognizes:

| Flag | Effect |
| --- | --- |
| `--debug [SERVICE ...]` | Raise to `DEBUG`. With no names, applies to everything. With names (e.g. `--debug camera`), raises only those services; everything else stays `INFO`. |
| `--trace [SERVICE ...]` | Same as `--debug`, but raises to `TRACE`. |
| `--clean-logs` | Empty `logs/` before this run instead of appending to it. |
| `--no-logs` | Disable logging entirely: no console sink, no file sinks. Short-circuits before `--clean-logs` runs, so combining the two does not clear existing logs. |
| `--console-only` | Add the console sink only; skip writing any log files. |
| `--simple-logs` | Format every sink as just `{message}`, skipping timestamp/level/name/line formatting. |

`--debug` and `--trace` are combinable, each targeting different services, e.g. `--debug camera --trace algorithm` raises `camera` to `DEBUG` and `algorithm` to `TRACE` while everything else stays at `INFO`.

This works via loguru's dict `filter`: the sink's `filter` maps a module name to a minimum level, with `""` as the fallback for anything not explicitly listed. Loguru resolves a record's module name (e.g. `algorithm.algorithm`) to the closest matching key in that dict, so a bare service name like `"algorithm"` governs every module inside that service's folder. See `configure_logging` in [logging_config.py](logging_config.py).

## Log files

Log files always land at `REPO_ROOT/logs`, where `REPO_ROOT` is derived from `logging_config.py`'s own location (`Path(__file__).resolve().parent.parent`) — not the current working directory, so it doesn't matter where a script is run from.

- `main.log` — everything, filtered with the exact same level and per-service overrides as the console sink, so it always mirrors what's on screen.
- `<service>.log` — one file per top-level service folder, containing only that service's log records, at whatever level the console shows for it.

The service list is generated each run by scanning the repo root for directories containing an `__init__.py` (`_service_packages()` in [logging_config.py](logging_config.py)). Adding a new service folder gets it a log file automatically — no changes needed here.

Because file sinks reuse the same level/filter as the console, log files never contain more than what the console would have shown. All file sinks use 10 MB rotation, zip compression, and 7-day retention.

## Performance notes

- **`ENQUEUE`** is a module-level constant at the top of `logging_config.py`, currently `False`. Setting it `True` moves formatting and writing to a background thread for every sink, so `logger.*()` calls just enqueue the record and return immediately — keeping logging off the hot path. The trade-off is that queued-but-unwritten records can be lost if the process is killed abruptly.
- **Deferred formatting.** Log calls should pass arguments to loguru rather than pre-formatting with an f-string:

  ```python
  logger.debug("camera: frame {} captured", frame.frame_id)   # good
  logger.debug(f"camera: frame {frame.frame_id} captured")    # avoid
  ```

  With the first form, interpolation only happens if a sink actually accepts the record at its configured level; the f-string form pays the formatting cost every time regardless of whether anything will read it.
- **Formats** are module constants — `CONSOLE_FORMAT`, `LOGFILE_FORMAT`, and `SIMPLE_FORMAT` — so the look of every sink can be changed in one place. `--simple-logs` swaps every sink to `SIMPLE_FORMAT` (`{message}` only, skipping loguru's per-call datetime/markup formatting); otherwise the console and file sinks use `CONSOLE_FORMAT` / `LOGFILE_FORMAT` respectively. See loguru's [record fields](https://loguru.readthedocs.io/en/stable/api/logger.html#record) for what's available (`{time}`, `{level}`, `{name}`, `{function}`, `{line}`, `{message}`, etc.) when editing these.
