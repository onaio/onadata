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

# Module-level connection pool — shared across all requests.
_pool = None


def _get_pool():
    """Return the shared ``ConnectionPool``, creating it on first call."""
    global _pool  # noqa: PLW0603
    if _pool is not None:
        return _pool
    url = getattr(settings, "ENKETO_LINKS_REDIS_URL", None)
    if not url:
        return None
    try:
        _pool = redis.ConnectionPool.from_url(url, decode_responses=True)
        return _pool
    except Exception:
        logger.exception("Failed to create enketo-links Redis connection pool")
        return None


def _get_connection():
    """Return a Redis client backed by the shared connection pool, or *None*."""
    pool = _get_pool()
    if pool is None:
        return None
    return redis.Redis(connection_pool=pool)


def _cache_ttl():
    return getattr(settings, "ENKETO_LINKS_CACHE_TTL", DEFAULT_CACHE_TTL)


def get_cached_survey_urls(form_pk):
    """Read all survey URLs cached for *form_pk*.

    Returns a ``dict`` with Enketo URL keys (e.g. ``offline_url``,
    ``preview_url``, ``single_once_url``) or ``None`` on cache miss /
    error.
    """
    conn = _get_connection()
    if conn is None:
        return None
    try:
        data = conn.hgetall(f"{SURVEY_URLS_PREFIX}{int(form_pk)}")
        return data if data else None
    except Exception:
        logger.exception("enketo-links Redis read error")
        return None


def store_survey_urls(form_pk, urls):
    """Cache the full set of survey URLs for *form_pk*.

    *urls* is a dict as returned by the Enketo API (keys like
    ``offline_url``, ``preview_url``, ``single_once_url``).
    """
    conn = _get_connection()
    if conn is None:
        return
    try:
        key = f"{SURVEY_URLS_PREFIX}{int(form_pk)}"
        mapping = {k: str(v) for k, v in urls.items() if v is not None}
        if mapping:
            pipe = conn.pipeline()
            pipe.hset(key, mapping=mapping)
            pipe.expire(key, _cache_ttl())
            pipe.execute()
    except Exception:
        logger.exception("enketo-links Redis write error")


def get_cached_preview_url(form_pk):
    """Read the cached preview URL for *form_pk*, or ``None``."""
    conn = _get_connection()
    if conn is None:
        return None
    try:
        return conn.get(f"{PREVIEW_URL_PREFIX}{int(form_pk)}")
    except Exception:
        logger.exception("enketo-links Redis read error")
        return None


def store_preview_url(form_pk, url):
    """Cache just the preview URL for *form_pk*."""
    conn = _get_connection()
    if conn is None:
        return
    try:
        conn.set(
            f"{PREVIEW_URL_PREFIX}{int(form_pk)}",
            str(url),
            ex=_cache_ttl(),
        )
    except Exception:
        logger.exception("enketo-links Redis write error")
