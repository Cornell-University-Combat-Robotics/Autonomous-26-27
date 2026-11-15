"""Read and process IMU sensor data"""

import serial
import json
import time
import math
import serial.tools.list_ports
import threading
from concurrent.futures import ThreadPoolExecutor
import logging
import logging_config.logging_config

logger = logging.getLogger(__name__)


class IMUReadError(Exception):
    """Base exception for IMU serial read issues"""

    pass


class IMU_sensor:
    def __init__(self, port: str | None = None, baud_rate: int = 115200, timeout: int = 1) -> None:
        """
        Args:
            port: port that the esp32 is connected to. If None, then calls choose_port for port selection
            buad_rate: the baud_rate (data transmission rate)
            timeout: amount of time to wait before raising an error on the serial connection
        """

        if port is None:
            port = self.choose_port()
        self.ser = serial.Serial(port, baud_rate, timeout=timeout)
        self.dict = {}
        self.roll = 0
        self.pitch = 0
        self.yaw = 0
        self.dict_lock = threading.Lock()
        self.error_lock = threading.Lock()
        self.errorCounter = 0
        self.goodTime = time.time()
        time.sleep(2)  # Wait for the serial connection to initialize
        self.update_continuous_dict()
        self.cali_angle = 0
        self.cali_lock = threading.Lock()

    def choose_port(self) -> str:
        """Allows user to determine what port the esp32 is on

        User Guide:
        1. Look at port list logged by choose_port
        2. unplug esp32 and press '0' to refresh list
        3. Look to see which port is missing
        4. replug esp32 and refresh port list
        6. select index of esp32 port

        Returns: string port value (ex. "COM3")
        """

        def get_ports() -> tuple[str, dict[str, str]]:
            """Lists available serial ports and prompts the user to select one.

            Returns:
                list: User selection and dictionary mapping option numbers to port names
            """
            available_ports = serial.tools.list_ports.comports()
            port_dic = {}
            if len(available_ports) == 0:
                logger.info("No ports found")
            else:
                logger.info("Choose a port for the SENSORS/ESP from the options below:")
                for i in range(len(available_ports)):
                    port = available_ports[i]
                    port_dic[str(i + 1)] = port.device
                    logger.info(f"{str(i + 1)} : {port}")
            logger.info("Choose 0 to refresh your options")

            selection = input("Enter your selection here: ")
            return selection, port_dic

        def check_validity(selection: str) -> str:
            """Validates the user's port selection, prompting again if invalid.

            Args:
                selection: User's selected port number or "0" to refresh

            Returns:
                str: Valid port selection or "0" to refresh
            """
            while selection != "0" and selection not in port_dic:
                logger.info(
                    "Selection invalid. Choose one of the following or 0 to refresh options:",
                    list(port_dic.keys()),
                )
                selection = input("Enter your selection here: ")
            return selection

        selection, port_dic = get_ports()
        selection = check_validity(selection)

        while selection == "0":
            selection, port_dic = get_ports()
            selection = check_validity(selection)

        return port_dic[selection]

    def update_dict(self) -> None:
        """Updates dict field with the latest reading from the IMU.

        Raises:
            IMUReadError if there is an issue with reading from the IMU.
        """
        try:
            json_string = self.ser.readline().decode("utf-8").strip()
            self.dict = json.loads(json_string)
        except UnicodeDecodeError as e:
            raise IMUReadError("IMU error: " + str(e))
        except json.decoder.JSONDecodeError as e:
            raise IMUReadError("IMU error: " + str(e))

    def update_continuous_dict(self) -> None:
        """Continuously updates dict field with the latest reading from the IMU in a separate thread.

        Raises:
            IMUReadError if there is an issue with reading from the IMU.
        """

        def update_dict() -> None:
            """Continuously reads IMU data and updates the sensor dictionary."""
            while True:
                try:
                    # logger.debug(f"error count: {self.errorCounter}")
                    json_string = self.ser.readline().decode("utf-8").strip()
                    new_dict = json.loads(json_string)
                    with self.dict_lock:
                        self.dict = new_dict
                    with self.error_lock:
                        self.errorCounter = 0
                        self.goodTime = time.time()
                except UnicodeDecodeError as e:
                    # logger.warning("IMU error: " + str(e))
                    with self.error_lock:
                        self.errorCounter += 1
                        # logger.debug(f"time since good: {time.time()-self.goodTime}")
                except json.decoder.JSONDecodeError as e:
                    # logger.warning("JSON error: " + str(e))
                    with self.error_lock:
                        self.errorCounter += 1
                        # logger.debug(f"time since good: {time.time()-self.goodTime}")

        thread = threading.Thread(target=update_dict, daemon=True)
        thread.start()

    def check_valid(self, threshold: float) -> bool:
        """Returns whether the background thread got a good reading in the last threshold seconds.

        Args:
            threshold: Maximum age of the last good reading, in seconds.

        Returns:
            bool: True if the last good reading is at most threshold seconds old, False otherwise.
        """
        with self.error_lock:
            return time.time() - self.goodTime <= threshold

    def calibrate_yaw(self, camera_read: float, sensor_read: float) -> None:
        """Sets the yaw offset so the IMU's yaw lines up with the camera's orientation.

        Args:
            camera_read: Huey's orientation from corner detection, in degrees.
            sensor_read: Uncalibrated yaw from get_yaw_uncali, in degrees. Should come from the
                same frame as camera_read so the two angles describe the same moment.

        Returns:
            None
        """
        with self.cali_lock:
            self.cali_angle = sensor_read - camera_read

    def get_yaw_uncali(self) -> float:
        """Returns the uncalibrated yaw in degrees from the background thread's latest reading.

        Doesn't wait on the serial port, so it returns right away. Converts the rot quaternion to
        yaw without applying the calibrate_yaw offset, so the result is in the IMU's own frame.
        Also logs the yaw at DEBUG level, but only when the raw yaw was negative. If the IMU stops
        sending, this keeps returning the last good reading, so use check_valid to see how fresh it is.

        Returns:
            float: Uncalibrated yaw in degrees, from 0 up to but not including 360.

        Raises:
            KeyError: If the latest reading doesn't have a rot field with r, i, j, and k. This
                also happens if it's called before the background thread gets its first reading.
        """
        with self.dict_lock:
            _, _, yaw = self.quaternion_to_euler(
                self.dict["rot"]["r"],
                self.dict["rot"]["i"],
                self.dict["rot"]["j"],
                self.dict["rot"]["k"],
            )
        self.yaw = (yaw / math.pi) * 180
        if self.yaw < 0:
            self.yaw += 360
            logger.debug(f"UNCALIBRATED YAW: {self.yaw}")
        return self.yaw

    def get_yaw_continuous(self) -> float:
        """Returns the calibrated yaw in degrees from the background thread's latest reading.

        Doesn't wait on the serial port, so it returns right away. Converts the rot quaternion to
        yaw, then subtracts the offset set by calibrate_yaw so the result lines up with the
        camera's orientation. If the IMU stops sending, this keeps returning the last good
        reading, so use check_valid to see how fresh it is.

        Returns:
            float: Calibrated yaw in degrees, from 0 up to but not including 360.

        Raises:
            KeyError: If the latest reading doesn't have a rot field with r, i, j, and k. This
                also happens if it's called before the background thread gets its first reading.
        """
        with self.dict_lock:
            _, _, yaw = self.quaternion_to_euler(
                self.dict["rot"]["r"],
                self.dict["rot"]["i"],
                self.dict["rot"]["j"],
                self.dict["rot"]["k"],
            )
        self.yaw = (yaw / math.pi) * 180
        if self.yaw < 0:
            self.yaw += 360
            # logger.debug(f"UNCALIBRATED YAW: {self.yaw}")
        with self.cali_lock:
            self.yaw = (self.yaw - self.cali_angle) % 360
            # logger.debug(f"CALIBRATED YAW: {self.yaw}")
        return self.yaw

    def get_field_continuous(self, field: str, subfield: str) -> float:
        """Returns one raw value from the background thread's latest IMU reading.

        Doesn't wait on the serial port, so it returns right away.

        Args:
            field: Top-level key in the reading, like "acc".
            subfield: Key inside that field, like "z".

        Returns:
            float: The value at self.dict[field][subfield].

        Raises:
            KeyError: If the latest reading doesn't have that field or subfield. This also happens
                if it's called before the background thread gets its first reading.
        """
        with self.dict_lock:
            return self.dict[field][subfield]

    def get_upside_down_continuous(self) -> int:
        """Returns whether the bot is right side up, using the background thread's latest reading.

        Doesn't wait on the serial port, so it returns right away. Checks the sign of the
        accelerometer's z value. Zero or positive counts as right side up. If the IMU stops
        sending, this keeps returning the last good reading, so use check_valid to see how fresh
        it is.

        Returns:
            int: 1 if the bot is right side up and -1 if it is upside down.

        Raises:
            KeyError: If the latest reading doesn't have an acc field with a z value. This also
                happens if it's called before the background thread gets its first reading.
        """
        with self.dict_lock:
            gravity_z = self.dict["acc"]["z"]
        return 1 if gravity_z >= 0 else -1

    def is_upside_down(self) -> int:
        """Reads a new line from the IMU and returns whether the bot is right side up.

        Returns:
            int: 1 if the bot is right side up and -1 if it is upside down.

        Raises:
            IMUReadError: If the line from the IMU can't be decoded or isn't valid JSON. This
                includes the serial read timing out and returning an empty line.
            KeyError: If the reading doesn't have an acc field with a z value.
        """
        self.update_dict()
        return 1 if self.dict["acc"]["z"] >= 0 else -1

    def get_yaw(self) -> float:
        """Reads a new line from the IMU and returns its yaw in degrees from 0 to 360.

        Returns:
            float: Uncalibrated yaw in degrees, from 0 up to but not including 360.

        Raises:
            IMUReadError: If the line from the IMU can't be decoded or isn't valid JSON. This
                includes the serial read timing out and returning an empty line.
            KeyError: If the reading doesn't have a rot field with r, i, j, and k.
        """
        # try to get a new reading for yaw
        self.update_dict()

        _, _, yaw = self.quaternion_to_euler(
            self.dict["rot"]["r"],
            self.dict["rot"]["i"],
            self.dict["rot"]["j"],
            self.dict["rot"]["k"],
        )
        self.yaw = (yaw / math.pi) * 180
        if self.yaw < 0:
            self.yaw += 360
        return self.yaw

    def quaternion_to_euler(
        self, q_w: float, q_x: float, q_y: float, q_z: float, yaw_only: bool = True
    ) -> tuple[float, float, float]:
        """Converts an IMU quaternion into roll, pitch, and yaw.

        Args:
            q_w: Real part of the quaternion. Sent as r by the IMU.
            q_x: i part of the quaternion. Sent as i by the IMU.
            q_y: j part of the quaternion. Sent as j by the IMU.
            q_z: k part of the quaternion. Sent as k by the IMU.
            yaw_only: If True, skips roll and pitch and returns 0 for both. Defaults to True.

        Returns:
            tuple[float, float, float]: Roll, pitch, and yaw in radians. Roll and yaw run from -pi
                to pi. Pitch runs from -pi/2 to pi/2.

        Raises:
            ValueError: If yaw_only is False and rounding error pushes the pitch term outside -1
                to 1, math.asin raises a math domain error.
        """
        self.yaw = math.atan2(2 * (q_w * q_z + q_x * q_y), 1 - 2 * (q_y**2 + q_z**2))
        if yaw_only:
            return 0, 0, self.yaw
        # Roll (x-axis rotation)
        self.roll = math.atan2(2 * (q_w * q_x + q_y * q_z), 1 - 2 * (q_x**2 + q_y**2))

        # Pitch (y-axis rotation)
        # TS BREAKS BTW SO FIX IT IF YOU WANT PITCH, 2 * (q_w * q_y - q_z * q_x) > 1 which is outside of asin domain (rounding error)
        self.pitch = math.asin(2 * (q_w * q_y - q_z * q_x))

        # Yaw (z-axis rotation)

        return self.roll, self.pitch, self.yaw
