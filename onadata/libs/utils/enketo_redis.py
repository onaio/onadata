"""
Enketo survey link caching using Redis.

Stores and retrieves enketo survey URLs using the same Redis key
patterns as Zebra so both apps can share the same cache:

  - Hash ``enketo-survey-urls-for-{form_pk}`` stores the full set of
    survey links (offline_url, preview_url, single_once_url, …).

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

# Default TTL: 24 hours.  Override via ENKETO_LINKS_CACHE_TTL (seconds).
DEFAULT_CACHE_TTL = 86400


# redis.Redis already manages a ConnectionPool internally, so reusing
# the same client object is the intended usage pattern.
_client = None  # pylint: disable=invalid-name


def _get_client():
    """Return the cached Redis client, or *None* if not configured."""
    global _client  # pylint: disable=global-statement
    if _client is not None:
        return _client
    url = getattr(settings, "ENKETO_LINKS_REDIS_URL", None)
    if not url:
        return None
    try:
        _client = redis.Redis.from_url(url, decode_responses=True)
        return _client
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
    except (redis.ConnectionError, redis.RedisError, OSError, ValueError, TypeError):
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
    except (redis.ConnectionError, redis.RedisError, OSError, ValueError, TypeError):
        logger.exception("enketo-links Redis write error")


def delete_cached_urls(form_pk):
    """Remove cached enketo URLs for *form_pk*.

    Call this when a form is deleted so stale links are not served for
    the remainder of the TTL.
    """
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(f"{SURVEY_URLS_PREFIX}{int(form_pk)}")
    except (redis.ConnectionError, redis.RedisError, OSError, ValueError, TypeError):
        logger.exception("enketo-links Redis delete error")
