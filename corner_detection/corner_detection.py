"""Identifies Huey among the detected bots and finds its orientation from its corner colors."""

import logging
import os

import cv2
import numpy as np

from .corner_detection_helpers import (
    calc_diagonal_and_side_length,
    compute_angle_between_midpoints,
    compute_blackout_box,
    deque,
    find_centroids,
    find_our_bot,
    is_overlap,
    math,
    two_corners,
)

logger = logging.getLogger(__name__)


class RobotCornerDetection:
    """A class for detecting the corners and orientation of robots in images
    based on their unique colors and shapes.
    """

    LENGTH_BUFFER = 20

    def __init__(
        self,
        selected_colors: list[list[int]],
        display_final_image: bool = False,
        display_possible_hueys: bool = False,
        BLACKOUT: bool = True,
        thresh: float = 0.4,
        frame_rate: int = 120,
    ) -> None:
        """Initializes the RobotCornerDetection class.

        Args:
            bots : A list of dictionary containing information about the
                        bots, including bounding boxes and images. This is empty
                        for now when initialized before the match. There is a
                        setter that will run during the match.
            selected_colors (list): Manually selected colors for front and back corners.
            display_final_image (bool): Whether to display the final image with
                        labeled left and right corners.
            display_possible_hueys (bool): Whether to display all possible
                        images of Huey.
        """
        self.bots = []
        self.selected_colors = selected_colors
        self.display_final_image = display_final_image
        self.display_possible_hueys = display_possible_hueys
        self.huey_color_percentage_threshold = -1
        self.color_percentage_rows = []
        self.is_diagonal = False
        self.centroids = []

        # Note: These are actually floats/int but we need them to be mutable
        self.diag_len = []
        self.side_len = []
        self.num_lens = [0]
        self.frame_rate = frame_rate

        self.thresh = thresh
        self.BLACKOUT = BLACKOUT
        self.prev_flipped = 1  # track for two corner
        self.dynamic_threshold_window = (
            60  # frame_rate//2 # Time/Number of Frames for the dynamic threshold for FindOurBot
        )
        self.threshold_queue = deque(maxlen=self.dynamic_threshold_window)
        self.running_sum = 0  # running sum of midpoints for threshold logic

        self.corner_method = 0

    def set_bots(self, bots: dict) -> None:
        """Sets the bots to search for Huey on the next detection pass.

        Args:
            bots : The bots to search for Huey on the next detection pass
        """
        self.bots = bots

    def detect_our_robot_main(self, bot_images: list[np.ndarray], threshold_set=True) -> np.ndarray:
        """Detects the image containing our robot between two or more given images.

        Args:
            bot1_image : The first bot image.
            bot2_image : The second bot image.

        Returns:
            np.ndarray: The image identified as containing our robot.
        """
        try:
            if self.display_possible_hueys:
                window_width = 300
                window_height = 300

                for i, img in enumerate(bot_images):
                    if img is not None:
                        try:
                            resized_img = cv2.resize(img, (window_width, window_height))
                            cv2.imshow(f"Bot Image {i + 1}", resized_img)
                        except cv2.error as e:
                            logger.warning(f"Error resizing or displaying image {i + 1}: {e}")
                            continue
                    else:
                        logger.info(f"Image {i + 1} is None")

                cv2.waitKey(0)
                cv2.destroyAllWindows()

            if bot_images and all(img is not None for img in bot_images):
                bot_color = self.selected_colors[0]
                our_bot = find_our_bot(self, bot_images, bot_color, threshold_set)

                return our_bot
            else:
                # logger.warning("No valid bot images found.")
                return None

        except Exception as e:
            logger.warning(f"Unexpected error in detect_our_robot_main: {e}")
            return None

    def four_good(self, tolerance: int = 15) -> int:
        """Checks whether the four detected corners form a square, so the reading can be trusted.

        Uses ``self.centroids`` (``[front_points, back_points]``, two (x, y) points each,
        after ``find_centroids`` has filled in a missing third or fourth corner). At each
        corner it builds two edge vectors: one to the other corner of the same color, and
        one to the nearest corner of the other color. The angle between them must be
        within ``tolerance`` of 90 degrees at all four corners.

        Args:
            tolerance: Largest allowed deviation from 90 degrees, in degrees, for
                the angle at each corner.

        Returns:
            int: 1 if all four corner angles are within tolerance of 90 degrees,
                0 otherwise.
        """
        logger.info("entered four good")
        for j in range(0, 2):
            for i in range(0, 2):
                same_color_side = self.centroids[j][(i + 1) % 2] - self.centroids[j][i]

                opposite_0 = self.centroids[j][i] - self.centroids[(j + 1) % 2][0]
                opposite_1 = self.centroids[j][i] - self.centroids[(j + 1) % 2][1]
                if np.linalg.norm(opposite_0) < np.linalg.norm(opposite_1):
                    other_color_side = opposite_0

                else:
                    other_color_side = opposite_1

                mag_same = np.linalg.norm(same_color_side)
                mag_opp = np.linalg.norm(other_color_side)

                angle = (
                    np.acos(np.dot(same_color_side, other_color_side) / (mag_same * mag_opp))
                    * 180
                    / math.pi
                )

                logger.debug(f"Angle 📐📐📐: {angle}")
                if 90 + tolerance < angle or 90 - tolerance > angle:
                    return 0
        return 1

    def non_diag_good(self, is_not_diagonal: bool, is_flipped: int) -> int:
        """Checks whether a two-corner orientation reading can be trusted.

        Args:
            is_not_diagonal : True if the two detected corners are on the same side, and False if they are not on the same side
            is_flipped : -1 if flipped, 1 if not flipped

        Returns:
            1 if the corners are on the same side, 0 if they are diagonal. Also 0 if the robot is upside down and detected two front or two back corners.
        """
        logger.debug("entered non diag good")

        if (len(self.centroids[0]) == 2 or len(self.centroids[1]) == 2) and (is_flipped == -1):
            return 0
        else:
            return int(is_not_diagonal)

    def confidence(
        self,
        corners: int,
        is_not_diagonal: bool,
        high_overlap: bool,
        is_flipped: int,
        tolerance: int = 15,
    ) -> int:
        """Decides whether this frame's orientation reading can be trusted.

        A reading is not trusted if the enemy's bbox covers too much of Huey's. Otherwise
        it is trusted if:
            - 3 or 4 corners were found and they form a square (``four_good``). With 3
              corners, ``find_centroids`` has already filled in the fourth, so the same
              square check applies.
            - 2 corners were found on the same side of the robot (``non_diag_good``).
        Any other corner count (0, 1, or more than 4) is not trusted.

        Args:
            corners: Number of Huey's corners detected in this frame.
            is_not_diagonal: For a 2-corner reading, True if the two corners are on
                the same side of the robot, False if they are diagonal.
            high_overlap: True if the enemy's bbox covered more than the blackout
                threshold of Huey's bbox (from ``compute_blackout_box``), which makes the
                corners unreliable.
            is_flipped: -1 if Huey is upside down, 1 if right side up.
            tolerance: Largest allowed deviation from 90 degrees, in degrees, for
                each corner angle in the square check.

        Returns:
            int: 1 if the orientation reading is trusted, 0 otherwise.
        """
        logger.debug("entered conf")
        if high_overlap:
            return 0
        elif ((corners == 4 or corners == 3) and self.four_good(tolerance)) or (
            corners == 2 and self.non_diag_good(is_not_diagonal, is_flipped)
        ):
            return 1
        else:
            return 0

    def corner_detection_main(
        self,
        area_threshold: int = 10,
        previous_orientations: list[float] | None = None,
        threshold_set: bool = True,
        is_flipped: int = 1,
        tolerance: int = 15,
    ) -> tuple[dict | None, int]:
        """Main function for detecting corners and orientation of the robot.

        Args:
            area_threshold : Minimum pixel area for a corner blob
            previous_orientations : Bot's past orientations in degrees
            threshold_set : False on the first frame, which sets the initial bot color threshold. True afterwards, which updates the rolling threshold.
            is_flipped : -1 if the robot is upside down, 1 if right side up
            tolerance : Allowed deviation from 90 degrees, in degrees, between adjacent corners

        Returns:
            dict : A dictionary containing details of the robot and enemy robots.
            confidence : 0 or 1, meaning whether we are confident in the orientation
        """
        if previous_orientations is None:
            previous_orientations = []
        try:
            self.corner_method = 0
            self.is_diagonal = False

            high_overlap = False
            bot_images = [bot["img"] for bot in self.bots["bots"]]

            image = self.detect_our_robot_main(bot_images, threshold_set)

            if image is not None:
                # Find the identified bot (our robot)
                huey_bbox = None
                for bot_data in self.bots["bots"]:
                    if bot_data["img"] is image:
                        huey_bbox = bot_data["bbox"]
                        break
                huey = {
                    "bbox": huey_bbox,
                    "center": np.mean(
                        huey_bbox, axis=0
                    ),  # center of the bot with respect to the entire arena
                    "orientation": None,
                    "corners": 0,
                }

                # Enemy bots are all except the identified bot
                enemy_bots = {}
                if isinstance(self.bots, dict) and "bots" in self.bots:
                    for bot_data in self.bots["bots"]:
                        if bot_data["img"] is not image:
                            enemy_bots = {
                                "bbox": bot_data["bbox"],
                                "center": np.mean(bot_data["bbox"], axis=0),
                            }

                            break
                    # Compute blackout overlapped part and create csv
                    if (
                        self.BLACKOUT
                        and enemy_bots
                        and enemy_bots["bbox"]
                        and huey
                        and huey["bbox"]
                        and is_overlap(huey["bbox"], enemy_bots["bbox"])
                    ):
                        image, high_overlap = compute_blackout_box(
                            image, huey["bbox"], enemy_bots["bbox"], thresh=self.thresh
                        )

                    centroid_points, three = find_centroids(
                        image, self.selected_colors, area_threshold
                    )
                    if three:
                        self.corner_method = 3
                    self.centroids = centroid_points

                # Every time we calculate 4 points, calculate diagonal and side length in the case of 1 front 1 back corner in the future
                calc_diagonal_and_side_length(
                    self.centroids, self.diag_len, self.side_len, self.num_lens
                )

                IS_NOT_DIAGONAL = False

                if len(centroid_points[0]) + len(centroid_points[1]) == 2:
                    if previous_orientations is not None and len(previous_orientations) > 0:
                        previous_orientation = previous_orientations[-1]
                        calc_orientation, IS_NOT_DIAGONAL = two_corners(
                            centroid_points,
                            previous_orientation,
                            self.diag_len,
                            self.side_len,
                            huey["bbox"],
                            self.prev_flipped,
                            is_flipped=is_flipped,
                        )
                        self.corner_method = 2

                        if IS_NOT_DIAGONAL:
                            self.is_diagonal = False
                            huey["orientation"] = calc_orientation

                        else:  # DIAGONAL
                            self.is_diagonal = True
                            huey["orientation"] = calc_orientation
                        self.prev_flipped = is_flipped

                        # logger.debug(f"PREV ORIENT: 🌸🐋💛 {previous_orientation}")
                        # logger.(f"Current ORIENT: 💛🐋🌸 { huey["orientation"]}")
                    else:
                        huey["orientation"] = None
                    conf = self.confidence(
                        self.corner_method,
                        IS_NOT_DIAGONAL,
                        high_overlap,
                        is_flipped,
                        tolerance,
                    )
                    return {"huey": huey, "enemy": enemy_bots}, conf

                elif len(centroid_points[0]) + len(centroid_points[1]) < 2:
                    logger.debug("Less than 2 corners found")
                    self.is_diagonal = False
                    conf = 0
                    return {"huey": huey, "enemy": enemy_bots}, conf

                logger.debug("FOURNER4️⃣")
                if self.corner_method != 3:
                    self.corner_method = 4

                front_midpoint = (centroid_points[0][0] + centroid_points[0][1]) * 0.5
                back_midpoint = (centroid_points[1][0] + centroid_points[1][1]) * 0.5

                huey["orientation"] = compute_angle_between_midpoints(back_midpoint, front_midpoint)
                result = {"huey": huey, "enemy": enemy_bots}
                conf = self.confidence(
                    self.corner_method,
                    IS_NOT_DIAGONAL,
                    high_overlap,
                    is_flipped,
                    tolerance,
                )
                return result, conf
            else:
                # logger.debug("Image doesn't exist")
                conf = 0
                return {"huey": {}, "enemy": {}}, conf

        except Exception as e:
            logger.warning(f"Unexpected error in corner_detection_main: {e}")
            conf = 0
            return None, conf


