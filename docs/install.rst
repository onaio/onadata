Ubuntu installation instructions
================================

Get the code
------------

.. code-block:: sh

    # create onadata user account
    useradd -m onadata -G www-data

    git clone https://github.com/onaio/onadata.git

    # move onadata to /srv/onadata and
    # make sure onadata user has permissions
    sudo mv onadata /srv/onadata
    sudo chown -R onadata:www-data /srv/onadata/
    cd /srv/onadata

Prepare OS
----------

.. code-block:: sh

    ./script/install/ubuntu

Database setup
--------------

In the base OS
~~~~~~~~~~~~~~

Replace username and db name accordingly.

.. code-block:: sh

    sudo su postgres -c "psql -c \"CREATE USER onadata WITH PASSWORD 'onadata';\""
    sudo su postgres -c "psql -c \"CREATE DATABASE onadata OWNER onadata;\""
    sudo su postgres -c "psql -d onadata -c \"CREATE EXTENSION IF NOT EXISTS postgis;\""
    sudo su postgres -c "psql -d onadata -c \"CREATE EXTENSION IF NOT EXISTS postgis_topology;\""

Create a local_settings.py and update it accordingly
----------------------------------------------------

Make sure you have a ``onadata/settings/local_settings.py`` file.

.. code-block:: sh

    cp onadata/settings/default_settings.py onadata/settings/local_settings.py
    # update the DATABASE and SECRET_KEY settings accordingly.

Set up and start your virtual environment or sandbox
----------------------------------------------------

.. code-block:: sh

    virtualenv .virtualenv
    source .virtualenv/bin/activate

Run make to set up onadata and for initial db setup
---------------------------------------------------

.. code-block:: sh

    make

You may at this point start core with

.. code-block:: sh

    python manage.py runserver --nothreading

or go on and set up the rest.

Compile api docs
----------------

.. code-block:: sh

    cd docs
    make html
    cd ..

Copy static files to static dir
-------------------------------

.. code-block:: sh

    python manage.py collectstatic --noinput
    python manage.py createsuperuser

Setup uwsgi init script
-----------------------

.. code-block:: sh

    pip install uwsgi
    # edit uwsgi.ini and onadata.service accrodingly, change paths and configurations accordingly.
    sudo cp script/etc/systemd/system/onadata.service /etc/systemd/system/onadata.service
    # start the onadata service
    sudo systemctl start onadata.servicea
    # check that it started ok
    sudo systemctl status onadata.servicea

Setup celery service
--------------------

.. code-block:: sh

    # edit script/etc/default/celeryd-ona with correct paths and user, group
    sudo cp script/etc/default/celeryd-generic /etc/default/celeryd-onadata
    sudo cp script/etc/default/celerybeat-generic /etc/default/celerybeat-onadata
    # copy init script celeryd-ona
    sudo cp script/etc/init.d/celeryd-generic /etc/init.d/celeryd-onadata
    sudo cp script/etc/init.d/celerybeat-generic /etc/init.d/celerybeat-onadata
    sudo chmod +x /etc/init.d/celeryd-onadata
    sudo chmod +x /etc/init.d/celerybeat-onadata
    sudo update-rc.d -f celeryd-onadata defaults
    sudo update-rc.d -f celerybeat-onadata defaults
    sudo service celeryd-onadata start
    sudo service celerybeat-onadata start

Setup nginx
-----------

.. code-block:: sh

    sudo apt-get install nginx
    sudo cp script/etc/nginx/sites-available/onadata /etc/nginx/sites-available/onadata
    sudo ln -s /etc/nginx/sites-available/onadata /etc/nginx/sites-enabled/onadata
    # update and test /etc/nginx/sites-available/onadata
    sudo service nginx configtest
    # remove default nginx server config
    sudo unlink /etc/nginx/sites-enabled/default
    sudo service nginx restart

Mac OS Installation Instructions
================================

Step 1: Install dependencies using brew
---------------------------------------

`Install homebrew <http://brew.sh/>`_ and run the following commands:

.. code-block:: sh

    brew install postgis
    brew install gdal
    brew install rabbitmq
    brew install libmemcached


Add the following to your ``~/.bash_profile`` or ``~/.zprofile``

::

    export LIBMEMCACHED=/usr/local
    export LC_ALL=en_US.UTF-8
    export LANG=en_US.UTF-8
    PATH=$PATH:/usr/local/sbin

Rabbitmq is not automatically added to your path that's why we add ``PATH=$PATH:/usr/local/sbin``.

Step 2: Install pip and virtualenv
----------------------------------

Install pip using `easy_install pip` if you don't have it already.

Install `virtualenvwrapper <https://virtualenvwrapper.readthedocs.org/en/latest/>`_ and then create a virtual environment.

Step 3: Clone the sourcecode
----------------------------

Clone `onadata <git@github.com:onaio/onadata.git>`_ in your directory of choice

Step 4: Install app requirements
--------------------------------

Before you install dependencies from the requirements directory files, ensure you have activated your virtual environment and if not, use the ``workon <your-virtual-env>`` to activate it. Then, run the following command:

.. code-block:: sh

    pip install numpy  --use-mirrors
    pip install -r requirements/base.pip --allow-all-external
    pip install -r requirements/dev.pip

There is a known bug that prevents numpy from installing correctly when in requirements.pip file

Step 5: Install postgres and create your database
-------------------------------------------------

`Install postgres <http://postgresapp.com/>`_ and access postgres in your
terminal using the command ``psql`` and use the following commands to create
your user and database:

.. code-block:: sql

    CREATE USER <username> WITH PASSWORD '<password>' SUPERUSER CREATEDB LOGIN;
    CREATE DATABASE <database-name> WITH ENCODING='UTF8' LC_CTYPE='en_US.UTF-8' LC_COLLATE='en_US.UTF-8' OWNER=<username> TEMPLATE=template0;

You will also need to create some extensions in your newly created database.
Enter the command ``\c <database-name>`` to connect to your database then run
the following commands to install the extensions:

.. code-block:: sql

    CREATE EXTENSION IF NOT EXISTS postgis;
    CREATE EXTENSION IF NOT EXISTS postgis_topology;

Create `local_settings.py` file in the root of you cloned app if you don't have one already and update the `DATABASE` property with the details above.

Step 6: Test installation using development server
--------------------------------------------------

Run

.. code-block:: sh

    python manage.py runserver

Step 7: Using celery
--------------------

Start rabbitmq with the command ``rabbitmq-server`` in a different terminal
window.

Add ``CELERY_ALWAYS_EAGER = False`` to your local_settings if doesn't exist
already.

Run ``python manage.py celeryd -l debug`` on the root the app directory in a
different terminal window.
