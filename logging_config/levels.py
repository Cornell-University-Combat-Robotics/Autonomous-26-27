"""Custom logging level numbers and their registration."""

# levels.py -- custom level numbers and their registration.
#
# PSEUDOCODE SKELETON.
#
# ---------------------------------------------------------------------------
# THE NUMBERS
# ---------------------------------------------------------------------------
# Stdlib, for reference:
#   CRITICAL 50 / ERROR 40 / WARNING 30 / INFO 20 / DEBUG 10 / NOTSET 0
#
# TRACE = 5
#   Sits between NOTSET and DEBUG; 5 is the de-facto convention.
#   NOTSET (0) is not usable as a real level -- it means "defer to my
#   parent" -- so nothing may be defined at 0.
#
# Define the number ONCE, here. No other module hardcodes 5.
#
# If more custom levels appear later, leave gaps (e.g. 15 between DEBUG
# and INFO) so a level can be inserted without renumbering its neighbours.
#
# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------
# def register() -> None:
#     # 1. logging.addLevelName(TRACE, "TRACE")
#     #    Installs the int -> str mapping the Formatter uses for
#     #    %(levelname)s. Without it every trace line renders "Level 5".
#     #    It also installs the reverse str -> int mapping, which is what
#     #    makes setLevel("TRACE") and a "TRACE" string in a config file
#     #    resolve at all.
#     #
#     # 2. Guard with a module-level _registered flag. addLevelName is
#     #    safe to repeat with the same pair, but a future non-idempotent
#     #    step added here must not be.
#     #
#     # 3. Do NOT add a module-level logging.trace() convenience function.
#     #    Module-level logging.* helpers act on the ROOT logger, which is
#     #    never a TraceLogger. Anything that looks like it works is a trap.
#
# ---------------------------------------------------------------------------
# HELPERS WORTH HAVING
# ---------------------------------------------------------------------------
# def level_to_int(name: str | int) -> int:
#     # Accepts "TRACE"/"DEBUG"/... or an int; returns the int. One place
#     # to parse whatever a config file or CLI flag hands us, so callers
#     # never write getattr(logging, name.upper()) -- that fails for
#     # TRACE, because logging.TRACE does not exist as a module attribute.
#     # logging.getLevelName(str) does the reverse lookup, but its
#     # two-way-function signature is a known wart; wrap it, don't spread it.
#
# LEVEL_CHOICES = ["NONE", "TRACE", "DEBUG", "INFO"]
#     # For argparse in config.parse_args(). "NONE" means "disable this
#     # sink entirely" and is NOT a logging level -- keep it out of any
#     # map that feeds setLevel().
#
# ---------------------------------------------------------------------------
# LEVEL SEMANTICS
# ---------------------------------------------------------------------------
# STYLE_GUIDE.md is authoritative. Summarised here only as a pointer:
#   TRACE  line-level execution tracing ("line X starting...", "done.")
#   DEBUG  why something might be misbehaving: timings, counts
#   INFO   essential at competition: initialization, per-frame results
# If the two drift, the style guide wins and this comment gets updated.
