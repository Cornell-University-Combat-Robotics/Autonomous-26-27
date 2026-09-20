"""Process-wide logging setup: five levels, per-run folders, and locals-capturing traces.

Importing this module installs :class:`Logger` as the class the standard library hands back, so
every other module just does ``import logging`` and ``logging.getLogger(__name__)``.

This package must not be imported with the repository root on ``sys.path`` under the name
``logging`` -- the folder is named ``logging_config`` precisely so it cannot shadow the standard
library's ``logging`` module.

Style reference: https://medium.com/@aman.deep291098/python-custom-logging-made-easy-c89f4972af95
"""

import logging
import math
import os
import sys
from time import time
from types import FrameType, ModuleType

ERROR_LEVEL = 40
WARNING_LEVEL = 30
INFO_LEVEL = 20
DEBUG_LEVEL = 10
TRACE_LEVEL = 5

logging.addLevelName(TRACE_LEVEL, "TRACE")

# These should be exposed to config file
CONSOLE_LOGGING_LEVEL = DEBUG_LEVEL
FILE_LOGGING_LEVEL = TRACE_LEVEL
TRACE_MAX_STACK_DEPTH = 1000
TRACE_REPR_LIMIT = 200
TRACE_ARRAY_MAX_ELEMENTS = 32

RUN_NAME = str(int(time()))  # This should be exposed to config file, can be set custom


def _safe_repr(value: object, limit: int = TRACE_REPR_LIMIT) -> str:
    """Return text for an object in the stack, limited by size `limit`.

    For np.arrays and similar data types, the text includes the values in the array, unless the
    object has more than `TRACE_ARRAY_MAX_ELEMENTS` elements.

    Args:
        value: Object to render
        limit: Maximum numbers of characters to keep.

    Returns:
        str: Single line, bounded representation of `value`.
    """
    try:
        shape = getattr(value, "shape", None)
        dtype = getattr(value, "dtype", None)
        if shape is not None and dtype is not None and math.prod(shape) > TRACE_ARRAY_MAX_ELEMENTS:
            return f"<{type(value).__name__} shape={tuple(shape)} dtype={dtype}>"
        text = repr(value)
    except Exception as exc:
        return f"<unreprable {type(value).__name__}: {type(exc).__name__}>"
    text = " ".join(text.split())  # collapse newlines and indentation to one line
    if len(text) > limit:
        return f"{text[:limit]}...(+{len(text) - limit})"
    return text


def _format_frame_locals(frame: FrameType, limit: int = TRACE_REPR_LIMIT) -> str:
    """Render a frame's local variables as a `name=value` list.

    Dunder names (__init__, __main__) and imported modules are dropped.

    Args:
        frame: The stack frame whose locals should be rendered
        limit: Maximum number of characters to for each variable (passed to ``_safe_repr``)

    Returns:
        str: A brace-wrapped list of locals, empty as ``{}`` when the frame held none worth
            showing.
    """
    frame_locals = dict(frame.f_locals)
    rendered = [
        f"{name}={_safe_repr(value, limit)}"
        for name, value in frame_locals.items()
        if not name.startswith("__") and not isinstance(value, ModuleType)
    ]
    return "{" + ", ".join(rendered) + "}"


def _format_call_with_locals(frame: FrameType, max_depth: int = TRACE_MAX_STACK_DEPTH) -> str:
    """Walk up the stack from `frame`, returning a string trail of the calls that led here.

    Walks at most `max_depth` frames up, unless the top of the stack is reached first. Any frames
    left unwalked are reported as a trailing count rather than silently dropped.

    Args:
        frame: Stack frame we start from, it's caller is first.
        max_depth: Max number of caller frames.

    Returns:
        str: Frames joined by ``<``, nearest (highest on the stack) caller first, or
            ``<top of stack>`` when `frame` has no caller at all.
    """
    caller = frame.f_back
    if caller is None:
        return "<top of stack>"

    entries: list[str] = []
    while caller is not None and len(entries) < max_depth:
        filename = os.path.basename(caller.f_code.co_filename)
        location = f"{filename}:{caller.f_code.co_qualname}:{caller.f_lineno}"
        entries.append(f"{location} {_format_frame_locals(caller)}")
        caller = caller.f_back
    if caller is not None:
        omitted = 0
        while caller is not None:
            omitted += 1
            caller = caller.f_back
        entries.append(f"...(+{omitted} frame{'s' if omitted != 1 else ''})")
    return " < ".join(entries)


