# -*- coding: utf-8 -*-
"""
Onadata django application, provides ODK Aggregate Server APIs,
ODK Briefcase API and a REST API to manage data analysis, collection and
visualization.
"""

from __future__ import absolute_import, unicode_literals

__version__ = "5.2.4"


# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from .celeryapp import app as celery_app

__all__ = ("celery_app",)
