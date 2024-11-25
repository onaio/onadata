#!/bin/bash
./docker-startup-install-requirements.sh
celery -A onadata.celeryapp worker -B -l INFO -E
