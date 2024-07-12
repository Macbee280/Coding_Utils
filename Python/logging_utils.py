import os, sys
from pathlib import Path
import time
import logging
import inspect

from .config_utils import add_attribute, setup_aws

def make_logger(name, opt={}, level=logging.INFO):
    """
    Make a logger using the name of the file where things occur

        Level, Numeric value, What it means / When to use it
        ----------------------------------------------------
        logging.NOTSET 0 
        When set on a logger, indicates that ancestor loggers are to be consulted to determine the effective level. If that still resolves to NOTSET, then all events are logged. When set on a handler, all events are handled.

        logging.DEBUG 10
        Detailed information, typically only of interest to a developer trying to diagnose a problem.

        logging.INFO 20
        Confirmation that things are working as expected.

        logging.WARNING 30
        An indication that something unexpected happened, or that a problem might occur in the near future (e.g. 'disk space low'). The software is still working as expected.

        logging.ERROR 40
        Due to a more serious problem, the software has not been able to perform some function.

        logging.CRITICAL 50
        A serious error, indicating that the program itself may be unable to continue running.

    Parameters
    ----------
    name : str (name of some file)
    application: str (name of the user's application)

    Returns
    -------
    logger
    """

    # level = 50  # uncomment to stop logging
    name   = os.path.basename(name)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    logger.handlers = []
    
    # Handlers
    opt = add_attribute('local_only', opt)

    if opt['local_only']:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


################################################################################
# LOGGING FUNCTIONS

def get_function_name():
    frame = inspect.currentframe().f_back
    function_name = frame.f_code.co_name
    return function_name, f"{function_name}_start_time"


def log_event(message, level='info', opt={}, is_verbose=False):
    """Log a message to the standard error using logging with a specified level."""

    #short circuit if a log is labeled as being verbose and opt['verbose'] exists and is false
    if is_verbose and ('verbose' in opt.keys() and not opt['verbose']):
        return

    if 'logger' not in globals():
        global logger
        logger = make_logger(__file__, opt=opt)
    
    frame = inspect.currentframe().f_back
    file_name = Path(frame.f_code.co_filename).name
    function_name = frame.f_code.co_name
    lineno = frame.f_lineno

    # Set default values for missing keys in the opt dictionary
    opt.setdefault('job_id', 'null')
    opt.setdefault('user_email', 'null')

    opt = add_attribute('name_space', opt)

    data_tags = {
        "tags": {
            "environment": opt['name_space'],
            "user_id": opt['user_email'],
            "job_id": opt['job_id'],
            "function": function_name
        }
    }

    function_start_time_key = f"{function_name}_start_time"
    opt.setdefault(function_start_time_key, time.time())
    opt.setdefault("full_search_start_time", time.time())


    # Print log message if running in pytest mode
    if opt['name_space'] == "pytest":
        print(f"{file_name} - {function_name} - {lineno} - {message}")
        return

    # Log with the caller's context based on the specified level
    if level.lower() == 'error':
        logger.error(f"{function_name} - {lineno} - {message}", extra=data_tags)
    elif level.lower() == 'debug':
        logger.debug(f"{function_name} - {lineno} - {message}", extra=data_tags)
    else:
        # Default to info level
        logger.info(f"{file_name} - {message}", extra=data_tags)