# this system uses structured settings.py as defined in
# http://www.slideshare.net/jacobian/the-best-and-worst-of-django
#
# this third-level staging file overrides some definitions in staging.py
# You may wish to alter it to agree with your local environment
#

# get most settings from staging_example.py (which in turn, imports from
# settings.py)
from staging_example import *  # nopep8

# # # now override the settings which came from staging # # # #
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'onadata',
        'USER': 'onadata',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'OPTIONS': {
            # note: this option obsolete starting with django 1.6
            'autocommit': True,
        }
    }
}

DATABASE_ROUTERS = []  # turn off second database

# Make a unique unique key just for testing, and don't share it with anybody.
SECRET_KEY = 'mlfs33^s1l4xf6a36$0#j%dd*sisfoi&)&4s-v=91#^l01v)*j'


# legacy setting for old sites who still use a local_settings.py file and have
# not updated to presets/
try:
    from local_settings import *  # nopep8
except ImportError:
    pass
