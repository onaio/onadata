# -*- coding: utf-8 -*-
"""
Loggger AppsConfig module
"""
from __future__ import unicode_literals

from django.apps import AppConfig


class LoggerConfig(AppConfig):
    """
    Logger AppsConfig class.
    """

    name = "onadata.apps.logger"
    verbose_name = "Logger"

    def ready(self):
        # pylint: disable=import-outside-toplevel,unused-import
        from onadata.apps.logger import signals  # noqa
