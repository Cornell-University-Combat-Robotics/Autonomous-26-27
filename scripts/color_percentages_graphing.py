"""Graphs the color percentages of the detected bots for the most recently ran video.

The highest percentage bot is represented by the blue line and the second highest percentage bot by the orange line.
The green line represents the color-percentage detection threshold defined in corner detection.
"""

import logging

import matplotlib.pyplot as plt
import pandas as pd

logger = logging.getLogger(__name__)


def makeGraph() -> None:
    """Plots each column of color_output.csv as a line of color percentage over frame number.

    Reads color_output.csv from the current working directory and logs some quick stats about the
    data at DEBUG level. Each column gets its own color, drawn as a solid line with a lighter dotted
    line on top. The graph is saved as color_percentage_graph.png in the current working directory 
    and then shown in a window.

    Returns:
        None

    Raises:
        FileNotFoundError: If color_output.csv is not in the current working directory.
    """
    df = pd.read_csv("color_output.csv", index_col=0)
    # df = pd.read_csv("ColorPercentageData.csv")

    # Log diagnostic information

    logger.debug(f"Column names: {df.columns.tolist()}")
    logger.debug(f"Data shape: {df.shape[0]} rows, {df.shape[1]} columns")
    logger.debug("\nFirst 10 rows:")
    logger.debug(df.head(10))
    logger.debug("\nData statistics:")
    logger.debug(df.describe())
    logger.debug("\nAny null values?")
    logger.debug(df.isnull().sum())
    logger.debug("\nMin and max values per column:")
    logger.debug(f"Huey: min={df.iloc[:, 0].min()}, max={df.iloc[:, 0].max()}")
    logger.debug(f"Enemy: min={df.iloc[:, 1].min()}, max={df.iloc[:, 1].max()}")
    # Create figure and axis
    fig, ax = plt.subplots(figsize=(12, 6))

    # Define color pairs for each column (two distinct colors per column)
    color_pairs = [
        ("#1f77b4", "#aec7e8"),  # Blue pair
        ("#ff7f0e", "#ffbb78"),  # Orange pair
        ("#2ca02c", "#98df8a"),  # Green pair
        ("#d62728", "#ff9896"),  # Red pair
        ("#9467bd", "#c5b0d5"),  # Purple pair
        ("#8c564b", "#c49c94"),  # Brown pair
        ("#e377c2", "#f7b6d2"),  # Pink pair
        ("#7f7f7f", "#c7c7c7"),  # Gray pair
    ]
    # Plot each column as a single distinct line
    for i, column in enumerate(df.columns):
        # Get color pair (use first color as main line, second as alternate)
        color1, color2 = color_pairs[i % len(color_pairs)]

        # Create x-axis values (row indices)
        x = range(len(df))
        y = df[column]

        # Plot one line per column with distinct color
        ax.plot(x, y, color=color1, linewidth=2.5, label=column)

        # Add a second overlay line with different style for visual interest
        ax.plot(x, y, color=color2, linewidth=1, linestyle=":", alpha=0.8)

    # Customize the plot
    ax.set_xlabel("Frame Number", fontsize=12)
    ax.set_ylabel("Percentage", fontsize=12)
    ax.set_title("Color Percentage Data Visualization", fontsize=14, fontweight="bold")
    ax.set_ylim(0, 1.0)  # expanded from 0.5
    # ax.set_xlim(0, 1000)
    ax.set_xticks(
        [i * 50 for i in range(len(df) // 50 + 2)]
    )  # dynamically fits however many frames you have
    ax.set_yticks([i * 0.05 for i in range(21)])  # 0, 0.05, 0.10, ..., 1.0 (finer granularity)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.2f}"))
    ax.grid(True, alpha=0.3)

    # Adjust layout
    plt.tight_layout()

    # Save the figure
    plt.savefig("color_percentage_graph.png", dpi=300, bbox_inches="tight")

    # Display the plot
    plt.show()

    logger.info("\nGraph created successfully!")


makeGraph()