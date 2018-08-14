#!/bin/bash

sleep 20

psql -h db -U postgres -c "CREATE ROLE onadata WITH SUPERUSER LOGIN PASSWORD 'onadata';"
psql -h db -U postgres -c "CREATE DATABASE onadata OWNER onadata;"
psql -h db -U postgres onadata -c "CREATE EXTENSION postgis; CREATE EXTENSION postgis_topology;"

virtualenv -p `which $SELECTED_PYTHON` /srv/onadata/.virtualenv/${SELECTED_PYTHON}
. /srv/onadata/.virtualenv/${SELECTED_PYTHON}/bin/activate

cd /srv/onadata
pip install --upgrade pip
yes w | pip install -r requirements/base.pip
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py runserver 0.0.0.0:8000
