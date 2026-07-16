At the end of the year, we discussed doing a system design overhaul to start the new year fresh, free of spaghetti code.
In this folder, I will be trying out some tools that could be useful for this redesign to encourage software engineering best practices.

## Setup

This project uses [uv](https://docs.astral.sh/uv/) to manage the Python version and dependencies.

Sync your environment to match `pyproject.toml` / `uv.lock` (installs Python 3.13.12 if needed):

```
uv sync
```

Run a script using that environment:

```
uv run <file>.py
```

Run a script with detailed timing info:
```
uv run viztracer <file>.py
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