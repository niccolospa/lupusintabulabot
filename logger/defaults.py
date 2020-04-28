from logging import getLogger, basicConfig

from logger import DEFAULT_LOG_LEVEL as LOG_LEVEL

levels = {
    "CRITICAL"	: 50 ,
    "ERROR"	    : 40 ,
    "WARNING"	: 30 ,
    "INFO"	    : 20 ,
    "DEBUG"	    : 10 ,
    "NOTSET"	: 0
}


class WithLogging:
    @property
    def logger(self):
        """
        Create logger

        :return: default logger
        """
        nameLogger = str(self.__class__).replace("<class '", "").replace("'>", "")
        return getLogger(nameLogger)

    def logResult(self, msg, level="INFO"):
        def wrap(x):
            if isinstance(msg, str):
                self.logger.log(levels[level], msg)
            else:
                self.logger.log(levels[level], msg(x))
            return x
        return wrap


def getDefaultLogger(level=levels[LOG_LEVEL]):
    """
    Create default logger

    :param level: logger level

    :type level: str

    :return: logger
    """
    basicConfig(level=level)
    return getLogger()
