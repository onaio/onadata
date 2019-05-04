#!/bin/sh
#
# flake8 check
exec git diff --staged --name-only | grep -E '\.py$' | xargs flake8 --exclude=migrations -
