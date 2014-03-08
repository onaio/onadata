from staging_example import *  # noqa

# choose a different database...
# mysql
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'test',
        'USER': 'adotest',
        'PASSWORD': '12345678',
        'HOST': '192.168.100.108'
    }
}

# Make a unique unique key just for testing, and don't share it with anybody.
SECRET_KEY = 'mlfs33^s1l4xf6a36$0#j%dd*sisfoi&)&4s-v=91#^l01v)*j'
