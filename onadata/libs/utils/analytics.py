# -*- coding: utf-8 -*-
# Analytics package for tracking and measuring with services like Segment.
# Heavily borrowed from RapidPro's temba.utils.analytics

import analytics as segment_analytics

from django.conf import settings


_segment = False


def init_analytics():
    segment_write_key = getattr(settings, 'SEGMENT_WRITE_KEY', None)
    if segment_write_key:
        global _segment
        segment_analytics.write_key = segment_write_key


def get_user_id(user):
    if user:
        return user.email or user.username

    return 'anonymous'


def track(user, event_name, properties=None, context=None):
    if _segment:
        context = context or {}
        context['source'] = settings.HOSTNAME

        properties = properties or {}

        if 'value' not in properties:
            properties['value'] = 1

        user_id = get_user_id(user)
        segment_analytics.track(user_id, event_name, properties, context)
