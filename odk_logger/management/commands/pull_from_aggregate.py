#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 fileencoding=utf-8

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from optparse import make_option
from django.utils.translation import ugettext as _
from utils.briefcase_client import BriefcaseClient


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
    )

    def handle(self, *args, **kwargs):
        url = kwargs.get('url')
        username = kwargs.get('username')
        password = kwargs.get('password')
        to = kwargs.get('to')
        user = User.objects.get(username=to)
        bc = BriefcaseClient(username=username, password=password,
                             user=user, url=url)
        bc.download_xforms(include_instances=True)
        bc.push()
