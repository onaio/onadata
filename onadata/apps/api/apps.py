# -*- coding: utf-8 -*-
"""API app configuration."""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = "onadata.apps.api"

    def ready(self):
        # Imported for the ``@register`` side effect that wires up the app's
        # system checks.
        from onadata.apps.api import checks  # noqa: F401  pylint: disable=C0415,W0611
