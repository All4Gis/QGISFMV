  # -*- coding: utf-8 -*-
import inspect
import logging
import logging.handlers
import os
import sys
import traceback

from qgis.core import QgsApplication

try:
    d = os.path.dirname(QgsApplication.qgisSettingsDirPath() + 'log/')
    if not os.path.exists(d):
        os.mkdir(d)
finally:
    logFilePath = QgsApplication.qgisSettingsDirPath() + 'log/qgis_fmv.log'


class log(object):

    handler = None
    pluginId = 'qgis_fmv'

    @staticmethod
    def error(text):
        ''' Error log text '''
        logger = logging.getLogger(log.pluginId)
        logger.error(text)

    @staticmethod
    def info(text):
        ''' Information log text '''
        logger = logging.getLogger(log.pluginId)
        logger.info(text)

    @staticmethod
    def warning(text):
        ''' Warning log text '''
        logger = logging.getLogger(log.pluginId)
        logger.warning(text)

    @staticmethod
    def debug(text):
        ''' Debug log text '''
        logger = logging.getLogger(log.pluginId)
        logger.debug(text)

    @staticmethod
    def last_exception(msg):
        ''' Last exception log text '''
        exc_type, exc_value, exc_traceback = sys.exc_info()
        log.error(
            msg + '\n  '.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))

    @staticmethod
    def initLogging():
        ''' Start log '''
        try:
            """ set up rotating log file handler with custom formatting """
            log.handler = logging.handlers.RotatingFileHandler(
                logFilePath, maxBytes=1024 * 1024 * 10, backupCount=5)
            formatter = logging.Formatter(
                "%(asctime)s %(levelname)-8s %(message)s")
            log.handler.setFormatter(formatter)
            logger = logging.getLogger(log.pluginId)  # root logger
            logger.setLevel(logging.DEBUG)
            logger.addHandler(log.handler)
            log.info("----------------- Start Log -----------------")
        except Exception:
            pass

    @staticmethod
    def removeLogging():
        ''' Remove log handler '''
        logger = logging.getLogger(log.pluginId)
        logger.removeHandler(log.handler)
        del log.handler

    @staticmethod
    def logStackTrace():
        ''' Trace log text '''
        logger = logging.getLogger(log.pluginId)
        logger.debug("logStackTrace")
        for x in inspect.stack():
            logger.debug(x)
