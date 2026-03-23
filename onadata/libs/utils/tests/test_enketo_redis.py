"""Tests for onadata.libs.utils.enketo_redis."""

from unittest.mock import MagicMock, patch

import redis
from django.test import TestCase, override_settings

from onadata.libs.utils import enketo_redis
from onadata.libs.utils.enketo_redis import (
    PREVIEW_URL_PREFIX,
    SURVEY_URLS_PREFIX,
    delete_cached_urls,
    get_cached_preview_url,
    get_cached_survey_urls,
    store_preview_url,
    store_survey_urls,
)


class EnketoRedisDisabledTest(TestCase):
    """When ENKETO_LINKS_REDIS_URL is empty, all functions are no-ops."""

    def setUp(self):
        # Reset the module-level cached client so a client set by a
        # previous test doesn't leak into these "disabled" tests.
        enketo_redis._client = None

    @override_settings(ENKETO_LINKS_REDIS_URL="")
    def test_get_cached_survey_urls_returns_none(self):
        self.assertIsNone(get_cached_survey_urls(42))

    @override_settings(ENKETO_LINKS_REDIS_URL="")
    def test_store_survey_urls_does_not_raise(self):
        store_survey_urls(42, {"offline_url": "https://e.test/x"})

    @override_settings(ENKETO_LINKS_REDIS_URL="")
    def test_get_cached_preview_url_returns_none(self):
        self.assertIsNone(get_cached_preview_url(42))

    @override_settings(ENKETO_LINKS_REDIS_URL="")
    def test_store_preview_url_does_not_raise(self):
        store_preview_url(42, "https://e.test/preview")

    @override_settings(ENKETO_LINKS_REDIS_URL="")
    def test_delete_cached_urls_does_not_raise(self):
        delete_cached_urls(42)


@override_settings(ENKETO_LINKS_REDIS_URL="redis://localhost:6379/15")
class EnketoRedisCacheTest(TestCase):
    """Test caching with a mocked Redis connection."""

    def setUp(self):
        self.mock_redis = MagicMock()
        self.client_patcher = patch.object(
            enketo_redis,
            "_get_client",
            return_value=self.mock_redis,
        )
        self.client_patcher.start()

    def tearDown(self):
        self.client_patcher.stop()
        enketo_redis._client = None

    # --- survey URLs ---

    def test_get_cached_survey_urls_returns_dict_on_hit(self):
        cached = {
            "offline_url": "https://e.test/x",
            "preview_url": "https://e.test/p",
        }
        self.mock_redis.hgetall.return_value = cached
        result = get_cached_survey_urls(99)
        self.assertEqual(result, cached)
        self.mock_redis.hgetall.assert_called_once_with(
            f"{SURVEY_URLS_PREFIX}99"
        )

    def test_get_cached_survey_urls_returns_none_on_miss(self):
        self.mock_redis.hgetall.return_value = {}
        self.assertIsNone(get_cached_survey_urls(99))

    def test_get_cached_survey_urls_returns_none_on_error(self):
        self.mock_redis.hgetall.side_effect = redis.RedisError("boom")
        self.assertIsNone(get_cached_survey_urls(99))

    def test_store_survey_urls_writes_hash_with_ttl(self):
        urls = {
            "offline_url": "https://e.test/x",
            "preview_url": "https://e.test/p",
            "single_once_url": "https://e.test/s",
        }
        mock_pipe = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipe

        store_survey_urls(42, urls)

        mock_pipe.hset.assert_called_once()
        call_kwargs = mock_pipe.hset.call_args
        self.assertEqual(
            call_kwargs[1]["mapping"]["offline_url"],
            "https://e.test/x",
        )
        mock_pipe.expire.assert_called_once()
        mock_pipe.execute.assert_called_once()

    def test_store_survey_urls_skips_none_values(self):
        urls = {"offline_url": "https://e.test/x", "preview_url": None}
        mock_pipe = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipe

        store_survey_urls(42, urls)

        mapping = mock_pipe.hset.call_args[1]["mapping"]
        self.assertNotIn("preview_url", mapping)

    def test_store_survey_urls_skips_empty_mapping(self):
        mock_pipe = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipe

        store_survey_urls(42, {})

        mock_pipe.hset.assert_not_called()

    # --- preview URL ---

    def test_get_cached_preview_url_returns_string_on_hit(self):
        self.mock_redis.get.return_value = "https://e.test/p"
        result = get_cached_preview_url(99)
        self.assertEqual(result, "https://e.test/p")
        self.mock_redis.get.assert_called_once_with(
            f"{PREVIEW_URL_PREFIX}99"
        )

    def test_get_cached_preview_url_returns_none_on_miss(self):
        self.mock_redis.get.return_value = None
        self.assertIsNone(get_cached_preview_url(99))

    def test_store_preview_url_writes_with_ttl(self):
        store_preview_url(42, "https://e.test/p")
        self.mock_redis.set.assert_called_once()
        args, kwargs = self.mock_redis.set.call_args
        self.assertEqual(args[0], f"{PREVIEW_URL_PREFIX}42")
        self.assertEqual(args[1], "https://e.test/p")
        self.assertIn("ex", kwargs)

    # --- delete ---

    def test_delete_cached_urls_removes_both_keys(self):
        delete_cached_urls(42)
        self.mock_redis.delete.assert_called_once_with(
            f"{SURVEY_URLS_PREFIX}42",
            f"{PREVIEW_URL_PREFIX}42",
        )

    def test_delete_cached_urls_handles_error(self):
        self.mock_redis.delete.side_effect = redis.RedisError("boom")
        delete_cached_urls(42)  # should not raise

    # --- key safety ---

    def test_form_pk_is_cast_to_int(self):
        """Keys always use int(form_pk) to prevent injection."""
        self.mock_redis.hgetall.return_value = {}
        get_cached_survey_urls("42")
        self.mock_redis.hgetall.assert_called_once_with(
            f"{SURVEY_URLS_PREFIX}42"
        )
