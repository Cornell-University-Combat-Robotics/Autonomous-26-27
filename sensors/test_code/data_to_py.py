"""Reads IMU data over serial and prints the yaw in degrees.

Sends get_imu to the board once, then reads one JSON line at a time forever. Each line has two
quaternions, rotation and game. Both are converted to roll, pitch, and yaw, and the two yaw values
are printed in degrees. Any line that fails to parse is printed as an error and skipped. Press
Ctrl+C to stop.

Uses the Mac serial port by default. Swap mac for windows in the serial.Serial call on Windows, or
use /dev/ttyUSB0 on Linux.
"""

import serial
import json
import time
import math

windows = "COM3"
mac = "/dev/tty.usbserial-0001"
ser = serial.Serial(mac, 115200, timeout=1)  # use /dev/ttyUSB0 on Linux
ser.write(b"get_imu\n")
line = ser.readline().decode("utf-8").strip()


def quaternion_to_euler(q_w, q_x, q_y, q_z):
    """Converts an IMU quaternion into roll, pitch, and yaw.

    Uses the standard aerospace (ZYX) rotation order. All angles are in radians.

    Args:
        q_w: Real part of the quaternion. Sent as r by the IMU.
        q_x: i part of the quaternion. Sent as i by the IMU.
        q_y: j part of the quaternion. Sent as j by the IMU.
        q_z: k part of the quaternion. Sent as k by the IMU.

    Returns:
        tuple[float, float, float]: Roll, pitch, and yaw in radians. Roll and yaw run from -pi to
            pi. Pitch runs from -pi/2 to pi/2.

    Raises:
        ValueError: If the quaternion is far enough from unit length that the pitch term lands
            outside -1 to 1, math.asin raises a math domain error.
    """
    # Roll (x-axis rotation)
    roll = math.atan2(2 * (q_w * q_x + q_y * q_z), 1 - 2 * (q_x**2 + q_y**2))

    # Pitch (y-axis rotation)
    pitch = math.asin(2 * (q_w * q_y - q_z * q_x))

    # Yaw (z-axis rotation)
    yaw = math.atan2(2 * (q_w * q_z + q_x * q_y), 1 - 2 * (q_y**2 + q_z**2))

    return roll, pitch, yaw


while True:
    # print(ser.readline().decode("utf-8").strip())
    try:
        json_string = ser.readline().decode("utf-8").strip()
        dict = json.loads(json_string)
        roll, pitch, yaw = quaternion_to_euler(
            dict["rotation"]["r"],
            dict["rotation"]["i"],
            dict["rotation"]["j"],
            dict["rotation"]["k"],
        )
        groll, gpitch, gyaw = quaternion_to_euler(
            dict["game"]["r"], dict["game"]["i"], dict["game"]["j"], dict["game"]["k"]
        )
        # print(f"dict: {dict}")
        yaw_to_deg = (yaw / math.pi) * 180
        gyaw_to_deg = (gyaw / math.pi) * 180
        print(f"yaw: {yaw_to_deg}")
        print(f"game yaw: {gyaw_to_deg}")
        # print(f"gravity: {dict["accelerometer"]["gravity_z"]}")
    except KeyboardInterrupt:
        break
    except Exception as e:
        print(e)
        continue
    # time.sleep(0.5)
