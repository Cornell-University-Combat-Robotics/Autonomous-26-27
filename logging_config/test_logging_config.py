"""Exercise every feature of ``logging_config`` and verify the log files it produces.

The file has three parts:

1. Unit checks that call the private formatting helpers and the handler classes directly.
2. A plain demo script -- a mock service class plus three layers of nested function calls --
   that fires all five log levels through a real ``Logger``.
3. Output checks that read the demo's log files back off disk and assert on their contents.

Every check is a zero-argument function using bare ``assert``, so the same functions can be
collected by pytest unchanged if a real test runner is added later. Run it directly with::

    uv run logging_config/test_logging_config.py

``logs/{RUN_NAME}/`` is created relative to the current working directory, because
``Logger.__init__`` builds that path relatively.
"""

import logging
import re
import sys
from collections.abc import Callable
from pathlib import Path

from logging_example_service import log_service

import logging_config
from logging_config import (
    DEBUG_LEVEL,
    TRACE_ARRAY_MAX_ELEMENTS,
    TRACE_LEVEL,
    TRACE_MAX_STACK_DEPTH,
    TRACE_REPR_LIMIT,
    ConsoleHandler,
    CustomFileHandler,
    Logger,
    _format_call_with_locals,
    _format_frame_locals,
    _safe_repr,
)

LOGGER_NAME = "test_logging_config"
SERVICE_LOGGER_NAME = "example_service"
MODULE_FILENAME = Path(__file__).name

# A distinctive string so the output checks can find this run's trace record in the log file.
TRACE_MARKER = "trace-marker-classify-target"
SERVICE_MARKER = "Service is starting..."

# Frames the demo pushes through the layered calls; one TRACE record is logged per frame.
DEMO_FRAME_IDS = (118, 119, 120)
DEMO_FRAME_COUNT = len(DEMO_FRAME_IDS)

# Importing logging_config ran `logging.setLoggerClass(Logger)`, so this is a logging_config.Logger
# with the custom `.trace()` method, not a stdlib one.
LOGGER: Logger = logging.getLogger(LOGGER_NAME)

# Results of every check run so far, as (check name, passed, failure detail).
_RESULTS: list[tuple[str, bool, str]] = []


# --------------------------------------------------------------------------------------
# Harness
# --------------------------------------------------------------------------------------


def run_check(check: Callable[[], None]) -> bool:
    """Run one check function and record whether it passed.

    Args:
        check: Zero-argument function that raises ``AssertionError`` when the behavior it
            describes is wrong.

    Returns:
        bool: True if the check passed.
    """
    try:
        check()
    except AssertionError as exc:
        _RESULTS.append((check.__name__, False, f"AssertionError: {exc}"))
        return False
    except Exception as exc:
        _RESULTS.append((check.__name__, False, f"{type(exc).__name__}: {exc}"))
        return False
    _RESULTS.append((check.__name__, True, ""))
    return True


def print_summary() -> int:
    """Print one line per recorded check plus a tally.

    Returns:
        int: 0 if every check passed, 1 otherwise.
    """
    print("\n=== CHECKS ===")
    for name, passed, detail in _RESULTS:
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
        if not passed:
            print(f"      {detail}")
    passed_count = sum(1 for _, passed, _ in _RESULTS if passed)
    print(f"\n{passed_count}/{len(_RESULTS)} passed")
    return 0 if passed_count == len(_RESULTS) else 1


class FakeDetectionArray:
    """Duck-typed stand-in for ``np.ndarray``.

    numpy is not a dependency of the root project, but ``_safe_repr`` only looks for ``shape``
    and ``dtype``, so this is enough to drive its array-summarizing branch.
    """

    def __init__(self, shape: tuple[int, ...], dtype: str) -> None:
        self.shape = shape
        self.dtype = dtype

    def __repr__(self) -> str:
        """Return a short stand-in for real array contents.

        Returns:
            str: Fixed text standing in for the array's values.
        """
        return "FakeDetectionArray([[1, 2], [3, 4]])"


