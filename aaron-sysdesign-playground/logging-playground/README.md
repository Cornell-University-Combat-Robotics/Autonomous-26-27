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

This works via loguru's dict `filter`: the sink's `filter` maps module name -> minimum level, with `""` as the default for any module not explicitly listed. See [logging_config.py](logging_config.py)'s `configure_logging`.
