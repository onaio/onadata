from setuptools import setup, find_packages


setup (
      name="core"
    , version = "0.0.1" # dev version
    , description = "Collect, Analyze and Share Data!"
    , author = "Ona Kenya"
    , author_email = "support@oan.io"
    , license = "Copyright (c) 2014, Ona Systems Inc, All rights reserved."
    , packages = find_packages()
    # pip is unable to install from git repos so we will depend on Makefile for this
    , dependency_links=[
          'http://github.com/onaio/pyxform.git@onaio#egg=pyxform'
        , 'http://github.com/jbalogh/django-nose.git#egg=django-nose'
        , 'http://github.com/onaio/python-json2xlsclient.git#egg=j2xclient'
        , 'http://github.com/onaio/django-cors-headers.git@allow-all-for-url#egg=cors-headers'
        , 'http://bitbucket.org/fomcl/savreaderwriter/downloads/savReaderWriter-3.3.0.zip'
    ]
    , install_requires =[
          'numpy'
        , 'pytz==2015.4'
        , 'simplejson'
        , 'Django >=1.7, <1.8'
        , 'django-guardian==1.2'
        , 'django-registration-redux==1.1'
        , 'django-templated-email==0.4.9'# ==0.4.9
        , 'gdata ==2.0.18' # ==2.0.18
        , 'httplib2 >=0.9,<1'
        , 'mock ==1.0.1'
        , 'httmock ==1.2.3'
        , 'modilabs-python-utils ==0.1.5'
        , 'Pillow ==2.9'
        , 'poster ==0.8.1'
        , 'psycopg2 ==2.6.1'
        , 'pymongo ==2.7.2'
        , 'lxml >= 3.4'
        , 'django-reversion ==1.8.7'
        , 'xlrd ==0.9.3'
        , 'xlwt ==0.7.5'
        , 'openpyxl ==2.2.5'
        , 'celery==3.1.19'
        , 'django-celery==3.1.17'
        , 'librabbitmq==1.6.1'
        , 'python-digest==1.7'
        , 'django-digest==1.13'
        , 'python-dateutil==2.4.2'
        , 'PyJWT==1.1.0'
        , 'requests==2.7.0'
        , 'elaphe==0.6.0'
        , 'dict2xml==1.3'
        , 'djangorestframework==3.0'
        , 'djangorestframework-csv==1.3.4'
        , 'djangorestframework-gis==0.8.2'
        , 'Markdown==2.6.2'
        , 'django-filter==0.10.0'
        , 'recaptcha-client==1.0.6'
        , 'unicodecsv==0.13'
        , 'dpath==1.4'
        , 'django-taggit==0.12.3'
        , 'django-oauth-toolkit==0.8.2'
        , 'jsonfield<1.0'
        , 'django-db-readonly==0.3.3'
        , 'pylibmc==1.5.0'
        , 'kombu'
        , 'billiard'
        , 'geojson'
        , 'python-memcached'
        , 'sphinx==1.3.1'
        , 'django-query-builder==0.8.0'
        , 'clint'
        , 'django-extensions'
        , 'django-kombu'
        , 'django-snippetscream'
        , 'django-statsd-mozilla'
        , 'fabric'
        , 'gunicorn'
        , 'ipdb'
        , 'ipython'
        , 'shell_command'
        , 'statsd'
        , 'twill'
        , 'django-debug-toolbar'
    ]
)
