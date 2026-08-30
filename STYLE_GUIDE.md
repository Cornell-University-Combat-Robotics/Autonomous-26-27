### High level structure conventions

### Tools
- loguru
    - Use this tool for logging. Use logging for tracing, debugging, and information.
    - Tracing (TRACE)
        - This is the level used when debugging, when a programmer needs to see what lines of code were executed on a given (possibly faulty) run.
        - Log things that are important for specifically debugging a file like "Line X starting...." "Line X done." at the TRACE level.
        - Here is an example of a logging trace line: `logger.trace("object_detection: line 5 done GO HUEY")`
    - Debugging (DEBUG)
        - This level is also used for debugging, to output information about a given run to make debugging easier for a programmer. 
        - Log things that are important for debugging when something might not be working generally like "Object Detection returned in 4.3 ms" at the DEBUG level.
        - Here is an example of a logging debug line: `logger.debug("camera: frame {} captured", frame.frame_id)`
    - Information (INFO)
        - Info level logs will be what will be outputted during actual competition. These should be essential for runtime. For example, "Camera initialized at 1920x1080, 120 fps."
        - Here is an example of a logging info line: `logger.info("camera: initialized ({}x{})", width, height)`
    - For all logs, don't use an f-string, use the lazy brace form `logger.debug("camera: frame {} captured", frame.frame_id)`.
- ruff
    - Ruff is the only linter and formatter in this repo. It replaces black, isort, flake8, and pylint. Do not add a second one.
    - All config lives under `[tool.ruff]` in the root `pyproject.toml`. No per-service config. Pin an exact version there and in pre-commit; bump it in its own PR.
    - `ruff format` is authoritative. Do not hand-format, and do not reformat unrelated files in a feature PR.
    - Enforced by pre-commit via `astral-sh/ruff-pre-commit`. Run `pre-commit install` once after cloning.
    - Suppress with a specific code and a reason: `# noqa: ARG002 - signature fixed by the SDK callback protocol`. Never a bare `# noqa`. Never widen `ignore` in `pyproject.toml` to silence one line.
    - Ruff does not check loguru call style. Use the lazy brace form `logger.debug("camera: frame {} captured", frame.frame_id)` rather than an f-string, so the message is only built when the level is enabled.
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


### Example Class
This example demonstrates the tooling, documentation, and naming conventions above: loguru logging at the TRACE/DEBUG/INFO levels using the lazy brace form, Google-style docstrings with Args/Returns/Raises, full type annotations (including `float | None` for an optional parameter), and short-but-clear variable names paired with descriptive method names.
```
from loguru import logger


class Calculator:
    """A running-total calculator with loguru-backed operation logging.

    Args:
        start: The running total's initial value. Defaults to 0.
    """

    def __init__(self, start: float = 0) -> None:
        self.total: float = start
        logger.info("calculator: initialized (start={})", start)

    def add_to_total(self, value: float) -> float:
        """Adds a value to the running total.

        Args:
            value: The amount to add.

        Returns:
            float: The updated running total.
        """
        logger.trace("calculator: add_to_total starting...")
        previous_total = self.total
        self.total += value
        logger.debug(
            "calculator: add_to_total computed {} + {} = {}", previous_total, value, self.total
        )
        logger.trace("calculator: add_to_total done.")
        return self.total

    def subtract_from_total(self, value: float) -> float:
        """Subtracts a value from the running total.

        Args:
            value: The amount to subtract.

        Returns:
            float: The updated running total.
        """
        logger.trace("calculator: subtract_from_total starting...")
        previous_total = self.total
        self.total -= value
        logger.debug(
            "calculator: subtract_from_total computed {} - {} = {}",
            previous_total,
            value,
            self.total,
        )
        logger.trace("calculator: subtract_from_total done.")
        return self.total

    def multiply_total_by(self, factor: float) -> float:
        """Multiplies the running total by a factor.

        Args:
            factor: The value to multiply the running total by.

        Returns:
            float: The updated running total.
        """
        logger.trace("calculator: multiply_total_by starting...")
        previous_total = self.total
        self.total *= factor
        logger.debug(
            "calculator: multiply_total_by computed {} * {} = {}",
            previous_total,
            factor,
            self.total,
        )
        logger.trace("calculator: multiply_total_by done.")
        return self.total

    def divide_total_by(self, divisor: float) -> float:
        """Divides the running total by a divisor.

        Args:
            divisor: The value to divide the running total by. May not be 0.

        Returns:
            float: The updated running total.

        Raises:
            ZeroDivisionError: If `divisor` is 0.
        """
        logger.trace("calculator: divide_total_by starting...")
        if divisor == 0:
            logger.debug("calculator: divide_total_by rejected a 0 divisor")
            raise ZeroDivisionError("divisor may not be 0")
        previous_total = self.total
        self.total /= divisor
        logger.debug(
            "calculator: divide_total_by computed {} / {} = {}",
            previous_total,
            divisor,
            self.total,
        )
        logger.trace("calculator: divide_total_by done.")
        return self.total

    def reset_total(self, new_total: float | None = None) -> float:
        """Resets the running total.

        Args:
            new_total: The value to reset the total to. Defaults to None,
                which resets the total back to 0.

        Returns:
            float: The updated running total.
        """
        logger.trace("calculator: reset_total starting...")
        self.total = new_total if new_total is not None else 0
        logger.info("calculator: total reset to {}", self.total)
        logger.trace("calculator: reset_total done.")
        return self.total
```
