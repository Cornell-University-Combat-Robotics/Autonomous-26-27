"""Manual test for IMU_sensor that logs the calibrated yaw in a loop.

Creates an IMU_sensor, which asks you to pick the esp32's serial port, then logs the yaw in
degrees (0 to 360) at DEBUG level as fast as it can. Any error is logged as a warning and the loop
keeps going, so a few warnings right at startup usually just mean the first reading hasn't arrived
yet. Press Ctrl+C to stop. Uncomment the other log lines to test the upside down check or a raw
field like the gyroscope.
"""

import serial
import json
import time
import math
import imu_class as imu_class
import logging
import logging_config.logging_config

logger = logging.getLogger(__name__)

windows = "COM3"
mac = "/dev/tty.usbserial-0001"

sensor = imu_class.IMU_sensor()

while True:
    try:
        # sensor.get_yaw_continuous()
        logger.debug(f"yaw: {sensor.get_yaw_continuous()}")
        # logger.debug(f"is upside down: {sensor.get_upside_down_continuous()}")
        # logger.debug(f"Z: {sensor.get_field_continuous("gyroscope", "z")}")
    except KeyboardInterrupt:
        break
    except Exception as e:
        logger.warning(e)
        continue
