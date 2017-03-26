#!/usr/bin/env python

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.translation import ugettext as _

from onadata.libs.utils.briefcase_client import BriefcaseClient


class Command(BaseCommand):
    help = _("ODK Briefcase like pull forms command.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--url', help=_("server url to pull forms and submissions"))
        parser.add_argument('-u', '--username', help=_("Username"))
        parser.add_argument('-p', '--password', help=_("Password"))
        parser.add_argument('--to', help=_("username in this server"))
        parser.add_argument(
            '--forms', help=_("comma separated list of form id_strings"))

    def handle(self, *args, **options):
        url = options.get('url')
        username = options.get('username')
        password = options.get('password')
        forms = options.get('forms')
        to = options.get('to')
        if username is None or password is None or to is None or url is None:
            self.stderr.write(
                'pull_form_aggregate -u username -p password --to=username'
                ' --url=aggregate_server_url')
        else:
            if forms:
                forms = forms.split(',')
            user = User.objects.get(username=to)
            bc = BriefcaseClient(
                username=username,
                password=password,
                user=user,
                url=url,
                forms=forms)
            bc.download_xforms(include_instances=True)
