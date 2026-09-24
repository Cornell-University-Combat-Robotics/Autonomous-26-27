### High level structure conventions

### Tools
- Logging
    - Info (level 1)
        - Anything that humans want to see in actual competition.
        - e.g. “x enemies detected,” “theta orientation,” “motor outputs”
    - Errors (level 1)
        - Big issues that need to be known.
        - e.g. “Sensors stopped”
    - Warnings (level 1)
        - Non-blocking faults which should be addressed, but aren't critical to the performance of the current run. 
        - e.g. “No robots detected”
    - Debug (level 2)
        - Permanently pushed to git, records major points in code.
        - e.g. “Entered 2 cornder”
    - Trace (level 3)
        - Should not be included in git (add github action).
        - Should be used in finding specific bugs.
        - Includes:
            - Line #
            - Containing function
            - Full call stack?
            - All vars in scope
            - Curr iteration of main
    - Log sorting
        - Each run gets its own /{time}_log folder
        - Within each folder, logs are sorted by parent function (in addition to one main function).
        - Config file contains set of “major” functions.
        - When a log function is called, it should move up the call stack until it reaches one of these “major” functions, then categorizes the call into that folder (in addition to the main folder).
- ruff
    - Ruff is the only linter and formatter in this repo. It replaces black, isort, flake8, and pylint. Do not add a second one.
    - All config lives under `[tool.ruff]` in the root `pyproject.toml`. No per-service config. Pin an exact version there and in pre-commit; bump it in its own PR.
    - `ruff format` is authoritative. Do not hand-format, and do not reformat unrelated files in a feature PR.
    - Enforced by pre-commit via `astral-sh/ruff-pre-commit`. Run `pre-commit install` once after cloning.
    - Suppress with a specific code and a reason: `# noqa: ARG002 - signature fixed by the SDK callback protocol`. Never a bare `# noqa`. Never widen `ignore` in `pyproject.toml` to silence one line.
- git
    - commit messages
        - Use conventional commits format.
        - Examples of how to do this:
            - `docs: correct spelling of CHANGELOG`
            - `fix: prevent racing of requests`
            - `feat: send an email to the customer when a product is shipped`
            - `test: add github actions`
    - pull requests
        - Make a pull request before merging into main or develop.
        - Unit tests must pass before pushing to develop, and real life testing must be done before pushing to main. 
        - One other developer must review the pull request before it is merged into develop or main.
        - AI must not be used (exclusivly) for reviewing pull requests. It must be read, reviewed, and approved by a human.

### Documentation Rules
#### Method Documentation
- Docstrings: Use triple double quotes with the summary line right after the opening quotes, and a blank line separating the summary from the description and each of the Args/Returns/Raises sections. Generally should have Args, Returns, Raises, and optionally Examples.
    - Example of docstring format:
    ```
    def module_level_function(
            param1: str,
            param2: int | None = None,
            *args: int,
            **kwargs: str) -> bool:
        """This is an example of a module level function.

        Function parameters should be documented in the ``Args`` section. The name of each parameter is required. The type and description of each parameter is optional, but should be included if not obvious.

        Args:
            param1: The first parameter.
            param2: The second parameter. Defaults to None.
                Second line of description should be indented.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            bool: True if successful, False otherwise.

        Raises:
            AttributeError: The ``Raises`` section is a list of all exceptions that
                are relevant to the interface.
            ValueError: If `param2` is equal to `param1`.
        """
        if param1 == param2:
            raise ValueError("param1 may not be equal to param2")
        return True
    ```
        

#### Type Enforcement
- All functions and methods must have defined types for both parameters and outputs.
    - Some types can be `Union[int, str]` which is equivalent to `int | str`
    - Try to avoid letting things be `None` but if they are, make sure to specify in type `None | int` for example.
    - If using other packages like numpy or pandas, still specify with types: `pd.DataFrame`, `np.array`.
- Look to Method Documentation for full docstrings.
- For complex data structures, try to only use defined data types. For commonly used dictionaries, like the bots dictionary use the defined spec.


#### Naming Convention
- Variable names should be short but understandable to someone that has read the specific block of code.
    - Avoid `temp`, but `img` or `lcorner` works
- Function names should not be as short as variable names. They should clearly say what their purpose or output is, so anyone not familiar with the code could understand what they do. 
    - Good examples: `get_huey_corner_colors`, ``
    - Bad examples: `new_colors`, ``


#### System Structure
- Each service has an init.py file. Each service should be treated as a package.

### AI Agent Instructions/Use Policy
- Rules
    - AI should not be used as the only step in a P.R. evaluation. P.R.s must be read, reviewed, and approved by a human. 
    - Humans should take the lead in ideation and design. 
    - Humans must understand and be able to defend every line of code. Any code changes by an AI must be thoroughly explained to a human such that a human could explain it in depth.