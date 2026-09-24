# Autonomous-26-27
Combat Robotics @ Cornell Autonomous Subteam repository for the 2026-2027 academic year.

### uv setup/running
Install uv
```
pip install uv
```

Sync your environment to match `pyproject.toml` / `uv.lock` (installs Python 3.13.12 if needed):

```
uv sync
```

Run the pipeline using that environment:

```
uv run main.py
```

Add a package to the environment:
```
uv add <package>
```

Remove a package from the environment:
```
uv remove <package>
```