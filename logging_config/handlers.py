"""Log record routing: deciding where each record is written."""

# handlers.py -- where records actually go.
#
# PSEUDOCODE SKELETON.
#
# Requirement: "specify where logs are getting saved for each, determined
# by a method call." In stdlib terms a destination IS a Handler, so the
# real question is whether the destination is chosen once at config time
# or per-record at emit time. Both shapes are below; pick the cheaper one
# that covers the need.
#
# ---------------------------------------------------------------------------
# A. THE GOTCHA THAT MAKES PER-LEVEL FILES NOT WORK NAIVELY
# ---------------------------------------------------------------------------
# handler.setLevel(TRACE) is a FLOOR (record.levelno >= handler.level),
# not an equality test. Because TRACE is the LOWEST level, a handler set
# to TRACE receives EVERY record in the system -- trace.log would contain
# all the INFO lines too.
#
# Level-exact routing needs a Filter:
#     class ExactLevel(logging.Filter):
#         # filter(record) -> record.levelno == self.level
# Attach one per level-specific handler. This is the single most common
# mistake when adding a level below DEBUG.
#
# ---------------------------------------------------------------------------
# B. RoutingHandler -- destination resolved by a method call, per record
# ---------------------------------------------------------------------------
# class RoutingHandler(logging.Handler):
#
#   def resolve_target(self, record) -> Path:
#       """Override point. Where should THIS record be written?"""
#       # The whole requested feature lives here. Subclass it, or inject a
#       # callable, so the policy is swappable without touching emit().
#       # One shape covers all of these uniformly:
#       #     per level    logs/{levelname.lower()}.log
#       #     per service  logs/{record.name.split('.')[0]}.log
#       #     per run      logs/{run_id}/main.log
#       #     per match    logs/{match_id}/trace.log      <- the robot case
#       # Keep it PURE and cheap: same record -> same path, and no I/O.
#
#   def emit(self, record) -> None:
#       # 1. path = self.resolve_target(record)
#       # 2. stream = self._streams.get(path), else open it:
#       #      mkdir(parents=True, exist_ok=True), line-buffered,
#       #      encoding="utf-8" explicitly (never the platform default)
#       # 3. stream.write(self.format(record) + self.terminator)
#       # 4. wrap the entire body in try/except and route failures to
#       #    self.handleError(record). A handler must NEVER raise into the
#       #    caller -- a full disk mid-match cannot be what stops the robot.
#
#   Concurrency: Handler.handle() already takes self.lock around emit(),
#   so the _streams dict needs no lock of its own. Do not add one, and do
#   not do slow work inside emit() while holding it (see D).
#
#   Lifecycle: you own every stream you open.
#     - close() closes them all, then calls super().close()
#     - logging.shutdown() closes handlers at exit, but only ones
#       registered in logging._handlerList -- confirm ours is, or add an
#       explicit atexit hook
#     - CAP the number of simultaneously open streams (LRU-close the
#       oldest) if resolve_target can produce unbounded distinct paths.
#       A per-frame path otherwise leaks descriptors until EMFILE.
#
# ---------------------------------------------------------------------------
# C. RESOLVED-ONCE ALTERNATIVE -- prefer this if it is enough
# ---------------------------------------------------------------------------
# If the destination depends only on the LEVEL and not on the record, you
# do not need RoutingHandler at all: build N plain FileHandlers at config
# time, each with an ExactLevel filter, each path computed by whatever
# method call you like. Cheaper, fully stdlib, nothing custom to maintain
# or to explain in a PR review.
# Reach for RoutingHandler only when the path genuinely varies per record
# (per run, per match, per frame).
#
# ---------------------------------------------------------------------------
# D. KEEPING I/O OFF THE HOT PATH
# ---------------------------------------------------------------------------
# Handler.emit runs synchronously on the calling thread. In the pipeline
# loop that is a disk write sitting between camera.read() and
# detector.detect().
#
#     logging.handlers.QueueHandler   -> the only handler on the loggers
#     logging.handlers.QueueListener  -> owns the real handlers, own thread
#
# The logger side then costs an enqueue. Two consequences to accept out
# loud rather than discover:
#   - records queued but not yet written are LOST on a hard kill (the
#     playground's ENQUEUE flag documents the same tradeoff for loguru)
#   - formatting happens later on another thread, which is precisely why
#     capture.py must stringify eagerly
# configure_logging() starts the listener; shutdown must stop it.
#
# ---------------------------------------------------------------------------
# E. ROTATION
# ---------------------------------------------------------------------------
# TRACE with locals capture produces a LOT of bytes. Either subclass
# RotatingFileHandler rather than Handler, or reimplement size-based
# rollover inside RoutingHandler. The playground uses 10 MB rotation and
# 7 day retention for loguru -- match those numbers unless there's a
# reason not to. Never rotate a file that multiple processes write.
