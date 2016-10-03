"""
WSGI config for mspray project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/howto/deployment/wsgi/
"""

import os
import uwsgi

from uwsgidecorators import timer
from django.utils import autoreload
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "onadata.settings.common")

application = get_wsgi_application()


@timer(3)
def change_code_gracefull_reload(sig):
        if autoreload.code_changed():
                    uwsgi.reload()
