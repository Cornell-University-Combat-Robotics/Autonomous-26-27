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

