"""
WSGI config

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
from django.utils import autoreload

import uwsgi  # pylint: disable=import-error
from uwsgidecorators import timer

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "onadata.settings.common")

application = get_wsgi_application()


@timer(3)
def change_code_gracefull_reload(sig):
    """Reload uWSGI whenever the code changes"""
    if autoreload.file_changed:
        uwsgi.reload()
