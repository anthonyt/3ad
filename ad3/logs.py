import logging
format = logging.Formatter("%(levelname)s %(asctime)s %(funcName)s %(lineno)d %(message)s")
logger = logging.getLogger('3ad')

def addHandler(handler=None):
    if handler is None:
        handler = logging.StreamHandler()
        handler.setFormatter(format)
    logger.addHandler(handler)