# One shared handler for the run-wide file, so every logger appends through a single stream
# instead of each opening its own. Built on first use, because it has to create the run folder.
_all_file_handler: "CustomFileHandler | None" = None


def _run_log_dir() -> str:
    """Return this run's log folder, creating it if this is the first logger of the run.

    Returns:
        str: Path to ``logs/{RUN_NAME}``, relative to the working directory.
    """
    run_dir = f"logs/{RUN_NAME}"
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def _shared_all_file_handler() -> "CustomFileHandler":
    """Return the one handler every logger uses to write the run-wide ``all.log``.

    Returns:
        CustomFileHandler: The process-wide handler for ``logs/{RUN_NAME}/all.log``.
    """
    global _all_file_handler
    if _all_file_handler is None:
        _all_file_handler = CustomFileHandler(logfile_name=f"{_run_log_dir()}/all.log")
    return _all_file_handler


class Logger(logging.Logger):
    """Logger with ERROR, WARNING, INFO, DEBUG, and TRACE levels.

    Each instance has a custom file handler, that saves logger entries per-run. Each module
    has its own file of entries within the run's saved logger folder.

    Always obtain one through ``logging.getLogger(name)``, never by calling ``Logger(name)``
    directly: ``getLogger`` caches by name, whereas direct construction builds a second object
    with a second set of handlers, so every record gets written twice.

    Trace calls are not to be pushed to main, as it contains local variables and sample of call
    stack per .trace() call (will over crowd log files with information only needed for deep debugging).
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.setLevel(TRACE_LEVEL)
        self.propagate = False
        # Adding a console handler
        # Whether we write to console should be exposed to config file
        console_handler = ConsoleHandler()
        self.addHandler(console_handler)

        # Adding a file handler
        # Whether we write to files should be exposed to config file
        run_file_handler = CustomFileHandler(logfile_name=f"{_run_log_dir()}/{name}.log")
        self.addHandler(run_file_handler)

        # Main file handler, shared by every logger in this run
        self.addHandler(_shared_all_file_handler())

    def trace(self, msg: str = "", max_stack_depth: int = TRACE_MAX_STACK_DEPTH) -> None:
        """Log at the custom trace level, for deep debugging.

        Message format: `{location} | {msg} | {local} | {stack}`
            - location is filename:function_name:line_of_code
            - msg is passed in
            - local is all local variables formatted
            - stack is a trail of stack calls `stack_depth` deep

        Args:
            msg: Text to be included before the rest of the data from the call.
            max_stack_depth: How far down the stack to go in data gathering.

        Returns:
            None
        """
        if not self.isEnabledFor(TRACE_LEVEL):
            return
        frame = sys._getframe(1)
        filename = os.path.basename(frame.f_code.co_filename)
        location = f"{filename}:{frame.f_code.co_qualname}:{frame.f_lineno}"
        parts = [location]
        if msg:
            parts.append(msg)
        parts.append(f"locals: {_format_frame_locals(frame)}")
        parts.append(f"stack: {_format_call_with_locals(frame, max_stack_depth)}")
        self.log(TRACE_LEVEL, " | ".join(parts))


class ConsoleHandler(logging.StreamHandler):
    """Stream handler for competition-visible output, shared format with the log files."""

    def __init__(self, level: int = CONSOLE_LOGGING_LEVEL) -> None:
        super().__init__()
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%m/%d/%Y %H:%M:%S",
        )
        self.setFormatter(formatter)
        # This should be exposed to config file
        self.setLevel(level)


class CustomFileHandler(logging.FileHandler):
    """File handler that writes one run's records at TRACE level and above."""

    def __init__(self, logfile_name: str = "logs/logfile.log") -> None:
        # We want to expose this variable to whenever we initialize the logger
        super().__init__(logfile_name, encoding="UTF-8")
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%m/%d/%Y %H:%M:%S",
        )
        self.setFormatter(formatter)
        # This should be exposed to config file
        self.setLevel(FILE_LOGGING_LEVEL)


# Set the custom logger class as the default logger class
logging.setLoggerClass(Logger)
