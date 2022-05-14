#!/usr/bin/env python
# -*- coding=utf-8 -*-
"""
pull_from_aggregate command

Uses the BriefcaseClient to download forms and submissions
from a server that implements the Briefcase Aggregate API.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from onadata.libs.utils.briefcase_client import BriefcaseClient


class Command(BaseCommand):
    """Download forms and submissions from a server with Briefcase Aggregate API"""

    help = _(
        "Download forms and submissions from a server with Briefcase Aggregate API"
    )

    def add_arguments(self, parser):
        """Download forms and submissions from a server with Briefcase Aggregate API"""
        parser.add_argument("--url", help=_("server url to pull forms and submissions"))
        parser.add_argument("-u", "--username", help=_("Username"))
        parser.add_argument("-p", "--password", help=_("Password"))
        parser.add_argument("--to", help=_("username in this server"))

    def handle(self, *args, **kwargs):
        url = kwargs.get("url")
        username = kwargs.get("username")
        password = kwargs.get("password")
        to_username = kwargs.get("to")
        if username is None or password is None or to_username is None or url is None:
            self.stderr.write(
                "pull_from_aggregate -u username -p password --to=username"
                " --url=aggregate_server_url"
            )
        else:
            user = get_user_model().objects.get(username=to_username)
            briefcase_client = BriefcaseClient(
                username=username, password=password, user=user, url=url
            )
            briefcase_client.download_xforms(include_instances=True)
