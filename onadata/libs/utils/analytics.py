# -*- coding: utf-8 -*-
# Analytics package for tracking and measuring with services like Segment.
# Heavily borrowed from RapidPro's temba.utils.analytics

import analytics as segment_analytics
from typing import Dict, List, Optional

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

from onadata.apps.logger.models import Instance
from onadata.libs.utils.common_tags import (
    INSTANCE_CREATE_EVENT, INSTANCE_UPDATE_EVENT)


_segment = False


def init_analytics():
    """Initialize the analytics agents with write credentials."""
    segment_write_key = getattr(settings, 'SEGMENT_WRITE_KEY', None)
    if segment_write_key:
        global _segment
        segment_analytics.write_key = segment_write_key
        _segment = True


def get_user_id(user):
    """Return a user email or username or the string 'anonymous'"""
    if user:
        return user.email or user.username

    return 'anonymous'


class track_object_event(object):
    """
    Decorator that helps track create and update actions for model
    objects.

    This decorator should only be used on functions that return either
    an object or a list of objects that you would like to track. For more
    precise control of what is tracked utilize the track() function
    """

    def __init__(
            self,
            user_field: str,
            properties: Dict[str, str],
            event_name: str = '',
            event_label: str = '',
            additional_context: Dict[str, str] = None):
        self.user_field = user_field
        self.properties = properties
        self.event_start = None
        self.event_name = event_name
        self.event_label = event_label
        self.additional_context = additional_context

    def _getattr_or_none(self, field: str):
        return getattr(self.tracked_obj, field, None)

    def _get_field_from_path(self, field_path: List[str]):
        value = self.tracked_obj
        for field in field_path:
            value = getattr(value, field, None)
        return value

    def set_user(self) -> Optional[User]:
        if '__' in self.user_field:
            field_path = self.user_field.split('__')
            self.user = self._get_field_from_path(field_path)
        else:
            self.user = self._getattr_or_none(self.user_field)

    def get_tracking_properties(self, label: str = None) -> dict:
        tracking_properties = {}
        for tracking_property, model_field in self.properties.items():
            if '__' in model_field:
                field_path = model_field.split('__')
                tracking_properties[tracking_property] = self. \
                    _get_field_from_path(field_path)
            else:
                tracking_properties[tracking_property] = self. \
                    _getattr_or_none(model_field)

        if self.additional_context:
            tracking_properties.update(self.additional_context)

        if label and 'label' not in tracking_properties:
            tracking_properties['label'] = label
        return tracking_properties

    def get_event_name(self) -> str:
        event_name = self.event_name
        if isinstance(self.tracked_obj, Instance) and not event_name:
            last_edited = self.tracked_obj.last_edited
            if last_edited and last_edited > self.event_start:
                event_name = INSTANCE_UPDATE_EVENT
            else:
                event_name = INSTANCE_CREATE_EVENT
        return event_name

    def get_event_label(self) -> str:
        event_label = self.event_label
        if isinstance(self.tracked_obj, Instance) and not event_label:
            form_id = self.tracked_obj.xform.pk
            username = self.user.username
            event_label = f"form-{form_id}-owned-by-{username}"
        return event_label

    def _track_object_event(self, obj, request=None) -> None:
        self.tracked_obj = obj
        self.set_user()
        event_name = self.get_event_name()
        label = self.get_event_label()
        tracking_properties = self.get_tracking_properties(label=label)
        track(
            self.user, event_name,
            properties=tracking_properties, request=request)

    def __call__(self, func):
        def decorator(obj, *args):
            request = None
            if hasattr(obj, "context"):
                request = obj.context.get('request')
            self.event_start = timezone.now()
            return_value = func(obj, *args)
            if isinstance(return_value, list):
                for tracked_obj in return_value:
                    self._track_object_event(tracked_obj, request)
            else:
                self._track_object_event(return_value, request)
            return return_value
        return decorator


def track(user, event_name, properties=None, context=None, request=None):
    """Record actions with the track() API call to the analytics agents."""
    if _segment:
        context = context or {}
        context['source'] = settings.HOSTNAME

        properties = properties or {}

        user_id = get_user_id(user)

        if 'value' not in properties:
            properties['value'] = 1

        if 'submitted_by' in properties:
            submitted_by = get_user_id(properties.pop('submitted_by'))
            properties['event_by'] = submitted_by
            context['event_by'] = submitted_by

        if 'xform_id' in properties:
            context['xform_id'] = properties['xform_id']

        if request:
            context['userId'] = user_id
            context['userAgent'] = request.META.get('HTTP_USER_AGENT', '')
            context['ip'] = request.META.get('REMOTE_ADDR', '')
            context['page'] = {
                'path': request.path,
                'url': request.build_absolute_uri(),
            }
            context['tags'] = {
                'path': request.path,
                'url': request.build_absolute_uri(),
                'userAgent': request.META.get('HTTP_USER_AGENT', ''),
                'ip': request.META.get('REMOTE_ADDR', ''),
                'userId': user_id,
            }

        segment_analytics.track(user_id, event_name, properties, context)
