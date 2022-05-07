# -*- coding: utf-8 -*-
"""
update_enketo_urls - command to update Enketo preview URLs in the MetaData model.
"""
import argparse
import os
import sys

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.http import HttpRequest
from django.utils.translation import gettext_lazy

from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.utils.viewer_tools import get_enketo_urls, get_form_url


class Command(BaseCommand):
    """Updates enketo preview urls in MetaData model"""

    help = gettext_lazy("Updates enketo preview urls in MetaData model")

    def add_arguments(self, parser):
        parser.add_argument(
            "-n", "--server_name", dest="server_name", default="enketo.ona.io"
        )
        parser.add_argument("-p", "--server_port", dest="server_port", default="443")
        parser.add_argument("-r", "--protocol", dest="protocol", default="https")
        parser.add_argument(
            "-c",
            "--generate_consistent_urls",
            dest="generate_consistent_urls",
            default=True,
        )
        parser.add_argument(
            "enketo_urls_file", argparse.FileType("r"), default=sys.stdin
        )

    # pylint: disable=too-many-locals
    def handle(self, *args, **options):
        """Updates enketo preview urls in MetaData model"""
        request = HttpRequest()
        server_name = options.get("server_name")
        server_port = options.get("server_port")
        protocol = options.get("protocol")
        generate_consistent_urls = options.get("generate_consistent_urls")

        if not server_name or not server_port or not protocol:
            raise CommandError(
                "please provide a server_name, a server_port and a protocol"
            )

        if server_name not in ["ona.io", "stage.ona.io", "localhost"]:
            raise CommandError("server name provided is not valid")

        if protocol not in ["http", "https"]:
            raise CommandError("protocol provided is not valid")

        # required for generation of enketo url
        request.META["HTTP_HOST"] = (
            f"{server_name}:{server_port}" if server_port != "80" else server_name
        )

        # required for generation of enketo preview url
        request.META["SERVER_NAME"] = server_name
        request.META["SERVER_PORT"] = server_port

        resultset = MetaData.objects.filter(
            Q(data_type="enketo_url") | Q(data_type="enketo_preview_url")
        )

        for meta_data in resultset:
            username = meta_data.content_object.user.username
            id_string = meta_data.content_object.id_string

            data_type = meta_data.data_type
            data_value = meta_data.data_value
            xform = meta_data.content_object
            xform_pk = xform.pk
            if not os.path.exists("/tmp/enketo_url"):
                break

            with open("/tmp/enketo_url", "a", encoding="utf-8") as f:
                form_url = get_form_url(
                    request,
                    username=username,
                    xform_pk=xform_pk,
                    generate_consistent_urls=generate_consistent_urls,
                )
                enketo_urls = get_enketo_urls(form_url, id_string)
                if data_type == "enketo_url":
                    _enketo_url = enketo_urls.get("offline_url") or enketo_urls.get(
                        "url"
                    )
                    MetaData.enketo_url(xform, _enketo_url)
                elif data_type == "enketo_preview_url":
                    _enketo_preview_url = enketo_urls.get("preview_url")
                    MetaData.enketo_preview_url(xform, _enketo_preview_url)

                f.write(f"{id_string} : {data_value} \n")
            self.stdout.write(f"{data_type}: {meta_data.data_value}")

        self.stdout.write("enketo urls update complete!!")
