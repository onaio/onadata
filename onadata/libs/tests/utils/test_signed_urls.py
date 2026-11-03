"""Expiry and streaming bounds for signed attachment responses."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse
from django.test import SimpleTestCase
from django.utils import timezone

from onadata.libs.utils.signed_urls import BATCH_SIZE, SignedAttachmentURLs, _url_expiry


class TestSignedURLExpiry(SimpleTestCase):
    """Respect provider and credential lifetimes shorter than configuration."""

    def test_provider_expiry_bounds_configured_lifetime(self):
        now = timezone.now().replace(microsecond=0)
        expires_at = now + timedelta(seconds=45)
        urls = (
            f"https://s3.example/file?X-Amz-Date={now.strftime('%Y%m%dT%H%M%SZ')}&X-Amz-Expires=45",
            f"https://s3.example/file?Expires={int(expires_at.timestamp())}",
            f"https://azure.example/file?se={expires_at.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(_url_expiry(url, now, 3600), expires_at)

    def test_available_credential_expiry_bounds_url_validity(self):
        now = timezone.now()
        expiry = now + timedelta(seconds=45)
        credentials = SimpleNamespace(_expiry_time=expiry)
        storage = SimpleNamespace(
            _connections=SimpleNamespace(
                connection=SimpleNamespace(
                    meta=SimpleNamespace(
                        client=SimpleNamespace(
                            _request_signer=SimpleNamespace(_credentials=credentials)
                        )
                    )
                )
            )
        )
        with patch("onadata.libs.utils.signed_urls.storages", {"default": storage}):
            self.assertEqual(_url_expiry("https://s3.example/file", now, 3600), expiry)

    def test_transformation_does_not_consume_the_whole_iterator(self):
        request = SimpleNamespace(
            build_absolute_uri=lambda: "https://api.example/data/1?signed_urls=true",
            accepted_media_type="application/json",
            user=SimpleNamespace(pk=1),
            auth=None,
        )
        signer = SignedAttachmentURLs(request)
        consumed = []

        def rows():
            for pk in range(BATCH_SIZE * 3):
                consumed.append(pk)
                yield {"_id": pk, "_attachments": []}

        result = signer.transform(rows())
        self.assertEqual(consumed, [])
        self.assertEqual(next(result), {"_id": 0, "_attachments": []})
        self.assertEqual(len(consumed), BATCH_SIZE)

    def test_signed_variant_and_caller_are_part_of_the_etag(self):
        request = SimpleNamespace(
            build_absolute_uri=lambda: "https://api.example/data/1?signed_urls=true",
            accepted_media_type="application/json",
            user=SimpleNamespace(pk=1),
            auth=None,
        )
        first = HttpResponse(b"[]", content_type="application/json")
        SignedAttachmentURLs(request).finalize_response(first)
        request.user.pk = 2
        second = HttpResponse(b"[]", content_type="application/json")
        SignedAttachmentURLs(request).finalize_response(second)
        self.assertNotEqual(first["ETag"], second["ETag"])
