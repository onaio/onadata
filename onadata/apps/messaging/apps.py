# -*- coding: utf-8 -*-
"""
Messaging AppsConfig module
"""
from __future__ import unicode_literals

from django.apps import AppConfig, apps


class MessagingConfig(AppConfig):
    """
    Messaging AppsConfig class.
    """
    name = 'onadata.apps.messaging'
    verbose_name = 'Messaging'

    def ready(self):
        from actstream import registry
        registry.register(apps.get_model(model_name='User', app_label='auth'))
        registry.register(
            apps.get_model(model_name='XForm', app_label='logger'))
        registry.register(
            apps.get_model(model_name='Project', app_label='logger'))
