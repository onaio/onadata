# -*- coding: utf-8 -*-
"""Serializer fields utils module."""

from django.contrib.contenttypes.models import ContentType

from onadata.libs.utils.cache_tools import safe_cache_get, safe_cache_set


def get_object_id_by_content_type(instance, model_class):
    """Return instance.object_id from a cached model's content type"""
    key = f"{model_class.__name__}-content_type_id"
    content_type_id = safe_cache_get(key)
    if not content_type_id:
        try:
            content_type_id = ContentType.objects.get(
                app_label=model_class._meta.app_label,
                model=model_class.__name__.lower(),
            ).id
        except ContentType.DoesNotExist:
            if instance and isinstance(instance.content_object, model_class):
                return instance.object_id
        else:
            safe_cache_set(key, content_type_id)

    if instance and instance.content_type_id == content_type_id:
        return instance.object_id

    return None
