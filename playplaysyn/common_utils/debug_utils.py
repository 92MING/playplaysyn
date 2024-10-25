import os
import logging
import colorama

logging.addLevelName(100, "SUCCESS")  # to ensure SUCCESS level is added
logging.addLevelName(5, "VERBOSE")  # to ensure VERBOSE level is added
logging.SUCCESS = 100  # type: ignore
logging.VERBOSE = 5  # type: ignore

log_level = os.environ.get("LOG_LEVEL", "INFO")
log_format = os.environ.get("LOG_FORMAT", "[%(levelname)s] (%(filename)s %(lineno)s) <%(asctime)s>: %(message)s")
time_format = os.environ.get("log_time_format", "%m-%d %H:%M:%S")

class Logger(logging.Logger):
    def success(self, msg: str, *args, **kwargs):
        self.log(logging.SUCCESS, msg, *args, **kwargs) # type: ignore
    
    def verbose(self, msg: str, *args, **kwargs):
        self.log(logging.VERBOSE, msg, *args, **kwargs) # type: ignore

class _RootColorStreamHandler(logging.StreamHandler):
    # this class is also defined in `main.py` to avoid circular import
    _ColorDict = {
        "VERBOSE": colorama.Fore.WHITE + colorama.Style.DIM,
        "DEBUG": colorama.Fore.WHITE,
        "INFO": colorama.Fore.BLUE,
        "WARNING": colorama.Fore.YELLOW,
        "ERROR": colorama.Fore.RED,
        "CRITICAL": colorama.Fore.RED + colorama.Style.BRIGHT,
        "SUCCESS": colorama.Fore.GREEN + colorama.Style.BRIGHT,
    }
    
    def emit(self, record: logging.LogRecord):
        levelname = record.levelname
        level_color = self._ColorDict.get(levelname, None)
        msg = self.format(record)
        if level_color:
            msg = level_color + msg + colorama.Style.RESET_ALL
        try:
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)

logging.basicConfig(level=log_level, format=log_format, datefmt=time_format)

logger: Logger = logging.getLogger()    # type: ignore
logger.__class__ = Logger

stream_handler = _RootColorStreamHandler()
stream_handler.setFormatter(logging.Formatter(log_format, datefmt=time_format))
logger.handlers = [stream_handler,]

logger.debug(f'Log level={log_level}, format={log_format}, time_format={time_format}')

__all__ = ['logger']

if __name__ == '__main__':
    logger.verbose('verbose')
    logger.debug('debug')
    logger.info('info')
    logger.warning('warning')
    logger.error('error')
    logger.critical('critical')