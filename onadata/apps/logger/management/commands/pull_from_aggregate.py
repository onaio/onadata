#!/usr/bin/env python

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.translation import ugettext as _
from optparse import make_option

from onadata.libs.utils.briefcase_client import BriefcaseClient


class Command(BaseCommand):
    help = _("Insert all existing parsed instances into MongoDB")
    option_list = BaseCommand.option_list + (
        make_option('--url',
                    help=_("server url to pull forms and submissions")),
        make_option('-u', '--username',
                    help=_("Username")),
        make_option('-p', '--password',
                    help=_("Password")),
        make_option('--to',
                    help=_("username in this server")),
        make_option('--formid',
                    help=_("form id to download")),
    )

    def handle(self, *args, **kwargs):
        url = kwargs.get('url')
        username = kwargs.get('username')
        password = kwargs.get('password')
        to = kwargs.get('to')
        form_id = kwargs.get('formid')
        if username is None or password is None or to is None or url is None:
            self.stderr.write(
                'pull_form_aggregate -u username -p password --to=username'
                ' --url=aggregate_server_url'
            )
        else:
            user = User.objects.get(username=to)
            bc = BriefcaseClient(username=username, password=password,
                                 user=user, url=url)
            bc.download_xforms(include_instances=True, form_id=form_id)
