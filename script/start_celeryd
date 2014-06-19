#! /bin/bash
# This script is for starting up celeryd and rabbitmq in dev mode to enable
# data imports using odk briefcase

# start rabbitmq-server
echo "[info] Starting rabbitmq server and celery worker"

(/usr/local/sbin/rabbitmq-server) & (python manage.py celeryd) & wait

echo "[info] Rabbitmq and Celery worker started!"