def _make_log_record(level: int, message: str) -> logging.LogRecord:
    """Build a synthetic record so a handler can be formatted without emitting anything.

    Args:
        level: Numeric level for the record.
        message: Record message.

    Returns:
        logging.LogRecord: Record suitable for passing to ``Handler.format``.
    """
    return logging.LogRecord(
        name=LOGGER_NAME,
        level=level,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def _console_handler() -> ConsoleHandler:
    """Return the console handler attached to the module logger.

    Returns:
        ConsoleHandler: The logger's one console handler.
    """
    return next(h for h in LOGGER.handlers if isinstance(h, ConsoleHandler))


def _file_handlers() -> list[CustomFileHandler]:
    """Return the file handlers attached to the module logger.

    Returns:
        list[CustomFileHandler]: The per-logger handler and the aggregate ``all.log`` handler.
    """
    return [h for h in LOGGER.handlers if isinstance(h, CustomFileHandler)]


# --------------------------------------------------------------------------------------
# Unit checks: _safe_repr
# --------------------------------------------------------------------------------------


def test_safe_repr_passes_short_values_through() -> None:
    """A value that fits under the limit is rendered as its plain repr."""
    assert _safe_repr("enemy") == "'enemy'", _safe_repr("enemy")
    assert _safe_repr(118) == "118", _safe_repr(118)


def test_safe_repr_truncates_long_values() -> None:
    """A value over the limit is cut at the limit and tagged with the dropped count."""
    long_text = "x" * (TRACE_REPR_LIMIT + 50)
    full = repr(long_text)
    rendered = _safe_repr(long_text)
    assert rendered == f"{full[:TRACE_REPR_LIMIT]}...(+{len(full) - TRACE_REPR_LIMIT})", rendered
    assert len(rendered) < len(full), "truncated text should be shorter than the full repr"


def test_safe_repr_collapses_whitespace_to_one_line() -> None:
    """Newlines and runs of indentation are collapsed so a record stays on one line."""
    rendered = _safe_repr("first line\n    second line")
    assert "\n" not in rendered, rendered
    assert "  " not in rendered, rendered
    assert rendered == "'first line\\n second line'", rendered


def test_safe_repr_summarizes_oversized_arrays() -> None:
    """An array-like with more than TRACE_ARRAY_MAX_ELEMENTS entries is described, not dumped."""
    frame = FakeDetectionArray(shape=(640, 640), dtype="uint8")
    assert TRACE_ARRAY_MAX_ELEMENTS < 640 * 640, "test fixture must exceed the element cap"
    rendered = _safe_repr(frame)
    assert rendered == "<FakeDetectionArray shape=(640, 640) dtype=uint8>", rendered


def test_safe_repr_keeps_small_array_contents() -> None:
    """An array-like under the element cap falls through to its real repr."""
    corners = FakeDetectionArray(shape=(2, 2), dtype="int32")
    rendered = _safe_repr(corners)
    assert rendered == "FakeDetectionArray([[1, 2], [3, 4]])", rendered


# --------------------------------------------------------------------------------------
# Unit checks: _format_frame_locals
# --------------------------------------------------------------------------------------


def test_frame_locals_filters_modules_and_dunders() -> None:
    """Ordinary locals are rendered; imported modules and dunder names are dropped."""
    frame_id = 118
    module_local = logging
    __hidden_local = "secret"
    rendered = _format_frame_locals(sys._getframe())

    assert rendered.startswith("{") and rendered.endswith("}"), rendered
    assert "frame_id=118" in rendered, rendered
    assert "module_local" not in rendered, rendered
    assert "__hidden_local" not in rendered, rendered

    # Read the locals by name too, so they are not merely dead assignments.
    assert frame_id == 118
    assert module_local is logging
    assert __hidden_local == "secret"


# --------------------------------------------------------------------------------------
# Unit checks: _format_call_with_locals
# --------------------------------------------------------------------------------------


def _innermost_trail_capture(max_depth: int) -> str:
    """Capture the caller trail from the deepest layer of the test stack.

    Args:
        max_depth: Maximum number of caller frames to walk.

    Returns:
        str: The rendered call trail.
    """
    return _format_call_with_locals(sys._getframe(), max_depth)


def _middle_trail_layer(max_depth: int) -> str:
    """Call the innermost trail capture, adding one frame to the stack.

    Args:
        max_depth: Maximum number of caller frames to walk.

    Returns:
        str: The rendered call trail.
    """
    return _innermost_trail_capture(max_depth)


def _outer_trail_layer(max_depth: int) -> str:
    """Call the middle layer, adding a second frame to the stack.

    Args:
        max_depth: Maximum number of caller frames to walk.

    Returns:
        str: The rendered call trail.
    """
    return _middle_trail_layer(max_depth)


def test_call_trail_lists_callers_nearest_first() -> None:
    """The trail walks outward, nearest caller first, as ``file:qualname:line {locals}``."""
    entries = _outer_trail_layer(TRACE_MAX_STACK_DEPTH).split(" < ")

    assert len(entries) >= 2, entries
    assert entries[0].startswith(f"{MODULE_FILENAME}:_middle_trail_layer:"), entries[0]
    assert entries[1].startswith(f"{MODULE_FILENAME}:_outer_trail_layer:"), entries[1]
    assert re.search(r":\d+ \{", entries[0]), entries[0]
    assert "max_depth=" in entries[0], entries[0]


def test_call_trail_caps_depth_and_counts_the_rest() -> None:
    """With a depth cap, the trail stops and reports how many frames it skipped."""
    entries = _outer_trail_layer(1).split(" < ")

    assert len(entries) == 2, entries
    assert entries[0].startswith(f"{MODULE_FILENAME}:_middle_trail_layer:"), entries[0]
    assert re.fullmatch(r"\.\.\.\(\+\d+ frames?\)", entries[1]), entries[1]


def test_call_trail_reports_suppressed_frames_at_zero_depth() -> None:
    """A zero depth cap reports the frames it skipped rather than claiming the stack was empty."""
    trail = _outer_trail_layer(0)
    assert trail != "<top of stack>", "callers existed, so the trail must not claim otherwise"
    assert re.fullmatch(r"\.\.\.\(\+\d+ frames?\)", trail), trail


def test_call_trail_reports_top_of_stack_without_a_caller() -> None:
    """``<top of stack>`` is reserved for a frame that genuinely has no caller."""
    outermost = sys._getframe()
    while outermost.f_back is not None:
        outermost = outermost.f_back

    assert _format_call_with_locals(outermost, TRACE_MAX_STACK_DEPTH) == "<top of stack>"


# --------------------------------------------------------------------------------------
# Unit checks: handlers and logger wiring
# --------------------------------------------------------------------------------------


def test_console_handler_level_and_format() -> None:
    """The console handler sits at DEBUG and stamps ``time - LEVEL - message``."""
    handler = _console_handler()
    assert handler.level == DEBUG_LEVEL, handler.level
    formatted = handler.format(_make_log_record(logging.INFO, "hello"))
    assert re.fullmatch(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2} - INFO - hello", formatted), formatted


def test_console_handler_filters_trace_records() -> None:
    """TRACE is below the console threshold, so it is file-only."""
    handler = _console_handler()
    assert handler.level > TRACE_LEVEL, (TRACE_LEVEL, handler.level)
    assert _make_log_record(TRACE_LEVEL, "hidden").levelno < handler.level


def test_file_handlers_level_and_format() -> None:
    """Both file handlers sit at TRACE and share the console layout."""
    handlers = _file_handlers()
    assert len(handlers) == 2, [h.baseFilename for h in handlers]
    assert all(h.level == TRACE_LEVEL for h in handlers), [h.level for h in handlers]
    formatted = handlers[0].format(_make_log_record(TRACE_LEVEL, "deep"))
    assert re.fullmatch(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2} - TRACE - deep", formatted), formatted


def test_logger_is_the_custom_class_and_fully_wired() -> None:
    """``getLogger`` hands back a logging_config.Logger with all three handlers attached."""
    assert isinstance(LOGGER, Logger), type(LOGGER)
    assert callable(LOGGER.trace)
    assert LOGGER.level == TRACE_LEVEL, LOGGER.level
    assert LOGGER.propagate is False, "propagate must be off so records are not duplicated upward"
    assert len(LOGGER.handlers) == 3, LOGGER.handlers


def test_all_log_handler_is_shared_between_loggers() -> None:
    """Every logger appends to all.log through one handler, not one open stream each."""
    service_handlers = logging.getLogger(SERVICE_LOGGER_NAME).handlers
    all_handlers = [h for h in _file_handlers() if h.baseFilename.endswith("all.log")]
    service_all = [
        h
        for h in service_handlers
        if isinstance(h, CustomFileHandler) and h.baseFilename.endswith("all.log")
    ]
    assert len(all_handlers) == 1, all_handlers
    assert len(service_all) == 1, service_all
    assert all_handlers[0] is service_all[0], "each logger opened its own stream onto all.log"


def test_trace_level_name_is_registered() -> None:
    """``addLevelName`` mapped level 5 to the name TRACE."""
    assert logging.getLevelName(TRACE_LEVEL) == "TRACE"
    assert LOGGER.isEnabledFor(TRACE_LEVEL)


# --------------------------------------------------------------------------------------
# Demo: a mock service class plus three layers of nested calls
# --------------------------------------------------------------------------------------


class MockDetectorService:
    """Stand-in detection service, so the trace formatter has a real method frame to render.

    Exists to prove two things about ``Logger.trace``: that it reports a bound method as
    ``ClassName.method`` (from ``co_qualname``), and that ``self`` shows up in the locals dump.
    State is private with read-only properties, matching the playground's service pattern.
    """

    def __init__(self, threshold: float, robot_name: str) -> None:
        self._threshold = threshold
        self._robot_name = robot_name
        self._frames_seen = 0

    @property
    def threshold(self) -> float:
        """Return the confidence a detection must beat to count as a target.

        Returns:
            float: The configured confidence threshold.
        """
        return self._threshold

    @property
    def frames_seen(self) -> int:
        """Return how many frames have been handed to ``detect``.

        Returns:
            int: Count of frames processed so far.
        """
        return self._frames_seen

    def detect(self, frame_id: int, confidence: float) -> bool:
        """Record a frame and decide whether it holds a target.

        Args:
            frame_id: Identifier of the frame being processed.
            confidence: Detector confidence for this frame.

        Returns:
            bool: True if the detection cleared the threshold.
        """
        self._frames_seen += 1
        LOGGER.trace("inside a bound method")
        margin = confidence - self._threshold
        LOGGER.debug(f"{self._robot_name} frame {frame_id} margin {margin:.2f}")
        return margin > 0


def classify_target(label: str, confidence: float, threshold: float) -> bool:
    """Decide whether one detection clears the threshold (innermost demo layer).

    Args:
        label: Name of the detected class.
        confidence: Detector confidence for this detection.
        threshold: Confidence the detection must beat.

    Returns:
        bool: True if the detection cleared the threshold.
    """
    margin = confidence - threshold
    LOGGER.trace(TRACE_MARKER)
    return margin > 0


def process_frame(frame_id: int, threshold: float) -> bool:
    """Run one frame through classification (middle demo layer).

    Args:
        frame_id: Identifier of the frame being processed.
        threshold: Confidence a detection must beat.

    Returns:
        bool: True if the frame held a target.
    """
    label = "enemy"
    confidence = 0.87
    return classify_target(label, confidence, threshold)


def run_match_sequence(frame_ids: list[int], threshold: float) -> int:
    """Process a run of frames (outermost demo layer).

    Args:
        frame_ids: Identifiers of the frames to process.
        threshold: Confidence a detection must beat.

    Returns:
        int: Number of frames that held a target.
    """
    hits = 0
    for frame_id in frame_ids:
        if process_frame(frame_id, threshold):
            hits += 1
    return hits


def run_demo() -> None:
    """Fire all five levels through the real logger by way of the demo call layers."""
    print("=== DEMO (console shows DEBUG and above; TRACE is file-only) ===")

    LOGGER.info("Match starting")
    LOGGER.warning("No robots detected yet")
    LOGGER.error("Sensor feed dropped a frame")

    hits = run_match_sequence(list(DEMO_FRAME_IDS), threshold=0.5)
    LOGGER.info(f"{hits} targets detected")

    detector = MockDetectorService(threshold=0.5, robot_name="huey")
    detector.detect(frame_id=121, confidence=0.91)
    LOGGER.debug(f"detector saw {detector.frames_seen} frame(s) at threshold {detector.threshold}")

    log_service()


# --------------------------------------------------------------------------------------
# Output checks: read the demo's log files back off disk
# --------------------------------------------------------------------------------------


def _run_log_dir() -> Path:
    """Return the folder this run wrote its log files to.

    The path is relative because ``Logger.__init__`` creates it relative to the working directory.

    Returns:
        Path: ``logs/{RUN_NAME}`` for the current run.
    """
    return Path("logs") / logging_config.RUN_NAME


def _read_log(filename: str) -> str:
    """Read one of this run's log files.

    Args:
        filename: Name of the log file inside this run's folder.

    Returns:
        str: The file's full contents.
    """
    return (_run_log_dir() / filename).read_text(encoding="UTF-8")


def _find_trace_records(qualname: str) -> list[str]:
    """Return this run's trace records that were emitted from ``qualname``.

    Matching on the location segment rather than on the message matters: a trace record also
    dumps its callers' locals, so a marker string defined at module level shows up inside
    unrelated records too.

    Args:
        qualname: Qualified name of the function the records came from, e.g. ``ClassName.method``.

    Returns:
        list[str]: Matching lines, in the order they were logged.

    Raises:
        AssertionError: If no record matches.
    """
    prefix = f" - TRACE - {MODULE_FILENAME}:{qualname}:"
    matches = [line for line in _read_log(f"{LOGGER_NAME}.log").splitlines() if prefix in line]
    assert matches, f"no TRACE record logged from {qualname}"
    return matches


def flush_log_handlers() -> None:
    """Flush every handler so the files on disk are complete before they are read back."""
    for logger_name in (LOGGER_NAME, SERVICE_LOGGER_NAME):
        for handler in logging.getLogger(logger_name).handlers:
            handler.flush()


def test_run_folder_holds_a_file_per_logger_plus_all() -> None:
    """The run folder exists and contains one file per logger alongside the aggregate."""
    run_dir = _run_log_dir()
    assert run_dir.is_dir(), f"{run_dir} was not created"
    for filename in (f"{LOGGER_NAME}.log", f"{SERVICE_LOGGER_NAME}.log", "all.log"):
        assert (run_dir / filename).is_file(), f"missing {filename} in {run_dir}"


def test_every_level_reached_the_per_logger_file() -> None:
    """All five levels appear in the logger's own file, TRACE included."""
    contents = _read_log(f"{LOGGER_NAME}.log")
    for level_name in ("INFO", "WARNING", "ERROR", "DEBUG", "TRACE"):
        assert f" - {level_name} - " in contents, f"no {level_name} record in {LOGGER_NAME}.log"


def test_trace_record_reports_its_own_location() -> None:
    """A trace record names the file, function and line it was called from, then the message."""
    records = _find_trace_records("classify_target")
    assert len(records) == DEMO_FRAME_COUNT, f"expected one record per frame, got {len(records)}"

    location = records[0].split(" - TRACE - ", 1)[1].split(" | ", 1)[0]
    assert re.fullmatch(rf"{re.escape(MODULE_FILENAME)}:classify_target:\d+", location), location
    assert f"| {TRACE_MARKER} |" in records[0], records[0][:400]


def test_trace_record_captures_calling_frame_locals() -> None:
    """A trace record dumps the locals of the function that called it."""
    locals_section = _find_trace_records("classify_target")[0]
    locals_section = locals_section.split("locals: ", 1)[1].split(" | stack: ", 1)[0]
    for name in ("label=", "confidence=", "threshold=", "margin="):
        assert name in locals_section, f"{name} missing from {locals_section}"


def test_trace_record_walks_the_full_call_stack() -> None:
    """The stack trail lists the demo's layers outward, nearest caller first."""
    stack = _find_trace_records("classify_target")[0].split(" | stack: ", 1)[1]
    middle = f"{MODULE_FILENAME}:process_frame:"
    outer = f"{MODULE_FILENAME}:run_match_sequence:"

    assert middle in stack, stack[:400]
    assert outer in stack, stack[:400]
    assert stack.index(middle) < stack.index(outer), "callers must be listed nearest first"
    assert " < " in stack, stack[:400]


def test_trace_record_from_a_method_reports_the_qualified_name() -> None:
    """A trace call inside a method is located as ``ClassName.method`` and shows ``self``."""
    record = _find_trace_records("MockDetectorService.detect")[0]
    location = record.split(" - TRACE - ", 1)[1].split(" | ", 1)[0]
    expected = rf"{re.escape(MODULE_FILENAME)}:MockDetectorService\.detect:\d+"
    assert re.fullmatch(expected, location), location
    assert "self=<" in record, record[:400]


def test_service_log_holds_only_its_own_records() -> None:
    """A second logger gets its own file, and the detector's records stay out of it."""
    contents = _read_log(f"{SERVICE_LOGGER_NAME}.log")
    assert SERVICE_MARKER in contents, contents
    assert TRACE_MARKER not in contents, "records leaked across per-logger files"


def test_all_log_aggregates_both_loggers() -> None:
    """``all.log`` collects records from every logger in the run."""
    contents = _read_log("all.log")
    assert TRACE_MARKER in contents, "detector records missing from all.log"
    assert SERVICE_MARKER in contents, "service records missing from all.log"


UNIT_CHECKS: list[Callable[[], None]] = [
    test_safe_repr_passes_short_values_through,
    test_safe_repr_truncates_long_values,
    test_safe_repr_collapses_whitespace_to_one_line,
    test_safe_repr_summarizes_oversized_arrays,
    test_safe_repr_keeps_small_array_contents,
    test_frame_locals_filters_modules_and_dunders,
    test_call_trail_lists_callers_nearest_first,
    test_call_trail_caps_depth_and_counts_the_rest,
    test_call_trail_reports_suppressed_frames_at_zero_depth,
    test_call_trail_reports_top_of_stack_without_a_caller,
    test_console_handler_level_and_format,
    test_console_handler_filters_trace_records,
    test_file_handlers_level_and_format,
    test_logger_is_the_custom_class_and_fully_wired,
    test_all_log_handler_is_shared_between_loggers,
    test_trace_level_name_is_registered,
]

OUTPUT_CHECKS: list[Callable[[], None]] = [
    test_run_folder_holds_a_file_per_logger_plus_all,
    test_every_level_reached_the_per_logger_file,
    test_trace_record_reports_its_own_location,
    test_trace_record_captures_calling_frame_locals,
    test_trace_record_walks_the_full_call_stack,
    test_trace_record_from_a_method_reports_the_qualified_name,
    test_service_log_holds_only_its_own_records,
    test_all_log_aggregates_both_loggers,
]


def main() -> int:
    """Run the unit checks, then the demo, then verify what the demo wrote to disk.

    Returns:
        int: 0 if every check passed, 1 otherwise.
    """
    for check in UNIT_CHECKS:
        run_check(check)

    run_demo()
    flush_log_handlers()

    for check in OUTPUT_CHECKS:
        run_check(check)

    print(f"\nLog files for this run: {_run_log_dir()}")
    return print_summary()


if __name__ == "__main__":
    sys.exit(main())
