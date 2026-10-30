"""CSV state logging and a mouse-driven object detection stand-in for testing Ram Ram."""

import csv
import logging
import os
import time
from tkinter import Event, Tk

import numpy as np

logger = logging.getLogger(__name__)

cursor_pos = None
fpath = None
fields = [
    "time",
    "delta_time",
    "bots",
    "huey_pos",
    "huey_facing",
    "enemy_pos",
    "huey_old_pos",
    "huey_velocity",
    "enemy_old_pos[-1]",
    "enemy_velocity",
    "speed",
    "turn",
    "left_speed",
    "right_speed",
    "angle",
    "direction",
]


class NoEnemyError(Exception):
    """Raised when no enemy is detected."""


def obj_detection_sim(width: int, height: int) -> None:
    """Open a tkinter window whose mouse position stands in for the enemy's detected position.

    The cursor position is normalized to [-1, 1] on both axes and stored in the module-level
    ``cursor_pos``; it is set to None when the cursor is in the top or bottom 20% of the window.

    Args:
        width: Window width in pixels.
        height: Window height in pixels.
    """
    # Create an instance of tkinter frame or window
    win = Tk()
    # Set the geometry of tkinter frame
    win.geometry(str(width) + "x" + str(height))

    def callback(e: Event) -> None:
        global no_enemy
        x = e.x
        y = e.y
        # For simulation, default is width = 640, height is 360
        # logger.debug("Pointer is currently at %d, %d" %(x,y))
        global cursor_pos
        if (y > (height * 0.8)) or (y < (height * 0.2)):
            cursor_pos = None
        else:
            cursor_pos = ((x - (width / 2)) / (width / 2), ((y - (height / 2)) / (-height / 2)))
        # logger.debug(cursor_pos)

    win.bind("<Motion>", callback)
    win.mainloop()


def test_file_init() -> None:
    """Establish a new test file for saving states of Ram Ram.

    Creates the next unused ``RamRamTest/ram_ram_test{i}.csv``, writes the header row, and stores
    its path in the module-level ``fpath``.

    NOTE: run this from Autonomous-23-24 or the things will not save in the right place
    """
    global fpath
    if "algorithm" in str(os.getcwd()):
        test_dir = os.path.join(os.getcwd(), os.path.join("RamRamTest"))
    else:
        test_dir = os.path.join(os.getcwd(), os.path.join("algorithm", "RamRamTest"))
    i = 0

    # remember to join the entire file path
    while os.path.exists(os.path.join(test_dir, f"ram_ram_test{i}.csv")):
        i += 1
    fpath = os.path.join(test_dir, f"ram_ram_test{i}.csv")
    # logger.debug(fpath)
    with open(fpath, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()


def test_file_update(
    delta_time: float | None = None,
    bots: dict | None = None,
    huey_pos: np.ndarray | None = None,
    huey_facing: float | None = None,
    enemy_pos: np.ndarray | None = None,
    huey_old_pos: np.ndarray | None = None,
    huey_velocity: np.ndarray | None = None,
    enemy_old_pos: np.ndarray | None = None,
    enemy_velocity: np.ndarray | None = None,
    speed: float | None = None,
    turn: float | None = None,
    left_speed: float | None = None,
    right_speed: float | None = None,
    angle: float | None = None,
    direction: int | None = None,
) -> None:
    """Append one row of Ram Ram state to the test file, creating the file first if needed.

    Every value is written with ``str()``, so an omitted field is recorded as ``None``.

    To add a field: add it to ``fields`` at the top, add it as an argument, and add it to the dict
    at the end.

    Args:
        delta_time: Time since the previous update.
        bots: Detection dictionary for huey and the enemy.
        huey_pos: Huey's current center.
        huey_facing: Huey's orientation.
        enemy_pos: Enemy's current center.
        huey_old_pos: Huey's previous center.
        huey_velocity: Huey's velocity.
        enemy_old_pos: Enemy's most recent previous center.
        enemy_velocity: Enemy's velocity.
        speed: Commanded speed.
        turn: Commanded turn.
        left_speed: Left motor speed.
        right_speed: Right motor speed.
        angle: Error angle to the enemy.
        direction: Arena-edge escape direction.
    """

    if fpath is None:
        test_file_init()

    with open(fpath, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        update_dict = {
            "time": time.strftime("%H:%M:%S", time.localtime()),
            "delta_time": str(delta_time),
            "bots": str(bots),
            "huey_pos": str(huey_pos),
            "huey_facing": str(huey_facing),
            "enemy_pos": str(enemy_pos),
            "huey_old_pos": str(huey_old_pos),
            "huey_velocity": str(huey_velocity),
            "enemy_old_pos[-1]": str(enemy_old_pos),
            "enemy_velocity": str(enemy_velocity),
            "speed": str(speed),
            "turn": str(turn),
            "left_speed": str(left_speed),
            "right_speed": str(right_speed),
            "angle": str(angle),
            "direction": str(direction),
        }
        writer.writerow(update_dict)
