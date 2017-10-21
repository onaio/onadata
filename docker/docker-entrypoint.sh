#!/bin/bash

sleep 20

psql -h db -U postgres -c "CREATE ROLE onadata WITH LOGIN PASSWORD 'onadata';"
psql -h db -U postgres -c "CREATE DATABASE onadata OWNER onadata;"
psql -h db -U postgres onadata -c "CREATE EXTENSION postgis; CREATE EXTENSION postgis_topology;"

. /srv/.virtualenv/bin/activate

cd /srv/onadata
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py runserver 0.0.0.0:8000
