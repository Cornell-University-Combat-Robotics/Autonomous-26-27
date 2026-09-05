"""Call-site, in-scope-variable, and context capture for TRACE records."""

# capture.py -- builds the TRACE payload: call site, in-scope variables,
# and the rest of the per-record context.
#
# PSEUDOCODE SKELETON.
#
# Highest-risk module in the package. Everything here runs inside a log
# call, so a bug breaks logging itself rather than producing a bad line.
#
# ---------------------------------------------------------------------------
# snapshot(...) -> dict
# ---------------------------------------------------------------------------
# Called by TraceLogger.trace() AFTER the isEnabledFor guard. Returns a
# plain dict of already-stringified values. Never returns live objects.
#
# ---------------------------------------------------------------------------
# 1. FINDING THE CALLER'S FRAME
# ---------------------------------------------------------------------------
# Do NOT use a fixed number of f_back hops. A decorator, context manager,
# or any helper wrapping trace() silently shifts the count and you capture
# the wrapper's variables instead of the caller's.
#
# Do what findCaller does: start at sys._getframe() and walk up while
# frame.f_code.co_filename belongs to THIS package. Precompute that set of
# filenames once at import (logging calls its equivalent _srcfile).
# Comparing strings per hop is fine; importing inspect and building
# FrameInfo objects per call is not -- inspect.stack() in particular
# reads source files for every frame and is orders of magnitude too slow.
#
# Also stop at a hop limit (say 20) so a pathological stack can't spin,
# and handle frame is None (possible on non-CPython / optimized builds).
#
# ---------------------------------------------------------------------------
# 2. WHAT ACTUALLY NEEDS THE FRAME
# ---------------------------------------------------------------------------
# Already free on the LogRecord once stacklevel is right -- do NOT
# duplicate these into the payload:
#     pathname, filename, module, funcName, lineno,
#     thread, threadName, process, created
#
# Genuinely needs the frame:
#   a. in-scope variables (frame.f_locals)
#   b. the QUALIFIED function name (co_qualname). record.funcName is
#      unqualified, so Camera.read and Detector.read look identical.
#   c. optionally the source line text (linecache.getline), which makes
#      "line X starting..." traces readable without opening the file.
#      linecache caches, so it is cheaper than it looks -- but it holds
#      whole file contents in memory.
#
# ARGUMENTS vs ALL LOCALS -- decide before implementing:
#   frame.f_code.co_varnames[:co_argcount] gives just the parameters.
#   Bounded, stable, and usually what people actually wanted.
#   All of f_locals is unbounded and GROWS as the function runs, so the
#   same trace line yields different fields depending where it sits.
#   Suggested default: arguments only; all locals behind an explicit flag.
#
# ---------------------------------------------------------------------------
# 3. THE COST (why step 1 of trace() is a hard guard)
# ---------------------------------------------------------------------------
# On CPython < 3.13, reading f_locals on an optimized (function) frame
# materializes a FRESH dict on every access. On 3.13+ (PEP 667) it is a
# write-through proxy -- cheaper, different aliasing, still not free.
# This repo runs 3.13.12 for dev but ruff targets py311 for the robot
# interpreter, so BOTH behaviours may be live. Don't depend on either
# one's aliasing semantics: read f_locals exactly once, bind it to a
# local, snapshot, move on.
#
# ---------------------------------------------------------------------------
# 4. SAFE STRINGIFICATION -- non-negotiable
# ---------------------------------------------------------------------------
# def safe_repr(value) -> str:
#   - wrap repr() in try/except BaseException. repr() is arbitrary user
#     code: it can raise, block, or have side effects. An exception here
#     kills the log call, which kills whatever was being traced. On
#     failure return e.g. "<repr failed: TypeError>".
#   - cap length per value (~200 chars) and mark truncation. reprlib
#     exists for exactly this and avoids building the full string first.
#   - TYPE-AWARE summaries before falling back to repr:
#       np.ndarray -> "ndarray(shape=(480,640,3), dtype=uint8)", not contents
#       datatypes/ messages (Frame, DetectionResult) -> frame_id + shape,
#         never the pixel buffer
#       long list/dict -> first N items + "... (N more)"
#     Without this, one trace call in the camera loop writes megabytes.
#   - cap the NUMBER of variables per record too, not just each one.
#
# ---------------------------------------------------------------------------
# 5. REDACTION -- a hard default, not an option
# ---------------------------------------------------------------------------
# Locals are exactly where credentials live, and this repo already talks
# to Box and Roboflow, so tokens will be in scope somewhere.
#   - denylist by variable NAME, case-insensitive substring:
#       key, token, secret, password, passwd, credential, auth,
#       cookie, session, signature
#     Replace the value with "<redacted>".
#   - match on the NAME, never the value. You cannot reliably detect a
#     secret by looking at it, and trying means reading every value.
#   - redact BEFORE stringification, so a secret is never even repr'd.
#   - keep the denylist here as a module constant, reviewable in one
#     place. Make it extendable by config, not replaceable.
#   - README should still say trace logs are not safe to paste publicly.
#     This is defence in depth, not a guarantee.
#
# ---------------------------------------------------------------------------
# 6. "A NUMBER OF OTHER FACTORS" -- the rest of the context
# ---------------------------------------------------------------------------
# Ethan: this list is the thing to argue about, not my guesses. Candidates
# that are cheap and specifically useful for this pipeline:
#
#   - frame_id of the pipeline frame being processed. CLAUDE.md says
#     frame_id is carried through every stage; a ContextVar set once per
#     loop iteration in main.py makes every trace line anywhere
#     attributable to a frame without threading it through signatures.
#     Probably the single highest-value field here.
#   - a monotonic timestamp (time.perf_counter_ns) alongside the wall
#     clock. record.created is wall time and useless for latency.
#   - a per-run id, so separate runs appended to one file stay separable.
#   - elapsed time since this logger's previous trace call -- what turns
#     "starting..."/"done." pairs into free timings.
#   - thread/task name once the pipeline goes concurrent (already on the
#     record -- do not duplicate).
#
# Use ContextVar over threading.local: works for threads and asyncio, and
# reads are cheap.
#
# ---------------------------------------------------------------------------
# 7. WHAT MUST NEVER GO IN THE PAYLOAD
# ---------------------------------------------------------------------------
# - the frame object. Holding it keeps every local alive and can create
#   reference cycles through the traceback machinery.
# - live references of any kind. Values mutate between capture and
#   format, and with a QueueListener formatting happens much later on
#   another thread.
# - anything already on the LogRecord (section 2).
