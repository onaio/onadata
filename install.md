# Ubuntu installation instructions
## Prepare Os

    sudo apt-get update
    sudo apt-get install  postgresql-9.3-postgis-2.1 binutils libproj-dev gdal-bin memcached libmemcached-dev build-essential python-pip python-virtualenv python-dev git libssl-dev libpq-dev gfortran libatlas-base-dev libjpeg-dev libxml2-dev libxslt-dev zlib1g-dev python-software-properties ghostscript python-celery python-sphinx openjdk-7-jdk openjdk-7-jre postgresql-9.3-postgis-2.1 postgresql-9.3-postgis-2.1-scripts

## Database setup
Replace username and db name accordingly.

    sudo su postgres -c "psql -c \"CREATE USER onadata WITH PASSWORD 'onadata';\""
    sudo su postgres -c "psql -c \"CREATE DATABASE onadata OWNER onadata;\""
    sudo su postgres -c "psql -d onadata -c \"CREATE EXTENSION IF NOT EXISTS postgis;\""
    sudo su postgres -c "psql -d onadata -c \"CREATE EXTENSION IF NOT EXISTS postgis;\""
    sudo su postgres -c "psql -d onadata -c \"CREATE EXTENSION IF NOT EXISTS postgis_topology;\""

## Get the code
    git clone https://github.com/onaio/onadata.git onadata
    cd onadata/
    git checkout osm

## Create python virtual environment and activate
    mkdir ~/.virtualenvs
    virtualenv ~/.virtualenvs/onadata
    source ~/.virtualenvs/onadata/bin/activate

## Install required python packages
    pip install -r requirements/base.pip --allow-all-external
    pip install numpy pandas==0.12.0

## Set local_settings.py, update it accordingly
    cp script/local_settings.py local_settings.py

## Initial db setup
    python manage.py syncdb --noinput
    python manage.py migrate

## compile api docs
    cd docs
    make html
    cd ..

## copy static files to static dir
    python manage.py collectstatic --noinput
    python manage.py createsuperuser

## Setup uwsgi init script
    pip install uwsgi
    # edit uwsgi.ini accrodingly, change paths, user among other parmas
    sudo cp script/etc/init/onadata.conf /etc/init/onadata.conf
    # start the onadata service
    sudo start onadata
    # check that it started ok
    # cat /path/to/onadata.log

## Setup celery service
    sudo apt-get install rabbitmq-server
    # edit script/etc/default/celeryd-ona with correct paths and user, group
    sudo cp script/etc/default/celeryd-ona /etc/default/celeryd-ona
    # copy init script celeryd-ona
    sudo cp script/etc/init.d/celeryd-ona /etc/init.d/celeryd-ona
    sudo chmod +x /etc/init.d/celeryd-ona
    sudo update-rc.d -f celeryd-ona defaults
    sudo service celeryd-ona start
    # confirm that the service started successfully
    cat /tmp/w1-ona.log

## Setup nginx
    sudo apt-get install nginx
    sudo cp script/etc/nginx/sites-available/onadata /etc/nginx/sites-available/onadata
    sudo ln -s /etc/nginx/sites-available/onadata /etc/nginx/sites-enabled/onadata
    # update and test /etc/nginx/sites-available/onadata
    sudo service nginx configtest
    # remove default nginx server config
    sudo unlink /etc/nginx/sites-enabled/default
    sudo service nginx restart

