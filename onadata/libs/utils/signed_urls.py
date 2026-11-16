"""Sign attachment links in submission responses without changing stored JSON."""

import hashlib
import json
from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone
from itertools import islice
from urllib.parse import parse_qs, quote, urlsplit

from django.conf import settings
from django.core.files.storage import storages
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.cache import patch_cache_control, patch_vary_headers
from django.utils.dateparse import parse_datetime
from django.utils.http import http_date, quote_etag

from onadata.apps.logger.models import Attachment, Instance
from onadata.libs.utils.cache_tools import safe_cache_get, safe_cache_set
from onadata.libs.utils.logger_tools import get_storages_media_download_url

SAFETY_MARGIN = 30
BATCH_SIZE = 100


def _url_expiry(url, issued_at, lifetime):
    """Bound validity by the URL and any available signing credential expiry."""
    expires_at = issued_at + timedelta(seconds=lifetime)
    params = parse_qs(urlsplit(url).query)
    try:
        if "X-Amz-Date" in params and "X-Amz-Expires" in params:
            signed_at = datetime.strptime(params["X-Amz-Date"][0], "%Y%m%dT%H%M%SZ")
            url_expiry = signed_at.replace(tzinfo=datetime_timezone.utc) + timedelta(
                seconds=int(params["X-Amz-Expires"][0])
            )
        elif "Expires" in params:
            url_expiry = datetime.fromtimestamp(
                int(params["Expires"][0]), tz=datetime_timezone.utc
            )
        elif "se" in params:
            url_expiry = parse_datetime(params["se"][0])
        else:
            url_expiry = None
        if url_expiry is not None and timezone.is_aware(url_expiry):
            expires_at = min(expires_at, url_expiry)
    except (ValueError, OverflowError):
        # The configured lifetime still bounds URLs with an unknown expiry format.
        pass

    storage = storages["default"]
    # Inspect an already-created S3 connection. Do not create a second SDK client
    # or resolve credentials separately from the backend that signed the URL.
    connection = getattr(getattr(storage, "_connections", None), "connection", None)
    client = getattr(getattr(connection, "meta", None), "client", None)
    credentials = getattr(
        getattr(client, "_request_signer", None), "_credentials", None
    )
    for credential_expiry in (
        getattr(credentials, "_expiry_time", None),
        getattr(storage, "_user_delegation_key_expiry", None),
    ):
        if isinstance(credential_expiry, datetime):
            if timezone.is_naive(credential_expiry):
                credential_expiry = credential_expiry.replace(
                    tzinfo=datetime_timezone.utc
                )
            expires_at = min(expires_at, credential_expiry)
    return expires_at