if __name__ == "__main__":
    # Manual smoke test: runs corner detection on saved images of Huey.
    huey_image_path = os.getcwd() + "/warped_images/east_4.png"
    not_huey_image_path = os.getcwd() + "/warped_images/east_4_not_huey.png"
    selected_colors_file = os.getcwd() + "/selected_colors.txt"

    try:
        huey_image = cv2.imread(huey_image_path)
        not_huey_image = cv2.imread(not_huey_image_path)

        if huey_image is None:
            raise ValueError(f"Failed to load image at path: {huey_image_path}")
        if not_huey_image is None:
            raise ValueError(f"Failed to load image at path: {not_huey_image_path}")

    except Exception as e:
        logger.warning(f"Error loading images: {e}")
        exit(1)

    housebot = {"bbox": [[0, 0], [1, 1]], "img": not_huey_image}
    bot1 = {"bbox": [[50, 50], [60, 60]], "img": not_huey_image}
    bot2 = {"bbox": [[150, 150], [160, 160]], "img": huey_image}
    bot3 = {"bbox": [[300, 150], [400, 180]], "img": not_huey_image}

    housebots = [housebot]
    bots = [bot1, bot2, bot3]
    all_bots = {"housebot": housebot, "bots": bots}

    selected_colors = []
    try:
        with open(selected_colors_file) as file:
            for line in file:
                hsv = list(map(int, line.strip().split(", ")))
                selected_colors.append(hsv)
        if len(selected_colors) != 3:
            raise ValueError("The file must contain exactly 3 HSV values.")

    except Exception as e:
        logger.warning(f"Error reading selected_colors.txt: {e}")
        exit(1)

        filename = "area.csv"

    corner_detection = RobotCornerDetection(selected_colors, True, False)
    corner_detection.set_bots(all_bots)
    result = corner_detection.corner_detection_main()
    logger.debug("result: " + str(result))
