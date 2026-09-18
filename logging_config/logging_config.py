# This logger derived from: https://medium.com/@aman.deep291098/python-custom-logging-made-easy-c89f4972af95

import logging
from time import time
import os
import sys
from types import FrameType, ModuleType
import math

ERROR_LEVEL = 40
WARNING_LEVEL = 30
INFO_LEVEL = 20
DEBUG_LEVEL = 10
TRACE_LEVEL = 5

logging.addLevelName(TRACE_LEVEL, "TRACE")

# These should be exposed to config file
CONSOLE_LOGGING_LEVEL = DEBUG_LEVEL
FILE_LOGGING_LEVEL = TRACE_LEVEL
TRACE_STACK_DEPTH = 3
TRACE_REPR_LIMIT = 200
TRACE_ARRAY_MAX_ELEMENTS = 32

RUN_NAME = str(int(time())) # This should be exposed to config file, can be set custom

def _safe_repr(value: object, limit: int = TRACE_REPR_LIMIT) -> str:
    """
    Returns text for a object in the stack, limited by size `limit`. For np.arrays and
    similar data types, the text includes the values in the array, unless the object has
    more than `TRACE_ARRAY_MAX_ELEMENTS` elements.

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
    """
    Render a frame's local variables as a `name=value` list.
    
    Dunder names (__init__, __main__) and imported modules are dropped. 

    Args:
        frame: The stack frame whose locals should be rendered
        limit: Maximum number of characters to for each variable (passed to ``_safe_repr``)

    Returns:
        str: A brace-wrapped list of locals, or a note explaining why none were read.
    """
    # Skip module level, it's local variables are the globals of the frame, so it is just noise.
    if frame.f_code.co_name == "<module>":
        return "<module scope, skipped>"
    frame_locals = dict(frame.f_locals)
    rendered = [
        f"{name}={_safe_repr(value, limit)}"
        for name, value in frame_locals.items()
        if not name.startswith("__") and not isinstance(value, ModuleType)
    ]
    return "{" + ", ".join(rendered) + "}"

def _format_call_stack(frame: FrameType, depth: int = TRACE_STACK_DEPTH) -> str:
    """
    Walks up the stack (at most ``depth``) starting at `frame`, returning a string trail of calls 
    (each function name being called going up).
    
    Walks at most `depth` frames up, unless the top is reached.

    Args:
        frame: Stack frame we start from, it's caller is first.
        depth: Max number of caller frames.
        
    Returns:
        str: Frames joined by ``<``, nearest (highest on the stack) caller first, or ``<top of stack>``.
    """
    
    entries: list[str] = []
    caller = frame.f_back
    while caller is not None and len(entries) < depth:
        filename = os.path.basename(caller.f_code.co_filename)
        entries .append(f"{filename}:{caller.f_code.co_qualname}:{caller.f_lineno}")
        caller = caller.f_back
    if not entries:
        return "<top of stack>"
    return " < ".join(entries)


class Logger(logging.Logger):
    """
    Logger with ERROR, WARNING, INFO, DEBUG, and TRACE levels.

    Each instance has a custom file handler, that saves logger entries per-run. Each module
    has its own file of entries within the run's saved logger folder.

    Trace calls are not to be pushed to main, as it contains local variables and sample of call
    stack per .trace() call (will over crowd log files with information only needed for deep debugging). 
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        print(f"Initializing logger with name: {name}")
        self.setLevel(TRACE_LEVEL)
        self.propagate = False
        # Adding a console handler
        # Whether we write to console should be exposed to config file
        console_handler = ConsoleHandler()
        self.addHandler(console_handler)

        
        # If logs/RUN_NAME directory does not exist, create it
        if not os.path.exists(f"logs/{RUN_NAME}"):
            os.makedirs(f"logs/{RUN_NAME}")
        
        # Adding a file handler
        # Whether we write to files should be exposed to config file
        run_file_handler = CustomFileHandler(logfile_name=f"logs/{RUN_NAME}/{name}.log")
        self.addHandler(run_file_handler)
        
        # Main file handler
        all_file_handler = CustomFileHandler(logfile_name=f"logs/{RUN_NAME}/all.log")
        self.addHandler(all_file_handler)

    def trace(self, msg: str = "", stack_depth: int = TRACE_STACK_DEPTH) -> None:
        """
        Custom trace level for deep debugging.

        Message format: `{location} | {msg} | {local} | {stack}`
            - location is filename:function_name:line_of_code
            - msg is passed in
            - local is all local variables formatted
            - stack is a trail of stack calls `stack_depth` deep
        
        Args:
            msg: Text to be included before the rest of the data from the call.
            stack_depth: How far down the stack to go in data gathering.
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
        parts.append(f"stack: {_format_call_stack(frame, stack_depth)}")
        self.log(TRACE_LEVEL, " | ".join(parts))
    
class ConsoleHandler(logging.StreamHandler):
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
    def __init__(self, logfile_name = "logs/logfile.log") -> None:
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