class SignedAttachmentURLs:
    """Request-scoped transformation and freshness tracking for signed JSON."""

    def __init__(self, request):
        self.lifetime = settings.ATTACHMENT_SIGNED_URL_EXPIRATION
        directives = settings.CACHE_CONTROL_DIRECTIVES
        self.cache_lifetime = max(0, int(directives.get("max_age", 60)))
        if directives.get("no_cache") or directives.get("no_store"):
            self.cache_lifetime = 0
        self.refresh_at = timezone.now() + timedelta(seconds=self.cache_lifetime)
        storage = storages["default"]
        storage_config = {
            name: getattr(storage, name, None)
            for name in (
                "location",
                "bucket_name",
                "endpoint_url",
                "custom_domain",
                "region_name",
                "signature_version",
                "url_protocol",
                "account_name",
                "azure_container",
                "querystring_auth",
                "access_key",
                "secret_key",
                "security_token",
                "account_key",
            )
        }
        context = (
            request.build_absolute_uri(),
            request.accepted_media_type,
            request.user.pk,
            type(request.auth).__name__,
            getattr(request.auth, "scope", None),
            settings.STORAGES,
            storage_config,
            self.lifetime,
            self.cache_lifetime,
        )
        self.context_key = hashlib.sha256(
            json.dumps(context, default=str, sort_keys=True).encode()
        ).hexdigest()

    def _get_attachments(self, rows):
        """Look up live attachments for submissions authorized by the data view."""
        attachment_ids = set()
        for row in rows:
            for reference in row.get("_attachments") or []:
                if isinstance(reference, dict) and isinstance(reference.get("id"), int):
                    attachment_ids.add(reference["id"])

        return (
            Attachment.objects.filter(pk__in=attachment_ids, deleted_at__isnull=True)
            .only(
                "id",
                "instance",
                "xform",
                "media_file",
                "date_modified",
                "file_hash",
                "mimetype",
            )
            .in_bulk()
        )

    def _download_url(self, attachment):
        key_data = (
            self.context_key,
            attachment.pk,
            attachment.date_modified,
            attachment.media_file.name,
            attachment.file_hash,
            attachment.mimetype,
        )
        key = "signed-attachment:" + hashlib.sha256(str(key_data).encode()).hexdigest()
        now = timezone.now()
        cached = safe_cache_get(key)
        if cached is not None and cached["refresh_at"] > now:
            self.refresh_at = min(self.refresh_at, cached["refresh_at"])
            return cached["url"]

        filename = quote(attachment.media_file.name.split("/")[-1])
        url = get_storages_media_download_url(
            attachment.media_file.name,
            f'attachment; filename="{filename}"',
            attachment.mimetype,
            expires_in=self.lifetime,
        )
        if url is None:
            return None
        expires_at = _url_expiry(url, now, self.lifetime)
        refresh_at = min(
            now + timedelta(seconds=self.cache_lifetime),
            expires_at - timedelta(seconds=SAFETY_MARGIN),
        )
        self.refresh_at = min(self.refresh_at, refresh_at)
        if expires_at <= timezone.now():
            return None
        timeout = max(0, int((refresh_at - timezone.now()).total_seconds()))
        if timeout:
            safe_cache_set(key, {"url": url, "refresh_at": refresh_at}, timeout)
        return url

    def transform(self, items):
        """Copy and sign at most one batch of submissions at a time."""
        iterator = (
            items.iterator(chunk_size=BATCH_SIZE)
            if isinstance(items, QuerySet)
            else iter(items)
        )
        while batch := list(islice(iterator, BATCH_SIZE)):
            rows = [item.json if isinstance(item, Instance) else item for item in batch]
            attachments = self._get_attachments(rows)
            for row in rows:
                yield self._transform_row(row, attachments)

    def _transform_row(self, row, attachments):
        """Replace download links on copies of the submission and attachments."""
        result = row.copy()
        if not isinstance(row.get("_attachments"), list):
            return result
        result["_attachments"] = [reference.copy() for reference in row["_attachments"]]
        for reference in result["_attachments"]:
            attachment = attachments.get(reference.get("id"))
            if (
                attachment is None
                or attachment.instance_id != reference.get("instance")
                or attachment.instance_id != row.get("_id", reference.get("instance"))
                or attachment.media_file.name != reference.get("filename")
                or attachment.xform_id != reference.get("xform")
            ):
                continue
            url = self._download_url(attachment)
            if url is not None:
                reference["download_url"] = url
        return result

    def finalize_response(self, response):
        """Set validators and remaining freshness after buffered JSON is rendered."""
        remaining = max(0, int((self.refresh_at - timezone.now()).total_seconds()))
        response.headers.pop("Last-Modified", None)
        if response.streaming:
            remaining = 0
            response.headers.pop("ETag", None)
        else:
            digest = hashlib.sha256(
                self.context_key.encode() + response.content
            ).hexdigest()
            response["ETag"] = quote_etag(digest)
        response.headers.pop("Cache-Control", None)
        restrictions = {
            name: value
            for name, value in settings.CACHE_CONTROL_DIRECTIVES.items()
            if name in ("no_cache", "no_store", "no_transform")
        }
        patch_cache_control(
            response,
            private=True,
            max_age=remaining,
            must_revalidate=True,
            **restrictions,
        )
        deadline = timezone.now() if response.streaming else self.refresh_at
        response["Expires"] = http_date(deadline.timestamp())
        patch_vary_headers(response, ("Authorization", "Cookie"))
