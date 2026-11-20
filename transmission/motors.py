"""Receives and transmits data between laptop and motors."""

import logging
import time

from transmission.serial_conn import OurSerial

logger = logging.getLogger(__name__)


class Motor:
    """The Motor Module can be used to control a motor via the flysky channel it is set up to.

    Args:
    speed : float
        numerical value from -1 to 1 representing the throttle
    channel : int
        the channel the motor is connected to
    ser : OurSerial
        a OurSerial object that establishes the laptop's connection to the Arduino


    Methods:
    -------
    move(speed: float)
        Sets the channel to [speed]. If [speed] is greater than 1,
        speed will be set to 1. If [speed] is less than -1, speed will be set to -1

    get_speed()
        Returns the current speed of the motor

    stop(t=0)
        sets motor speed to 0 and sleeps for time [t] seconds

    """

    max_speed = 1
    min_speed = -1

    def __init__(
        self,
        ser: OurSerial,
        channel: int,
        speed: float = 0,
        channel2: int | None = None,
        speed2: float | None = None,
    ) -> None:
        """Controls a motor through a FlySky channel using serial communication.

        Motor speed values are expected to be between -1 and 1. Values
        outside this range are clamped when calling the move() method.

        Attributes:
            max_speed (float): Maximum allowed motor speed. Defaults to 1.
            min_speed (float): Minimum allowed motor speed. Defaults to -1.
            zero_speed (float): Speed used when stopping the motor.
            speed (float): Current speed of the primary motor channel.
            speed2 (float | None): Current speed of the secondary motor channel.
            channel (int): Primary FlySky channel assigned to the motor.
            channel2 (int | None): Optional secondary FlySky channel.
            ser (OurSerial): Serial connection used to send motor commands.
        """
        self.zero_speed = speed
        self.speed = speed
        self.channel = channel
        self.ser = ser
        self.channel2 = channel2
        if speed2 is None:
            speed2 = 0
        self.speed2 = speed2

        if channel2 is not None:
            self.ser.send_data(channel, speed)
        else:
            self.ser.send_data(channel, speed, channel2, speed2)

    def move(
        self,
        speed: float,
        speed2: float | None = None,
    ) -> None:
        """Sets the motor speed and sends the updated command.

         Speed values are clamped to the range [-1, 1].
         If a secondary channel is configured, its speed is also
         sent through the serial connection.

        Args:
            speed: Desired speed of the primary motor channel. Values greater than 1 are set to 1,
            and values less than -1 are set to -1.
            speed2: Desired speed of the secondary
                 motor channel. Values outside [-1, 1] are clamped.
                 Defaults to None.
        """
        if speed > Motor.max_speed:
            speed = Motor.max_speed
        if speed < Motor.min_speed:
            speed = Motor.min_speed
        if speed2 is not None:
            if speed2 > Motor.max_speed:
                speed2 = Motor.max_speed
            if speed2 < Motor.min_speed:
                speed2 = Motor.min_speed

        self.speed = speed
        self.speed2 = speed2
        if self.channel2 is None:
            self.ser.send_data(self.channel, self.speed)
        else:
            # logger.debug(f"Channel data: {self.channel}, {self.speed}, {self.channel2}, {self.speed2}")
            self.ser.send_data(self.channel, self.speed, self.channel2, self.speed2)

    def get_speed(self) -> tuple[float, float]:
        """Returns the current motor speed values.

        Returns:
            speed of the primary channel and the current speed of the
            secondary channel. The secondary speed may be None.
        """
        return self.speed, self.speed2

    def stop(self, t: float = 0) -> None:
        """Stops the motor and optionally pauses execution.

        Resets both motor speeds to the stored zero_speed value,
        sends the updated speeds through the serial connection,
        and pauses execution for the specified duration.

        Args:
            t (float): Number of seconds to pause after sending
                the stop command. Defaults to 0.

        Returns:
            None.

        Raises:
            ValueError: If t is negative.
        """
        self.speed = self.zero_speed
        self.speed2 = self.zero_speed
        self.ser.send_data(self.channel, self.speed, self.channel2, self.speed2)
        time.sleep(t)
