"""Establishes a serial connection between laptop and Arduino."""

import logging
import time

import serial
import serial.tools.list_ports

logger = logging.getLogger(__name__)


class OurSerial:
    """Manages serial communication between the laptop and Arduino.

    The OurSerial class establishes a serial connection, allows users
    to select an available port, sends motor speed commands to one or
    two FlySky channels, and closes the connection when finished.

    Attributes:
        ser (serial.Serial): Serial connection to the Arduino.

    """

    def __init__(
        self,
        baudrate: int = 115200,
        timeout: float = 1,
        port: str | None = None,
    ) -> None:
        """Initializes the serial connection to the Arduino.

        If no port is provided, prompts the user to select one from
        the available serial ports. Waits two seconds after opening
        the connection to allow the Arduino to initialize.

        Args:
            baudrate: Serial communication rate in bits per second.
                Defaults to 115200.
            timeout: Read timeout in seconds.
                Defaults to 1.
            port: Serial port connected to the Arduino.
                If None, calls choose_port() to prompt for selection.
                Defaults to None.

        Raises:
            serial.SerialException: If the serial port cannot be opened.
        """
        if port is None:
            port = self.choose_port()
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(2)  # Wait for the serial connection to initialize

    def choose_port(self) -> str:
        """Prompts the user to select an available serial port.

        Steps:
            1. View the list of available serial ports.
            2. Unplug the Arduino and enter '0' to refresh the list.
            3. Identify which port disappeared from the list.
            4. Reconnect the Arduino and enter '0' to refresh again.
            5. Enter the number corresponding to the Arduino's port.

        Returns:
            str: Device name of the selected serial port,
                such as "COM3" or "/dev/ttyUSB0".
        """

        def get_ports() -> tuple[str, dict[str, str]]:
            """Lists available serial ports and prompts for a selection.

            Returns:
                tuple[str, dict[str, str]]: A tuple containing the
                    user's selection and a dictionary mapping numbered
                    options to serial port device names.
            """
            available_ports = serial.tools.list_ports.comports()
            port_dic = {}
            if len(available_ports) == 0:
                logger.info("No ports found")
            else:
                logger.info("Choose a port from the options below:")
                for i in range(len(available_ports)):
                    port = available_ports[i]
                    port_dic[str(i + 1)] = port.device
                    logger.info(f"{i + 1!s} : {port}")
            logger.info("Choose 0 to refresh your options")

            selection = input("Enter your selection here: ")
            return [selection, port_dic]

        def check_validity(selection: str) -> str:
            """Validates a serial port selection.

            Repeatedly prompts the user until they enter a valid port
            number or '0' to refresh the available ports.

            Args:
                selection (str): User's selected port number or '0'
                    to refresh the list.

            Returns:
                str: Validated port selection.
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

    def send_data(
        self,
        channel1: int,
        speed1: float,
        channel2: int | None = None,
        speed2: float | None = None,
    ) -> None:
        """Sets one or two channels to specified speeds.

        Speed values are clamped to the range [-1, 1].
        If a secondary channel is configured, its speed is also
        sent through the serial connection.

        Args:
           channel1: Number of primary channel to set as speed1.
           speed1: Desired speed of the primary motor channel. Values greater than 1 are set to 1,
           and values less than -1 are set to -1.2 to.
           channel2: Number of secondary channel to set as speed2. Defaults to None.
           speed2: Desired speed of the secondary
                motor channel. Values outside [-1, 1] are clamped.
                Defaults to None.
        """
        data = f"{channel1} {speed1:.2f}"
        if channel2 is not None and speed2 is not None:
            data += f" {channel2} {speed2:.2f}"
        data += "\n"
        self.ser.write(data.encode())

    def cleanup(self) -> None:
        """Closes the serial connection to the Arduino.

        Releases the serial port so it can be used by other programs.
        """
        self.ser.close()
