import logging
import functools

def create_log_decorator():
    """
    Creates a logging object and returns it
    """
    logger = logging.getLogger("function-logger")
    logger.setLevel(logging.DEBUG)

    # create the logging file handler
    fh = logging.FileHandler("diagnostic.log")
    fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(fmt)
    fh.setFormatter(formatter)

    # add handler to logger object
    logger.addHandler(fh)
    return logger

def function_log(function):
    """
    A decorator that wraps the passed in function and logs
    exceptions should one occur
    """

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        logger = create_log_decorator()
        try:
            logger.debug("{0} - {1} - {2}".format(function.__name__, args, kwargs))
            result = function(*args, **kwargs)
            logger.debug(result)
            return result
        except:
            # log the exception
            err = "There was an exception in  "
            err += function.__name__
            logger.exception(err)
            # re-raise the exception
            raise

    return wrapper