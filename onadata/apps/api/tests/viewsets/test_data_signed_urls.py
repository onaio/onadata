"""Signed attachment URLs on JSON submission responses."""

import json
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.core.cache import cache
from django.test import Client, override_settings
from django.utils import timezone

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.logger.models import Attachment
from onadata.apps.logger.models.instance import InstanceHistory
from onadata.apps.main.models import MetaData
from onadata.libs.models.share_xform import ShareXForm
from onadata.libs.permissions import EditorMinorRole, EditorRole
from onadata.libs.utils.signed_urls import SignedAttachmentURLs


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    CACHE_CONTROL_DIRECTIVES={"max_age": 60},
    STREAM_DATA=False,
)
class TestDataSignedURLs(TestAbstractViewSet):
    """Exercise signing for attachments of authorized submissions."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self._publish_xls_form_to_project()
        self._submit_transport_instance_w_attachment(delete_existing_attachments=False)
        self.client = Client()
        self.instance = self.attachment.instance
        self.url = f"/api/v1/data/{self.xform.pk}"
        self.now = timezone.now()
        clock = patch(
            "onadata.libs.utils.signed_urls.timezone.now", return_value=self.now
        )
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        signer = patch("onadata.libs.utils.signed_urls.get_storages_media_download_url")
        self.signer = signer.start()
        self.addCleanup(signer.stop)
        self.signer.side_effect = lambda *args, **kwargs: (
            f"https://storage.example.test/media?version={self.signer.call_count}"
        )

    def get(self, params=None, url=None, **headers):
        """Use the real request middleware, including conditional GET handling."""
        return self.client.get(
            url or self.url,
            params if params is not None else {"signed_urls": "true"},
            **{**self.extra, **headers},
        )

    def test_list_and_detail_only_replace_download_url(self):
        original = deepcopy(self.instance.json)
        history = InstanceHistory.objects.create(
            xform_instance=self.instance, xml=self.instance.xml, uuid=self.instance.uuid
        )
        history_json = deepcopy(history.json)
        for url in (self.url, f"{self.url}/{self.instance.pk}"):
            with self.subTest(url=url):
                response = self.get(url=url)
                self.assertEqual(response.status_code, 200)
                data = response.json()
                row = data[0] if isinstance(data, list) else data
                attachment = row["_attachments"][0]
                self.assertTrue(
                    attachment["download_url"].startswith("https://storage.")
                )
                expected = deepcopy(original["_attachments"][0])
                expected["download_url"] = attachment["download_url"]
                self.assertEqual(attachment, expected)
        self.instance.refresh_from_db()
        history.refresh_from_db()
        self.assertEqual(self.instance.json, original)
        self.assertEqual(history.json, history_json)
        self.assertEqual(
            self.get({}).json()[0]["_attachments"], original["_attachments"]
        )

    def test_default_and_false_do_not_sign(self):
        for params in ({}, {"signed_urls": "false"}):
            with self.subTest(params=params):
                response = self.get(params)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Cache-Control"], "max-age=60")
                self.assertTrue(
                    response.json()[0]["_attachments"][0]["download_url"].startswith(
                        "/api/v1/files/"
                    )
                )
        self.signer.assert_not_called()

    def test_cache_hit_and_304_do_not_extend_freshness(self):
        first = self.get()
        etag = first["ETag"]
        self.assertTrue(etag.startswith('"'))
        self.clock.return_value = self.now + timedelta(seconds=40)
        hit = self.get()
        self.assertEqual(hit.json(), first.json())
        self.assertEqual(hit["ETag"], etag)
        self.assertIn("max-age=20", hit["Cache-Control"])
        self.assertEqual(hit["Expires"], first["Expires"])
        conditional = self.get(HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(conditional.status_code, 304)
        self.assertIn("max-age=20", conditional["Cache-Control"])
        self.assertEqual(conditional["Expires"], first["Expires"])
        self.assertEqual(self.signer.call_count, 1)

        self.clock.return_value = self.now + timedelta(seconds=61)
        renewed = self.get(HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(renewed.status_code, 200)
        self.assertNotEqual(renewed["ETag"], etag)
        self.assertNotEqual(renewed.json(), first.json())
        self.assertEqual(self.signer.call_count, 2)

    @override_settings(ATTACHMENT_SIGNED_URL_EXPIRATION=45)
    def test_short_expiry_bounds_cache_and_http_freshness(self):
        first = self.get()
        self.assertIn("max-age=15", first["Cache-Control"])
        self.assertEqual(self.signer.call_args.kwargs["expires_in"], 45)
        self.clock.return_value = self.now + timedelta(seconds=16)
        renewed = self.get(HTTP_IF_NONE_MATCH=first["ETag"])
        self.assertEqual(renewed.status_code, 200)
        self.assertEqual(self.signer.call_count, 2)

    def test_sorted_selected_and_paginated_rows_are_signed(self):
        for extra in (
            {"sort": '{"date_created":1}'},
            {"sort": '{"today":1}'},
            {"fields": '["_attachments"]'},
            {"page": 1, "page_size": 1},
            {"start": 0, "limit": 1},
        ):
            with self.subTest(extra=extra):
                response = self.get({"signed_urls": "true", **extra})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(
                    response.json()[0]["_attachments"][0]["download_url"].startswith(
                        "https://storage."
                    )
                )
        selected = self.get({"signed_urls": "true", "fields": '["_id"]'})
        self.assertEqual(selected.json(), [{"_id": self.instance.pk}])

    def test_pagination_keeps_signed_urls_and_filters(self):
        self._submit_transport_instance(survey_at=1)
        params = {
            "signed_urls": "true",
            "page_size": 1,
            "sort": '{"date_created":1}',
            "fields": '["_attachments"]',
        }
        response = self.get(params)
        next_url = response["Link"].split(";")[0].strip("<>")
        next_params = parse_qs(urlsplit(next_url).query)
        for key, value in params.items():
            self.assertEqual(next_params[key], [str(value)])
        self.assertEqual(next_params["page"], ["2"])
        self.assertEqual(self.get(url=next_url, params={}).status_code, 200)

    def test_request_variants_and_users_have_separate_cache_entries(self):
        first = self.get()
        for params in (
            {"signed_urls": "true", "page": 1, "page_size": 1},
            {"signed_urls": "true", "query": json.dumps({"_id": self.instance.pk})},
            {"signed_urls": "true", "fields": '["_attachments"]'},
        ):
            self.assertNotEqual(self.get(params)["ETag"], first["ETag"])
        other = self._create_user("signed-reader", "password")
        ShareXForm(self.xform, other.username, EditorRole.name).save()
        other_response = self.get(HTTP_AUTHORIZATION=f"Token {other.auth_token.key}")
        self.assertEqual(other_response.status_code, 200)
        self.assertNotEqual(other_response.json(), first.json())
        self.assertEqual(self.signer.call_count, 5)

    def test_permission_change_is_checked_after_cache_warmup(self):
        other = self._create_user("signed-reader", "password")
        ShareXForm(self.xform, other.username, EditorRole.name).save()
        headers = {"HTTP_AUTHORIZATION": f"Token {other.auth_token.key}"}
        first = self.get(**headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.signer.call_count, 1)
        MetaData.xform_meta_permission(self.xform, data_value="editor-minor")
        ShareXForm(self.xform, other.username, EditorMinorRole.name).save()
        response = self.get(HTTP_IF_NONE_MATCH=first["ETag"], **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        self.assertEqual(self.signer.call_count, 1)

    def test_signed_attachments_inherit_submission_access(self):
        other = self._create_user("signed-reader", "password")
        ShareXForm(self.xform, other.username, EditorMinorRole.name).save()
        type(self.instance).objects.filter(pk=self.instance.pk).update(user=other)
        headers = {"HTTP_AUTHORIZATION": f"Token {other.auth_token.key}"}
        MetaData.xform_meta_permission(self.xform, data_value="editor-minor")
        ShareXForm(self.xform, other.username, EditorMinorRole.name).save()
        denied_file = self.get(
            url=f"/api/v1/files/{self.attachment.pk}",
            params={"filename": self.attachment.media_file.name},
            **headers,
        )
        self.assertEqual(denied_file.status_code, 404)
        for url in (self.url, f"{self.url}/{self.instance.pk}"):
            with self.subTest(url=url):
                first = self.get(url=url, **headers)
                self.assertEqual(first.status_code, 200)
                data = first.json()
                row = data[0] if isinstance(data, list) else data
                self.assertTrue(
                    row["_attachments"][0]["download_url"].startswith(
                        "https://storage."
                    )
                )
                calls = self.signer.call_count
                cached = self.get(url=url, **headers)
                self.assertEqual(cached.json(), data)
                self.assertEqual(self.signer.call_count, calls)
        self.assertEqual(self.signer.call_count, 2)

    def test_attachment_lookup_uses_one_query_per_batch(self):
        row = deepcopy(self.instance.json)
        attachment = Attachment.objects.bulk_create(
            [
                Attachment(
                    instance=self.instance,
                    xform=self.xform,
                    media_file=self.attachment.media_file.name,
                    mimetype=self.attachment.mimetype,
                )
            ]
        )[0]
        row["_attachments"].append({**row["_attachments"][0], "id": attachment.pk})
        rows = [row]
        request = self.get({}).renderer_context["request"]
        signer = SignedAttachmentURLs(request)
        with self.assertNumQueries(1):
            signed = list(signer.transform(rows))
        self.assertEqual(self.signer.call_count, 2)
        for row in signed:
            self.assertTrue(
                row["_attachments"][0]["download_url"].startswith("https://storage.")
            )
        with self.assertNumQueries(1):
            self.assertEqual(list(signer.transform(rows)), signed)
        self.assertEqual(self.signer.call_count, 2)
        with self.assertNumQueries(0):
            self.assertEqual(
                list(signer.transform([{"_id": self.instance.pk}])),
                [{"_id": self.instance.pk}],
            )

    @override_settings(
        MIDDLEWARE=(
            "django.middleware.cache.UpdateCacheMiddleware",
            *settings.MIDDLEWARE,
            "django.middleware.cache.FetchFromCacheMiddleware",
        )
    )
    def test_page_cache_does_not_bypass_authorization(self):
        first = self.get()
        self.assertEqual(first.status_code, 200)
        other = self._create_user("signed-denied", "password")
        denied = self.get(HTTP_AUTHORIZATION=f"Token {other.auth_token.key}")
        self.assertIn(denied.status_code, (403, 404))
        ordinary = self.get({})
        self.assertEqual(
            ordinary.json()[0]["_attachments"], self.instance.json["_attachments"]
        )
        self.assertEqual(self.get().json(), first.json())
        self.assertEqual(self.signer.call_count, 1)

    def test_stale_attachment_ownership_does_not_sign_another_submissions_file(self):
        original = deepcopy(self.instance.json)
        self._submit_transport_instance(survey_at=1)
        other = self.xform.instances.exclude(pk=self.instance.pk).get()
        original["_attachments"][0]["instance"] = other.pk
        type(self.instance).objects.filter(pk=self.instance.pk).update(json=original)
        response = self.get(url=f"{self.url}/{self.instance.pk}")
        self.assertEqual(response.json()["_attachments"], original["_attachments"])
        self.signer.assert_not_called()

    def test_deleted_attachments_do_not_receive_cached_urls(self):
        original = deepcopy(self.instance.json)
        self.get()
        self.signer.reset_mock()
        self.attachment.deleted_at = self.now
        self.attachment.save()
        # Keep a stale submission snapshot, as can occur before an async refresh.
        type(self.instance).objects.filter(pk=self.instance.pk).update(json=original)
        response = self.get()
        self.assertEqual(response.json()[0]["_attachments"], original["_attachments"])
        self.signer.assert_not_called()

    def test_local_storage_fallback_and_cache_failure(self):
        original = deepcopy(self.instance.json["_attachments"])
        self.signer.return_value = None
        self.signer.side_effect = None
        self.assertEqual(self.get().json()[0]["_attachments"], original)
        self.signer.return_value = "https://storage.example.test/signed"
        with (
            patch(
                "onadata.libs.utils.cache_tools.cache.get",
                side_effect=RuntimeError("cache unavailable"),
            ),
            patch(
                "onadata.libs.utils.cache_tools.cache.set",
                side_effect=RuntimeError("cache unavailable"),
            ),
            self.assertLogs("onadata.libs.utils.cache_tools", level="ERROR"),
        ):
            response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()[0]["_attachments"][0]["download_url"],
            self.signer.return_value,
        )

    @override_settings(STREAM_DATA=True)
    def test_stream_is_lazy_reuses_urls_and_revalidates_with_200(self):
        response = self.get(HTTP_IF_NONE_MATCH='"old-etag"')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)
        self.assertNotIn("ETag", response)
        self.assertEqual(
            response["Cache-Control"], "private, max-age=0, must-revalidate"
        )
        self.signer.assert_not_called()
        first = json.loads(b"".join(response.streaming_content))
        second = self.get(HTTP_IF_MODIFIED_SINCE="Wed, 31 Dec 2098 23:59:59 GMT")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(json.loads(b"".join(second.streaming_content)), first)
        self.assertEqual(self.signer.call_count, 1)

    @override_settings(STREAM_DATA=True)
    def test_sorted_and_selected_streams_sign_only_selected_attachments(self):
        for params in (
            {"signed_urls": "true", "sort": '{"date_created":1}'},
            {"signed_urls": "true", "fields": '["_attachments"]'},
            {"signed_urls": "true", "fields": '["_attachments"]', "page_size": 1},
        ):
            with self.subTest(params=params):
                response = self.get(params)
                rows = json.loads(b"".join(response.streaming_content))
                self.assertTrue(
                    rows[0]["_attachments"][0]["download_url"].startswith(
                        "https://storage."
                    )
                )
        selected = self.get({"signed_urls": "true", "fields": '["_id"]'})
        self.assertEqual(
            json.loads(b"".join(selected.streaming_content)),
            [{"_id": self.instance.pk}],
        )

    def test_history_does_not_sign(self):
        InstanceHistory.objects.create(
            xform_instance=self.instance, xml=self.instance.xml, uuid=self.instance.uuid
        )
        response = self.get(url=f"{self.url}/{self.instance.pk}/history")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.json()[0]["_attachments"][0]["download_url"].startswith(
                "/api/v1/files/"
            )
        )
        self.signer.assert_not_called()

    @override_settings(ATTACHMENT_SIGNED_URL_EXPIRATION=7200)
    @patch("onadata.libs.utils.image_tools.get_storages_media_download_url")
    def test_files_uses_the_same_configured_expiry(self, signer):
        signer.return_value = "https://storage.example.test/signed"
        response = self.get(
            url=f"/api/v1/files/{self.attachment.pk}",
            params={"filename": self.attachment.media_file.name},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(signer.call_args.kwargs["expires_in"], 7200)
