# this system uses structured settings.py as defined in http://www.slideshare.net/jacobian/the-best-and-worst-of-django

try:
    from ..settings import *
except ImportError:
    import sys, django
    django.utils.six.reraise(RuntimeError, *sys.exc_info()[1:])  # use RuntimeError to extend the traceback
except:
    raise

DEBUG = False  # this setting file will not work on "runserver" -- it needs a server for static files

# set the actual location for the production static and media directories
STATIC_ROOT = "/srv/ona-static"
STATICFILES_DIRS = (os.path.join(PROJECT_ROOT, "static"),)
MEDIA_ROOT = '/var/ona-media'

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

# your actual production settings go here...,.
# for 12-factor installations, this will be in a URL read by default_settings.py
# which will override any definition here
DATABASES = {
     'default': {
         'ENGINE': 'django.contrib.gis.db.backends.postgis',
         'NAME': 'ona_production',
         'USER': 'change this',
         # Note: make sure this user can read db tables "geometry_columns" and "spatial_ref_sys" (fixes a postgis bug)
         'PASSWORD': 'change this too',
         'HOST': 'dbserver.and_change_this.org',
         'OPTIONS': {
             'autocommit': True  # note: this option obsolete starting with django 1.6
             }
         }
    }

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/New_York'
#TIME_ZONE = 'Africa/Lagos'

TOUCHFORMS_URL = 'http://localhost:9000/'

MONGO_DATABASE = {
    'HOST': 'localhost',
    'PORT': 27017,
    'NAME': 'onadata',
    'USER': '',
    'PASSWORD': ''
}
# Make this unique, and don't share it with anybody.
SECRET_KEY = 'mlfs33^s1l4xf6a36$0#j%dd*sisfo6HOk3245u3tYXB9y'
