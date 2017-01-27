# Ubuntu installation instructions.
## Prepare OS
    $ ./script/install/ubuntu

## Database setup

### In the base OS
Replace username and db name accordingly.

    sudo su postgres -c "psql -c \"CREATE USER onadata WITH PASSWORD 'onadata';\""
    sudo su postgres -c "psql -c \"CREATE DATABASE onadata OWNER onadata;\""
    sudo su postgres -c "psql -d onadata -c \"CREATE EXTENSION IF NOT EXISTS postgis;\""
    sudo su postgres -c "psql -d onadata -c \"CREATE EXTENSION IF NOT EXISTS postgis;\""
    sudo su postgres -c "psql -d onadata -c \"CREATE EXTENSION IF NOT EXISTS postgis_topology;\""

### In Docker
These are just examples and you shouldn't run them as they are in production:
Use the Dockerfile in [onaio/docker-builds](https://github.com/onaio/docker-builds/tree/master/postgres) for postgres 9.6.0 with postgis 2.3.0.
```
$ mkdir ~/docker-images/postgres-9.6/
$ cd ~/docker-images/postgres-9.6
$ docker build -t postgres:9.6.0 .
```

To run it.

> This will be a persistent using ~/postgresql/data

```
$ mkdir ~/postgresql/data
$ docker run -e POSTGRES_PASSWORD=pass -p 5432:5432 --volume ~/postgresql/data:/var/lib/postgresql/data --name onadata -d postgres:9.6.0
```

Connect using psql with:
`psql -h localhost -p 5432 -U postgres`

In psql:
```
CREATE USER onadata WITH PASSWORD 'pass'
CREATE DATABASE onadata OWNER onadata
CONNECT onadata
CREATE EXTENSION IF NOT EXISTS postgis
CREATE EXTENSION IF NOT EXISTS postgis_topology;\""
```

From now onwards start your DB with `docker start onadata` provided you passed the name "onadata" to Docker's `--name` option.

## Get the code
    git clone https://github.com/onaio/onadata.git

## Set up and start your virtual environment or sandbox.
    $ virtualenv <.venv>
    $ source <.venv>/bin/activate

## Create a local_settings.py, update it accordingly.
Make sure you have a `onadata/settings/local_settings.py` file.
*This file is usually gitignored.

## Run make to set up core and for initial db setup.
    $ make
You may at this point start core with `$ python manage.py runserver --nothreading` or go on and set up the rest.

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
