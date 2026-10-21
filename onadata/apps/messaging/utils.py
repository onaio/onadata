# -*- coding: utf-8 -*-
"""
Messaging util functions.
"""

from __future__ import unicode_literals

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.messaging.constants import APP_LABEL_MAPPING, UNKNOWN_TARGET

User = get_user_model()


def get_available_targets(model):
    """Return targets available through the public messaging endpoints."""
    filters = {
        "xform": {
            "deleted_at__isnull": True,
            "project__deleted_at__isnull": True,
            "project__organization__is_active": True,
        },
        "project": {"deleted_at__isnull": True, "organization__is_active": True},
        "entitylist": {
            "deleted_at__isnull": True,
            "project__deleted_at__isnull": True,
            "project__organization__is_active": True,
        },
        "user": {"is_active": True},
    }
    if model._meta.model_name == "kmskey":
        return model.objects.filter(
            Q(
                content_type=ContentType.objects.get_for_model(User),
                object_id__in=User.objects.filter(is_active=True).values("pk"),
            )
            | Q(
                content_type=ContentType.objects.get_for_model(OrganizationProfile),
                object_id__in=OrganizationProfile.objects.filter(
                    user__is_active=True
                ).values("pk"),
            )
        )
    return model.objects.filter(**filters.get(model._meta.model_name, {}))


class TargetDoesNotExist(Exception):
    """
    Target does not Exist exception class.
    """

    message = UNKNOWN_TARGET


def get_target(target_type):
    """
    Returns a ContentType object if it exists, raises TargetDoesNotExist
    exception if target_type is not known.
    """
    try:
        app_label = APP_LABEL_MAPPING[target_type]

        return ContentType.objects.get(app_label=app_label, model=target_type)
    except (KeyError, ContentType.DoesNotExist) as exc:
        raise TargetDoesNotExist() from exc
