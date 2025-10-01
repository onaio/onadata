# -*- coding: utf-8 -*-
"""
Default settings module.
"""
# this system uses structured settings.py as defined in
# http://www.slideshare.net/jacobian/the-best-and-worst-of-django
#
# this third-level staging file overrides some definitions in staging_example.py
# You may wish to alter it to agree with your local environment
#

# get most settings from staging_example.py (which in turn, imports from
# settings.py)
from onadata.settings.staging_example import *  # noqa pylint: disable=W0401,W0614

# DEBUG = True

ALLOWED_HOSTS = ["*"]

# # # now override the settings which came from staging # # # #
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": "onadata",
        "USER": "onadata",
        "PASSWORD": "",
        "HOST": "127.0.0.1",
    }
}

DATABASE_ROUTERS = []  # turn off second database
SLAVE_DATABASES = []

# Make a unique unique key just for testing, and don't share it with anybody.
SECRET_KEY = "mlfs33^s1l4xf6a36$0#j%dd*sisfoi&)&4s-v=91#^l01v)*j"  # noqa
