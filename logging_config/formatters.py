"""Rendering of log records and their captured TRACE payload."""

# formatters.py -- turning a record (and its captured payload) into text.
#
# PSEUDOCODE SKELETON.
#
# Hard rule: formatters RENDER. They never capture, never call repr() on a
# live object, never touch a frame. By the time a record arrives here
# everything in the payload is already a safe, truncated, redacted string
# (capture.py). That is exactly what makes it correct to format on a
# QueueListener thread long after the call site returned.
#
# ---------------------------------------------------------------------------
# TraceFormatter -- human-readable
# ---------------------------------------------------------------------------
# def format(self, record) -> str:
#   # 1. base = super().format(record)   -> the normal one-line message
#   # 2. if not getattr(record, "crc_trace", None): return base
#   #    Non-TRACE records must be completely unaffected.
#   # 3. append the payload. Indented multi-line reads far better than one
#   #    enormous line:
#   #        09.05.26 14:22:03.481 | TRACE | camera:31 - camera: read starting...
#   #          @ Camera.read  camera/camera.py:31
#   #          frame_id=12  elapsed=1.4ms
#   #          self=<Camera 10x10>  pixels=ndarray(shape=(10,10), dtype=float64)
#   #    Multi-line breaks naive grep and line-oriented log parsers.
#   #    Decide which matters more for the team's workflow, and record the
#   #    choice here rather than leaving it to whoever edits next.
#   # 4. DETERMINISTIC field order (sorted, or an explicit priority list).
#   #    Dict order follows the function's locals, and unstable ordering
#   #    makes diffing two runs useless.
#
# Match the playground's console format so both projects read alike:
#     MM.DD.YY HH:mm:ss.SSS | LEVEL | name:line - message
# Note %(levelname)-5s fits TRACE/DEBUG/ERROR but not WARNING/CRITICAL --
# pick the column width deliberately.
#
# ---------------------------------------------------------------------------
# JsonTraceFormatter -- machine-readable
# ---------------------------------------------------------------------------
# Same payload as one JSON object per line, nested under its own key.
# Worth having early: it is what makes "which frame was slow" answerable
# with a script instead of by eye. Cheap, because the payload is already
# flat strings.
#
# ---------------------------------------------------------------------------
# NOTES
# ---------------------------------------------------------------------------
# - Formatter.format() mutates record.message and record.asctime. Sharing
#   ONE Formatter across handlers is fine, and so is two Formatters over
#   one record -- but never cache formatted output on the record itself.
# - record.getMessage() applies %-style args. STYLE_GUIDE.md mandates the
#   brace form logger.debug("... {} ...", x), which stdlib does NOT
#   support and drops SILENTLY. See logger.py, "BRACE-STYLE MESSAGES",
#   and README "Open decisions" -- this must be settled before anyone
#   writes call sites against it.
# - Colour only when the stream isatty(). Never write ANSI into a file.
