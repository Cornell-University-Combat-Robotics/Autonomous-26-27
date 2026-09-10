# This logger derived from: https://medium.com/@aman.deep291098/python-custom-logging-made-easy-c89f4972af95

import logging
from time import time
import os

ERROR_LEVEL = 40
WARNING_LEVEL = 30
INFO_LEVEL = 20
DEBUG_LEVEL = 10
TRACE_LEVEL = 5

# These should be exposed to config file
CONSOLE_LOGGING_LEVEL = logging.DEBUG
FILE_LOGGING_LEVEL = logging.DEBUG

RUN_NAME = str(int(time())) # This should be exposed to config file, can be set custom

class Logger(logging.Logger):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        print(f"Initializing logger with name: {name}")
        self.setLevel(logging.DEBUG)
        self.propagate = False
        # Adding a console handler
        # Whether we write to console should be exposed to config file
        console_handler = ConsoleHandler()
        self.addHandler(console_handler)

        
        # If logs/RUN_NAME directory does not exist, create it
        if not os.path.exists(f"logs/{RUN_NAME}"):
            os.makedirs(f"logs/{RUN_NAME}")
        
        # Adding a file handler
        # Whether we write to files should be exposed to config file
        file_handler = CustomFileHandler(logfile_name=f"logs/{RUN_NAME}/{name}.log")
        self.addHandler(file_handler)
        
        # Main file handler
        file_handler = CustomFileHandler(logfile_name=f"logs/{RUN_NAME}/all.log")
        self.addHandler(file_handler)
        
        # Initialize logging levels, TRACE is custom
        # CLAUDE: Is this the proper way to instantialize all the level numbers? Will there be other defaults? Are these in the right spot in the code?
        logging.addLevelName(ERROR_LEVEL, "ERROR")
        logging.addLevelName(WARNING_LEVEL, "WARNING")
        logging.addLevelName(INFO_LEVEL, "INFO")
        logging.addLevelName(DEBUG_LEVEL, "DEBUG")
        logging.addLevelName(TRACE_LEVEL, "TRACE")

    def trace(self, msg = ""):
        if self.isEnabledFor(TRACE_LEVEL):
            if msg == "":
                # All of the super cool stuff
                self._log(TRACE_LEVEL, "This is our custom TRACE debugger") # TODO: IMPLEMENT
            else:
                # CLAUDE: What does self._log do? What is this referencing?
                self._log(TRACE_LEVEL, msg)
    
class ConsoleHandler(logging.StreamHandler):
    def __init__(self, level: int = CONSOLE_LOGGING_LEVEL) -> None:
        super().__init__()
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%m/%d/%Y %H:%M:%S",
        )
        self.setFormatter(formatter)
        # This should be exposed to config file
        self.setLevel(level)

class CustomFileHandler(logging.FileHandler):
    def __init__(self, logfile_name = "logs/logfile.log") -> None:
        # We want to expose this variable to whenever we initialize the logger
        super().__init__(logfile_name, encoding="UTF-8")
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%m/%d/%Y %H:%M:%S",
        )
        self.setFormatter(formatter)
        # This should be exposed to config file
        self.setLevel(FILE_LOGGING_LEVEL)

# Set the custom logger class as the default logger class
logging.setLoggerClass(Logger)

# Use the custom logger

RUN_TIME = time()
logger = logging.getLogger(__name__)
logger = logging.getLogger("algorithm")

logger.info("This is a debug message")
logger.trace()