"""
Enketo survey link caching using Redis.

Stores and retrieves enketo survey URLs using the same Redis key
patterns as Zebra so both apps can share the same cache:

  - Hash ``enketo-survey-urls-for-{form_pk}`` stores the full set of
    survey links (offline_url, preview_url, single_once_url, …).
  - String ``enketo-preview-url-for-{form_pk}`` stores just the
    preview URL (used when only the preview is requested).

A separate Redis instance can be configured via the
``ENKETO_LINKS_REDIS_URL`` Django setting.  When not set the module
silently skips caching so that development environments work without
extra infrastructure.
"""

import logging

import redis

from django.conf import settings

logger = logging.getLogger(__name__)

SURVEY_URLS_PREFIX = "enketo-survey-urls-for-"
PREVIEW_URL_PREFIX = "enketo-preview-url-for-"

# Default TTL: 24 hours.  Override via ENKETO_LINKS_CACHE_TTL (seconds).
DEFAULT_CACHE_TTL = 86400


def _get_client():
    """Return a new Redis client, or *None* if not configured."""
    url = getattr(settings, "ENKETO_LINKS_REDIS_URL", None)
    if not url:
        return None
    try:
        return redis.Redis.from_url(url, decode_responses=True)
    except (redis.ConnectionError, redis.RedisError, OSError):
        logger.exception("Failed to create enketo-links Redis client")
        return None


def _cache_ttl():
    return getattr(settings, "ENKETO_LINKS_CACHE_TTL", DEFAULT_CACHE_TTL)


def get_cached_survey_urls(form_pk):
    """Read all survey URLs cached for *form_pk*.

    Returns a ``dict`` with Enketo URL keys (e.g. ``offline_url``,
    ``preview_url``, ``single_once_url``) or ``None`` on cache miss /
    error.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        data = client.hgetall(f"{SURVEY_URLS_PREFIX}{int(form_pk)}")
        return data if data else None
    except (redis.ConnectionError, redis.RedisError, OSError):
        logger.exception("enketo-links Redis read error")
        return None


def store_survey_urls(form_pk, urls):
    """Cache the full set of survey URLs for *form_pk*.

    *urls* is a dict as returned by the Enketo API (keys like
    ``offline_url``, ``preview_url``, ``single_once_url``).
    """
    client = _get_client()
    if client is None:
        return
    try:
        key = f"{SURVEY_URLS_PREFIX}{int(form_pk)}"
        mapping = {k: str(v) for k, v in urls.items() if v is not None}
        if mapping:
            pipe = client.pipeline()
            pipe.hset(key, mapping=mapping)
            pipe.expire(key, _cache_ttl())
            pipe.execute()
    except (redis.ConnectionError, redis.RedisError, OSError):
        logger.exception("enketo-links Redis write error")


def get_cached_preview_url(form_pk):
    """Read the cached preview URL for *form_pk*, or ``None``."""
    client = _get_client()
    if client is None:
        return None
    try:
        return client.get(f"{PREVIEW_URL_PREFIX}{int(form_pk)}")
    except (redis.ConnectionError, redis.RedisError, OSError):
        logger.exception("enketo-links Redis read error")
        return None


def store_preview_url(form_pk, url):
    """Cache just the preview URL for *form_pk*."""
    client = _get_client()
    if client is None:
        return
    try:
        client.set(
            f"{PREVIEW_URL_PREFIX}{int(form_pk)}",
            str(url),
            ex=_cache_ttl(),
        )
    except (redis.ConnectionError, redis.RedisError, OSError):
        logger.exception("enketo-links Redis write error")


def delete_cached_urls(form_pk):
    """Remove all cached enketo URLs for *form_pk*.

    Call this when a form is deleted so stale links are not served for
    the remainder of the TTL.
    """
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(
            f"{SURVEY_URLS_PREFIX}{int(form_pk)}",
            f"{PREVIEW_URL_PREFIX}{int(form_pk)}",
        )
    except (redis.ConnectionError, redis.RedisError, OSError):
        logger.exception("enketo-links Redis delete error")
