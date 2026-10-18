import numpy as np
from typing import Any
import math

BACK_UP_SPEED = -1
BACK_UP_TURN = 0
FORWARD_SPEED = 1
FORWARD_TURN = 0
LEFT_SPEED = 1
LEFT_TURN = -1
RIGHT_SPEED = 1
RIGHT_TURN = 1
ARENA_WIDTH = 700


def invert_y(pos: np.ndarray) -> np.ndarray:
    """
    Inverts y position, does not mutate pos.

    Args:
        pos: Position to be inverted

    Returns:
        np.ndarray: copy of pos with y inverted
    """
    pos2 = np.copy(pos)
    pos2[1] = -pos[1]
    return pos2


def check_wall(predicted_position: np.ndarray) -> None:
    """
    If enemy robot predicted position is outside of arena, mutates
    predicted position to be inside.

    Args:
        predicted_position: Array of where we think the robot is

    Returns:
        None: Just mutates predicted_position
    """
    if predicted_position[0] > ARENA_WIDTH:
        predicted_position[0] = ARENA_WIDTH
    if predicted_position[0] < 0:
        predicted_position[0] = 0
    if predicted_position[1] > ARENA_WIDTH:
        predicted_position[1] = ARENA_WIDTH
    if predicted_position[1] < 0:
        predicted_position[1] = 0


def clamp(x: int | float, lo: int | float, hi: int | float) -> int | float:
    """
    Basic clamp function, bounding x between lo and hi.

    Args:
        x: number to be bounded
        lo: lower bound
        hi: upper bound

    Returns:
        int | float: x bounded by lo and hi
    """
    return max(lo, min(hi, x))


def to_float(x: Any, fallback: float = 0.0) -> float:
    """
    Convert x to float, if x can't be converted, then return fallback.

    Args:
        x: Value to be converted to float.

    Returns:
        float: If x can be converted to float, then x. Otherwise, returns fallback.
    """
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return float(fallback)
        return v
    except Exception:
        return float(fallback)


def mix_speed_turn(speed: float, turn: float) -> tuple[float, float]:
    """
    Mix forward speed and turn into left/right motor speeds

    Args:
        speed: how quickly to go foward (and what direction)
        turn: how quickly to turn (and what direction)

    Returns:
        tuple[float, float]: left motor speed and right motor speed (in that order)
    """
    # symmetric, safe motor mixing
    left = clamp(speed - turn, -1, 1)
    right = clamp(speed + turn, -1, 1)
    return left, right


def init_values(bots: dict, arena_width: int, is_pos: bool, is_huey: bool) -> float | np.ndarray:
    """
    Initialize a bot's position or orientation from detected values

    Args:
        bots: Dictionary of huey and enemy bots, each with bbox and center and other things.
        arena_width: The width of the arena measured in pixels.
        is_pos: Whether we are initializing position or orientation.
        is_huey: Whether the bot desired for init values is huey (as opposed to enemy).

    Returns:
        value: The position (np.ndarray) or orientation (float) that we are setting
    """
    if is_huey:
        if is_pos:  # Huey Position
            value = np.array(
                bots["huey"]["center"]
                if np.array(bots["huey"]["center"]) is not None
                else (arena_width / 2, arena_width / 2),
                dtype=float,
            )
        else:  # Orientation
            value = float(
                bots["huey"]["orientation"] if bots["huey"]["orientation"] is not None else 0.0
            )
    else:
        if is_pos:
            value = np.array(
                bots["enemy"]["center"] if bots["enemy"]["center"] is not None else (0.0, 0.0),
                dtype=float,
            )
        else:
            value = 0.0
    return value
