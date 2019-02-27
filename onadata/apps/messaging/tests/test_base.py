# -*- coding: utf-8 -*-
"""
Messaging app base tests module.
"""

from django.contrib.auth import get_user_model

from actstream.signals import action

from onadata.apps.messaging.constants import MESSAGE

User = get_user_model()


def _create_user(username='testuser'):
    return User.objects.create(username=username)


def _create_message(actor, target, message='Hello'):
    results = action.send(
        actor, verb=MESSAGE, target=target, description=message)

    return results[0][1]
