"""DEPRECATED: This is not part of the main loop, and is for visualization purposes.

Script to visualize RamRam data: orientation, speed, etc.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# filepath for CSV input
CSV = "RamRamTest/ram_ram_test101.csv"


def plot_velocity(df: pd.DataFrame) -> None:
    """Plots robot's speed data vs time with 2 lines: one line is the calculated speed from Ram, the other line is the actual bot's logged speed.

    Args:
        df: dataframe containing bot's data on orientation, speed, etc.

    Returns:
        None: Creates a plot
    """
    # Create a copy of the dataframe for plotting
    plot_df = df.copy()
    column_list = plot_df["huey_velocity"].tolist()
    plot_df["row_number"] = np.arange(len(plot_df))

    result = []
    for item in column_list:
        coords = item.strip("[]").split()
        coords_list = ((float(coords[0]) ** 2 + float(coords[1]) ** 2) ** 0.5) / 200
        result.append(coords_list)

    plot_df["huey_velocity"] = result

    plot_df_filtered = plot_df.iloc[5:, :]

    # Plot with the filtered data
    plot_df_filtered.plot("row_number", y=["speed", "huey_velocity"])


def plot_turn(df: pd.DataFrame) -> None:
    """Plots robot's turn data with 2 lines: one line is the calculated turn data from Ram, the other line is the frame-to-frame difference in the robot's logged orientation.

    Args:
        df: dataframe containing bot's data on orientation, speed, etc.

    Returns:
        None: Creates a plot
    """
    turn = df["turn"].tolist()
    facing = df["huey_facing"].tolist()
    df["row_number"] = np.arange(len(df))

    dfacing = []

    for i in range(len(facing) - 1):
        diff = facing[i + 1] - facing[i]
        diff = (diff + 180) % 360 - 180
        dfacing.append(diff)

    for i in range(len(turn)):
        turn[i] = turn[i] * 180

    dfacing.append(diff)

    df["facing_diff"] = dfacing
    df["turn"] = turn

    df.plot("row_number", y=["turn", "facing_diff"])


fields = ["time", "huey_velocity", "speed", "huey_facing", "turn"]
df = pd.read_csv(CSV, skipinitialspace=True, usecols=fields)
plot_turn(df)
plot_velocity(df)
plt.xlabel("frame")
plt.show()
