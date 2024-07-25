# -*- coding: utf-8 -*-
"""
Test service health view.
"""
import json

from django.http import HttpRequest
from django.test import override_settings

import onadata
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.views import service_health


class TestServiceHealthView(TestBase):
    def test_service_health(self):
        """
        Test that the `service_health` view function
        works as expected:

        1. Returns a 200 when secondary services are healthy
        2. Returns a 500 when a secondary service is not available
        """
        req = HttpRequest()
        resp = service_health(req)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            json.loads(resp.content.decode("utf-8")),
            {
                "default-Database": "OK",
                "Cache-Service": "OK",
                "onadata-version": onadata.__version__,
            },
        )

        sql_statement_with_error = "SELECT id FROM non_existent_table limit 1;"

        with override_settings(CHECK_DB_SQL_STATEMENT=sql_statement_with_error):
            resp = service_health(req)
            self.assertEqual(resp.status_code, 500)
            response_json = json.loads(resp.content.decode("utf-8"))
            self.assertEqual(response_json["Cache-Service"], "OK")
            self.assertEqual(response_json["onadata-version"], onadata.__version__)
            self.assertEqual(
                response_json["default-Database"][:111],
                (
                    'Degraded state; relation "non_existent_table" does not exist'
                    + f"\nLINE 1: {sql_statement_with_error}"
                ),
            )
