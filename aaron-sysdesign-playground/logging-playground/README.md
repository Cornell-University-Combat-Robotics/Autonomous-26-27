This folder gives an example of a popular logger, loguru.
With a custom logger, we don't need to jump around creating/deleting print statements.

When developing code, log things important to see on every run like "Object Detection initialized succesfully" at the INFO level. 
Log things important for debugging why something might not be working generally like "Object Detection returned in 4.3 ms" at the DEBUG level.
Log things important for specifically debugging a file like "Line X starting...." "Line X done." at the TRACE level.

A multi-file example (`main.py`, `service_a.py`, `service_b.py`) shows per-module log level control, configured entirely in code (no env vars needed).

By default everything logs at `INFO`. Flags let you selectively raise the level:

```
uv run logging-playground/main.py                                # INFO everywhere
uv run logging-playground/main.py --debug                        # DEBUG everywhere
uv run logging-playground/main.py --trace                        # TRACE everywhere
uv run logging-playground/main.py --debug service_a               # only service_a at DEBUG, rest stay INFO
uv run logging-playground/main.py --trace service_a service_b     # both at TRACE
```

`--debug` and `--trace` can also be combined, each targeting different modules, e.g. `--debug service_b --trace service_a`.

This works via loguru's dict `filter`: the sink's `filter` maps module name -> minimum level, with `""` as the default for any module not explicitly listed. See [logging_config.py](../logging_config.py)'s `configure_logging`.

`logging_config.py` now lives at the repo root (`aaron-sysdesign-playground/logging_config.py`) so any folder can reuse it — each entry-point script adds the repo root to `sys.path` before importing it (see the top of `main.py`).

## Log files and formatting

`configure_logging(args, log_dir)` also writes every log (always at `TRACE`, regardless of the CLI flags) to `<log_dir>/app.log`, rotating to a new file past 10 MB, compressing rotated files, and deleting anything older than 7 days. Each entry-point script passes its own directory (`log_dir=Path(__file__).parent / "logs"`), so `logging-playground/main.py` writes to `logging-playground/logs/`, `example-main/main.py` writes to `example-main/logs/`, and so on — logs always land next to the script that produced them, not in `logging_config.py`'s own location. To change rotation/retention/compression, edit the `logger.add(log_dir / "app.log", ...)` call in [logging_config.py](../logging_config.py).

Console output uses `CONSOLE_FORMAT` (no date, just time) instead of loguru's default. Each sink can have its own `format`, so the file sink keeps loguru's default (full date + function name) since it's meant for later review. To change what a sink prints, edit its `format` string — see loguru's [record fields](https://loguru.readthedocs.io/en/stable/api/logger.html#record) for what's available (`{time}`, `{level}`, `{name}`, `{function}`, `{line}`, `{message}`, etc.).
