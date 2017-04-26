#!/usr/bin/env python

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.translation import ugettext as _

from onadata.libs.utils.briefcase_client import BriefcaseClient


class Command(BaseCommand):
    help = _("Insert all existing parsed instances into MongoDB")

    def add_arguments(self, parser):
        parser.add_argument(
            '--url', help=_("server url to pull forms and submissions"))
        parser.add_argument('-u', '--username', help=_("Username"))
        parser.add_argument('-p', '--password', help=_("Password"))
        parser.add_argument('--to', help=_("username in this server"))

    def handle(self, *args, **kwargs):
        url = kwargs.get('url')
        username = kwargs.get('username')
        password = kwargs.get('password')
        to = kwargs.get('to')
        if username is None or password is None or to is None or url is None:
            self.stderr.write(
                'pull_form_aggregate -u username -p password --to=username'
                ' --url=aggregate_server_url')
        else:
            user = User.objects.get(username=to)
            bc = BriefcaseClient(
                username=username, password=password, user=user, url=url)
            bc.download_xforms(include_instances=True)
