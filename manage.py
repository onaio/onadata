#!/usr/bin/env python
# encoding=utf-8
from __future__ import print_function
import logging
import os
import sys
import warnings

south_logger = logging.getLogger('south')
south_logger.setLevel(logging.INFO)

if __name__ == "__main__":
    # altered for new settings layout
    if not any([arg.startswith('--settings=') for arg in sys.argv]):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                              "onadata.settings.common")
        print('Your environment is:"{}"'.format(
            os.environ['DJANGO_SETTINGS_MODULE']))

    import django
    if django.VERSION[0] == 2:
        message = "This version of onadata is no-longer supported and no new"\
            "features will be added. However, bugs that will be found will be"\
            "fixed. Please consider upgrading your onadata version to the "\
            "latest one. https://github.com/onaio/onadata/releases"
        RED = '\033[91m'
        CEND = '\033[0m'
        print(RED + "{}".format(message) + CEND)

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
