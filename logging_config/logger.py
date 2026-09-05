"""TraceLogger: the logging.Logger subclass that provides .trace()."""

# logger.py -- the Logger subclass that provides .trace().
#
# PSEUDOCODE SKELETON.
#
# ---------------------------------------------------------------------------
# class TraceLogger(logging.Logger)
# ---------------------------------------------------------------------------
#
# def trace(self, msg, *args, **kwargs) -> None:
#     """Log at TRACE, capturing the call site and its in-scope variables."""
#
#     # STEP 1 -- CHEAP GUARD, FIRST.
#     #   if not self.isEnabledFor(TRACE): return
#     # Nothing above this line may touch a frame, build a dict, or format
#     # anything. This is the most important line in the file: the capture
#     # in step 2 is expensive, so with TRACE disabled the whole call must
#     # cost one integer comparison.
#     #
#     # isEnabledFor consults the logger's effective level and the global
#     # logging.disable() floor, but NOT handler levels -- a record can
#     # pass here and still be dropped by every handler.
#
#     # STEP 2 -- CAPTURE (capture.py). Eager, at call time. Never deferred
#     # to format time: the frame dies and the values mutate.
#     #   payload = capture.snapshot(...)
#
#     # STEP 3 -- EMIT.
#     #   self._log(TRACE, msg, args, extra=..., stacklevel=...)
#     # Use _log, not self.log(): self.log() re-validates the level and
#     # adds one more frame to correct for.
#
# ---------------------------------------------------------------------------
# STACKLEVEL -- the bug everyone ships
# ---------------------------------------------------------------------------
# Logger.findCaller walks up the stack skipping frames whose filename is
# logging's own source (its _srcfile). THIS module is not that file, so
# without correction findCaller stops at trace() and every record reports
# logger.py's filename and lineno instead of the real call site.
#
#   - Pass stacklevel through to _log. Baseline is 2: one for trace().
#   - If a caller supplies their own stacklevel (a helper wrapping
#     trace()), ADD to it, never overwrite:
#       stacklevel = kwargs.pop("stacklevel", 1) + 1
#   - Every wrapper layer added later must bump this. If capture.py and
#     the LogRecord ever disagree about the call site, this is why.
#   - Write a test asserting record.funcName == the calling test
#     function's name. It is the only way this stays correct.
#
# ---------------------------------------------------------------------------
# makeRecord OVERRIDE -- how the captured payload rides along
# ---------------------------------------------------------------------------
# def makeRecord(self, ...) -> logging.LogRecord:
#     # super().makeRecord(...), then attach the payload as ONE namespaced
#     # attribute, e.g. record.crc_trace = payload.
#     #
#     # Why one attribute instead of extra={"a": .., "b": ..}:
#     #   - logging RAISES KeyError when an extra key collides with an
#     #     existing LogRecord attribute (message, asctime, args, filename,
#     #     module, exc_info, ...). A dozen loose keys is a dozen chances
#     #     to collide with names we don't control.
#     #   - one namespaced attribute is trivially ignored by any formatter
#     #     that doesn't care about it.
#     #
#     # Set it to None (not absent) on non-TRACE records so formatters can
#     # test truthiness rather than hasattr().
#
# ---------------------------------------------------------------------------
# BRACE-STYLE MESSAGES -- unresolved, and it bites immediately
# ---------------------------------------------------------------------------
# STYLE_GUIDE.md mandates the lazy brace form:
#     logger.debug("camera: frame {} captured", frame.frame_id)
# That is LOGURU syntax. Stdlib LogRecord.getMessage() does `msg % args`,
# so with stdlib logging that call renders the literal text
# "camera: frame {} captured" and SILENTLY drops the argument -- no
# exception, just a wrong log line.
#
# Options, pick one and write it down:
#   (a) custom LogRecord subclass whose getMessage() uses str.format, and
#       have makeRecord() return it. Keeps every existing call site in the
#       playground valid. Note %-style callers then break, and any
#       third-party library logging through our root handlers still emits
#       %-style -- so getMessage() must try one and fall back.
#   (b) switch the whole repo to %-style and amend STYLE_GUIDE.md.
#   (c) a lazy wrapper object around the message that formats on demand.
# (a) is the least disruptive; it is also the reason makeRecord is being
# overridden anyway.
#
# ---------------------------------------------------------------------------
# WHAT DOES NOT BELONG IN THIS FILE
# ---------------------------------------------------------------------------
# - No I/O, no routing, no destination logic. trace() builds a record and
#   hands it off; where it lands is handlers.py's job. Keeping the method
#   dumb is exactly what lets one call site behave differently per
#   environment without touching the call site.
# - No repr() of captured values -- capture.py owns that, so redaction and
#   truncation live in exactly one reviewable place.
# - Do not override isEnabledFor() or handle(). Both are on the hot path
#   for every level, not just TRACE.
#
# ---------------------------------------------------------------------------
# LoggerAdapter
# ---------------------------------------------------------------------------
# LoggerAdapter does NOT inherit .trace() -- it proxies a fixed set of
# methods. If adapters get used anywhere, a matching TraceLoggerAdapter is
# needed. Decide before they spread; retrofitting is worse.
