"""This file contains the methods to pick colors."""

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ColorPicker:
    """A class for manually picking colors from an image."""

    @staticmethod
    def pick_colors(image: np.ndarray) -> list[np.ndarray] | None:
        """Let the user click to pick the robot, front-corner, and back-corner colors.

        Click the robot first, then the front corner, then the back corner. Press 'z' to undo the
        last pick. After third click, one more is required to confirm. Press Esc to cancel.

        Args:
            image: BGR image to pick colors from, e.g. a warped arena frame.

        Returns:
            Three HSV colors (robot, front, back), each a uint8 array of [H, S, V]. Returns None if
            the user cancels with Esc, or an empty list if no image was given.
        """
        try:
            if image is None:
                raise FileNotFoundError(f"Image not found: {image}")
        except Exception as e:
            logger.warning(f"Error loading image: {e}")
            return []

        selected_colors = []
        points = []

        def click_event(event: int, x: int, y: int, flags: int, param: object | None) -> None:
            """Record the HSV color under a left-click and redraw the selection overlay.

            Args:
                event: OpenCV mouse event code (as an int).
                x: x-coordinate of the click, in window pixels.
                y: y-coordinate of the click, in window pixels.
                flags: Which mouse buttons and modifier keys (Ctrl/Shift/Alt) were held during the event (unused).
                param: User data from ``cv2.setMouseCallback`` (unused).
            """
            if event == cv2.EVENT_LBUTTONDOWN:
                if x < 0 or y < 0 or x >= image.shape[1] or y >= image.shape[0]:
                    logger.info(f"Clicked outside the image: ({x}, {y})")
                    return

                try:
                    color = image[y, x]  # OpenCV reads as BGR
                    hsv_color = cv2.cvtColor(np.uint8([[color]]), cv2.COLOR_BGR2HSV)[0][0]
                    if len(selected_colors) < 4:
                        selected_colors.append(hsv_color)
                        points.append([x, y])
                        logger.info(f"Selected color (HSV): {hsv_color}")
                        logger.info(f"Point added: {x}, {y}")
                        redraw_image()
                except Exception as e:
                    logger.warning(f"Error processing color at ({x}, {y}): {e}")

        def redraw_image() -> None:
            """Redraw the picker window with the current selections."""
            img_copy = image.copy()
            for point in points:
                cv2.circle(img_copy, point, 5, (0, 255, 0), -1)
                cv2.putText(
                    img_copy, f"{point}", point, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1
                )

            # Create a display panel for selected colors
            color_panel_height = img_copy.shape[0]
            color_panel_width = 150
            color_panel = np.zeros((color_panel_height, color_panel_width, 3), dtype=np.uint8)

            labels = ["Robot", "Front", "Back"]

            for i, hsv_color in enumerate(selected_colors):
                bgr_color = cv2.cvtColor(np.uint8([[hsv_color]]), cv2.COLOR_HSV2BGR)[0][0]
                start_y = i * (color_panel_height // 3)
                end_y = (i + 1) * (color_panel_height // 3)
                color_panel[start_y:end_y, :] = bgr_color

                cv2.putText(
                    color_panel,
                    labels[i],
                    (10, start_y + 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                )

            combined_image = np.hstack((img_copy, color_panel))
            cv2.imshow(
                "Color Picking: Pick Huey color, front corner, then back corner. Press 'z' to cancel previous selection. Once 3 colors are selected, press anywhere on the screen to continue",
                combined_image,
            )

        cv2.imshow(
            "Color Picking: Pick Huey color, front corner, then back corner. Press 'z' to cancel previous selection. Once 3 colors are selected, press anywhere on the screen to continue",
            image,
        )
        cv2.setMouseCallback(
            "Color Picking: Pick Huey color, front corner, then back corner. Press 'z' to cancel previous selection. Once 3 colors are selected, press anywhere on the screen to continue",
            click_event,
        )

        while True:
            key = cv2.waitKey(1) & 0xFF

            if key == ord("z"):  # Undo last selection
                if selected_colors and points:
                    removed_color = selected_colors.pop()
                    removed_point = points.pop()
                    logger.info(f"🛑 Color removed: {removed_color}")
                    logger.info(f"🛑 Point removed: {removed_point}")
                    redraw_image()
                else:
                    logger.info("⚠ No points to remove.")
            elif key == 27:  # Press 'Esc' to exit without saving
                logger.info("❌ Selection canceled. Exiting...")
                selected_colors = []
                return None
            elif len(selected_colors) == 4:
                selected_colors = selected_colors[: len(selected_colors) - 1]
                logger.info(f"🎨 Final Selected Colors (HSV): {selected_colors}")
                logger.info(f"📌 Final Selected Points: {points}")
                break

        cv2.destroyAllWindows()
        return selected_colors

    @staticmethod
    def save_colors_to_file(colors: list[np.ndarray], output_file: str) -> None:
        """Saves the selected colors to a text file in HSV format.

        Args:
            colors: List of HSV colors to be saved.
            output_file: Path to the output file.
        """
        try:
            with open(output_file, "w") as file:
                for color in colors:
                    file.write(f"{color[0]}, {color[1]}, {color[2]}\n")
            logger.info(f"Selected colors have been saved to '{output_file}'.")
        except FileNotFoundError:
            logger.warning(f"Error: Output file path '{output_file}' does not exist.")
        except Exception as e:
            logger.warning(f"Error saving colors to file: {e}")

    @staticmethod
    def make_new_colors(output_file_path: str, warped_frame: np.ndarray) -> list[np.ndarray] | None:
        """Pick colors interactively, save them to a file, and return them.

        Args:
            output_file_path: Path to write the colors file to, one "H, S, V" line per color.
            warped_frame: Warped BGR arena frame to pick colors from.

        Returns:
            Three HSV colors (robot, front, back), each a uint8 array of [H, S, V]. Returns None if
            the user cancels with Esc, or an empty list if no frame was given.
        """
        selected_colors = ColorPicker.pick_colors(warped_frame)
        ColorPicker.save_colors_to_file(selected_colors, output_file_path)
        return selected_colors


def display_colors(selected_colors: list) -> None:
    """Displays the selected colors as colored blocks in the HUD.

    Args:
        selected_colors: HSV colors in robot, front, back order, each [H, S, V].
    """
    if not selected_colors:
        logger.info("No colors selected to display.")
        return

    try:
        # Convert HSV colors to BGR and create a blank image to show them
        bgr_colors = [
            cv2.cvtColor(np.uint8([[color]]), cv2.COLOR_HSV2BGR)[0][0] for color in selected_colors
        ]

        height = 175
        width = 175
        img = np.zeros(
            (height, width * len(bgr_colors), 3), dtype=np.uint8
        )  # TODO: 4 color channels?

        for idx, color in enumerate(bgr_colors):
            img[:, idx * width : (idx + 1) * width] = color

            label = ""
            if idx == 0:
                label = "Robot Color"
            elif idx == 1:
                label = "Front Corner"
            elif idx == 2:
                label = "Back Corner"

            cv2.putText(
                img,
                label,
                (idx * width + 10, height - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

        cv2.imshow("Selected Colors", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    except Exception as e:
        logger.warning(f"Error displaying colors: {e}")
