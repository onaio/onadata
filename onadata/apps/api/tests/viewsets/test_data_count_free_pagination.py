"""Count-free submission pages and validators."""

import json
from unittest.mock import patch
from urllib.parse import urlsplit

from django.core.cache import cache
from django.db import DataError, connection
from django.test import Client, RequestFactory, override_settings
from django.test.testcases import SerializeMixin
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

import defusedxml.ElementTree as ET
import requests

from onadata.apps.api.viewsets.data_viewset import DataViewSet
from onadata.apps.logger.models import Instance, XForm
from onadata.apps.main.models import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.models.share_xform import ShareXForm
from onadata.libs.pagination import CountFreePageNumberPagination
from onadata.libs.permissions import EditorMinorRole
from onadata.libs.serializers.data_serializer import DataInstanceXMLSerializer


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    STREAM_DATA=False,
)
class TestCountFreeDataPagination(SerializeMixin, TestBase):
    """Exercise the opt-in path through the submission endpoint."""

    lockfile = __file__

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self._create_user_and_login()
        self._publish_transportation_form()
        self._make_submissions()
        self.factory = RequestFactory()
        self.extra = {"HTTP_AUTHORIZATION": f"Token {self.user.auth_token.key}"}
        self.url = f"/api/v1/data/{self.xform.pk}"
        self.instances = list(self.xform.instances.order_by("pk"))
        self.ids = [instance.pk for instance in self.instances]
        for index, instance in enumerate(self.instances):
            instance.json.update(
                facility=51512444, endtime=f"2026-11-26T08:00:0{index}"
            )
            Instance.objects.filter(pk=instance.pk).update(json=instance.json)

    def get(self, params=None, *, url=None, pk=None, fmt=None, headers=None):
        """Call the view, or follow one of its navigation links."""
        params = {"include_count": "false", "page_size": 2, **(params or {})}
        request = self.factory.get(
            url or f"/api/v1/data/{pk or self.xform.pk}",
            data=None if url else params,
            **(self.extra if headers is None else headers),
        )
        return DataViewSet.as_view({"get": "list"})(
            request, pk=pk or self.xform.pk, format=fmt
        )

    @staticmethod
    def links(response):
        return {
            link["rel"]: link["url"]
            for link in requests.utils.parse_header_links(response.get("Link", ""))
            if "rel" in link
        }

    def test_pages_follow_links_without_duplicates(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["_id"] for row in response.data], self.ids[:2])
        self.assertEqual(set(self.links(response)), {"next"})

        response = self.get(url=self.links(response)["next"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["_id"] for row in response.data], self.ids[2:])
        self.assertEqual(set(self.links(response)), {"prev", "first"})
        self.assertIn("include_count=false", response["Link"])
        response = self.get(url=self.links(response)["prev"])
        self.assertEqual([row["_id"] for row in response.data], self.ids[:2])

        response = self.get({"page_size": 3, "page": 2})
        self.assertEqual([row["_id"] for row in response.data], self.ids[3:])
        self.assertNotIn("next", self.links(response))

    def test_sorted_pages_break_ties_by_submission_id(self):
        for sort, ids, direction in (
            ('{"facility":1}', self.ids, "ASC"),
            ('{"facility":1,"_id":-1}', self.ids[::-1], "DESC"),
        ):
            with self.subTest(sort=sort):
                with CaptureQueriesContext(connection) as queries:
                    response = self.get({"sort": sort})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([row["_id"] for row in response.data], ids[:2])
                response = self.get(url=self.links(response)["next"])
                self.assertEqual(response.status_code, 200)
                self.assertEqual([row["_id"] for row in response.data], ids[2:])
                self.assertNotIn("next", self.links(response))
                sql = next(
                    query["sql"]
                    for query in queries
                    if 'FROM "logger_instance"' in query["sql"]
                )
                self.assertIn(f', "logger_instance"."id" {direction} LIMIT 3', sql)

    def test_fetches_one_page_without_count_or_etag_sql(self):
        variants = (
            {},
            {"sort": '{"_submission_time":-1}'},
            {"sort": '{"endtime":-1}', "query": '{"facility":51512444}'},
            {"fields": '["_id","facility","endtime","missing"]'},
            {"fields": '["_id","endtime"]', "sort": '{"endtime":-1}'},
        )
        for streaming in (False, True):
            for params in variants:
                with self.subTest(
                    streaming=streaming, params=params
                ), override_settings(STREAM_DATA=streaming), patch(
                    "onadata.apps.api.viewsets.data_viewset.query_count",
                    side_effect=AssertionError("Unexpected submission count"),
                ), patch(
                    "onadata.apps.api.viewsets.data_viewset.get_etag_hash_from_query",
                    side_effect=AssertionError("Unexpected ETag query"),
                ), CaptureQueriesContext(
                    connection
                ) as queries:
                    response = self.get(params)
                    self.assertEqual(response.status_code, 200)
                    if streaming:
                        data = json.loads(b"".join(response.streaming_content))
                    else:
                        response.render()
                        data = response.data
                    self.assertEqual(len(data), 2)
                    self.assertTrue(response["ETag"].startswith('W/"'))

                instance_sql = [
                    query["sql"].lower().replace('"', "")
                    for query in queries
                    if "from logger_instance " in query["sql"].lower().replace('"', "")
                ]
                self.assertEqual(len(instance_sql), 1, instance_sql)
                self.assertIn("limit 3", instance_sql[0])
                self.assertNotIn("count(", instance_sql[0])
                self.assertNotIn("string_agg", instance_sql[0])

    def test_sorted_selected_pages_keep_filters_and_types(self):
        params = {
            "sort": '{"endtime":-1}',
            "query": '{"facility":51512444}',
            "fields": '["_id","facility","endtime","missing"]',
        }
        response = self.get(params)
        self.assertEqual([row["_id"] for row in response.data], self.ids[::-1][:2])
        self.assertEqual(response.data[0]["facility"], 51512444)
        self.assertIsNone(response.data[0]["missing"])
        self.assertEqual(
            set(response.data[0]), {"_id", "facility", "endtime", "missing"}
        )
        response = self.get(url=self.links(response)["next"])
        self.assertEqual([row["_id"] for row in response.data], self.ids[::-1][2:])
        self.assertNotIn("next", self.links(response))
        self.assertIn("query=", response["Link"])
        self.assertIn("fields=", response["Link"])
        self.assertIn("sort=", response["Link"])

    def test_empty_pages_and_invalid_options(self):
        response = self.get({"query": '{"facility":0}'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        self.assertNotIn("Link", response)
        for params, code in (
            ({"page": 3}, 404),
            ({"query": '{"facility":0}', "page": 2}, 404),
            ({"page": "last"}, 404),
            ({"page": "invalid"}, 404),
            ({"page": 0}, 404),
            ({"page": -1}, 404),
            ({"start": 0}, 400),
            ({"limit": 1}, 400),
            ({"fields": "[1]"}, 400),
        ):
            with self.subTest(params=params):
                self.assertEqual(self.get(params).status_code, code)
        self.assertEqual(len(self.get({"fields": ""}).data), 2)

    def test_invalid_options_return_public_error_messages(self):
        for params, detail in (
            ({"include_count": "invalid"}, "Use 'true' or 'false' for include_count."),
            ({"fields": "invalid"}, "Invalid query, sort, or fields parameter."),
            (
                {"fields": "[]"},
                "fields must be a non-empty JSON array of field names "
                "for JSON responses.",
            ),
        ):
            with self.subTest(params=params):
                response = self.get(params)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data, {"detail": detail})

    def test_database_errors_return_public_error_message(self):
        with patch.object(
            CountFreePageNumberPagination,
            "paginate_queryset",
            side_effect=DataError("Internal database error detail"),
        ):
            response = self.get()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {"detail": "Invalid query, sort, or fields parameter."}
        )

    def test_selected_json_values_and_literal_field_names(self):
        values = {
            "nested__field": "123",
            "quoted'field": True,
            "repeat/value": [1, "2", {"value": False}],
        }
        instance = self.instances[0]
        instance.json.update(values)
        Instance.objects.filter(pk=instance.pk).update(json=instance.json)
        response = self.get(
            {
                "query": json.dumps({"_id": instance.pk}),
                "fields": json.dumps(list(values)),
                "sort": json.dumps({"nested__field": 1}),
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [values])

    def test_default_and_true_keep_legacy_count_and_etag(self):
        for option in ({}, {"include_count": "true"}):
            with self.subTest(option=option), patch(
                "onadata.apps.api.viewsets.data_viewset.query_count", return_value=4
            ) as count, patch(
                "onadata.apps.api.viewsets.data_viewset.get_etag_hash_from_query",
                return_value="legacy-etag",
            ) as etag:
                request = self.factory.get(
                    self.url,
                    {"query": '{"facility":51512444}', "page_size": 1, **option},
                    **self.extra,
                )
                response = DataViewSet.as_view({"get": "list"})(
                    request, pk=self.xform.pk
                )
                self.assertEqual(response.status_code, 200)
                count.assert_called_once()
                etag.assert_called_once()
                self.assertIn("last", self.links(response))
                self.assertEqual(response["ETag"], "legacy-etag")

    def test_etag_tracks_returned_data_and_navigation(self):
        params = {"include_count": "false", "page_size": 1, "fields": '["facility"]'}
        client = Client()
        first = client.get(self.url, params, **self.extra)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(
            client.get(
                self.url, params, HTTP_IF_NONE_MATCH=first["ETag"], **self.extra
            ).status_code,
            304,
        )
        instance = self.instances[0]
        instance.json["facility"] = 42
        Instance.objects.filter(pk=instance.pk).update(json=instance.json)
        changed = client.get(
            self.url, params, HTTP_IF_NONE_MATCH=first["ETag"], **self.extra
        )
        self.assertEqual(changed.status_code, 200)
        self.assertNotEqual(first["ETag"], changed["ETag"])
        self.assertEqual(changed.json(), [{"facility": 42}])

        # An extra record's content does not contribute to the page's validator.
        other = self.instances[1]
        other.json["facility"] = 43
        Instance.objects.filter(pk=other.pk).update(json=other.json)
        self.assertEqual(
            client.get(self.url, params, **self.extra)["ETag"], changed["ETag"]
        )
        Instance.objects.filter(pk__in=self.ids[1:]).update(deleted_at=timezone.now())
        last = client.get(self.url, params, **self.extra)
        self.assertEqual(last.json(), changed.json())
        self.assertNotEqual(last["ETag"], changed["ETag"])
        self.assertNotIn("Link", last)

    def test_restricted_submissions_do_not_create_next_links(self):
        alice = self._create_user("alice", "password")
        MetaData.xform_meta_permission(self.xform, data_value="editor-minor")
        ShareXForm(self.xform, alice.username, EditorMinorRole.name).save()
        Instance.objects.filter(pk=self.ids[-1]).update(user=alice)
        headers = {"HTTP_AUTHORIZATION": f"Token {alice.auth_token.key}"}
        for params in ({}, {"sort": '{"endtime":-1}', "fields": '["_id"]'}):
            with self.subTest(params=params):
                response = self.get({"page_size": 1, **params}, headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual([row["_id"] for row in response.data], self.ids[-1:])
                self.assertNotIn("Link", response)

    def test_tags_and_decryption_filters_survive_json_sorting(self):
        for instance in (self.instances[0], self.instances[-1]):
            instance.tags.add("keep")
        Instance.objects.filter(pk__in=self.ids[:-1]).update(decryption_status="failed")
        response = self.get(
            {
                "page_size": 1,
                "sort": '{"endtime":-1}',
                "fields": '["_id"]',
                "tags": "keep",
                "decryption_status": "failed",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [{"_id": self.ids[0]}])
        self.assertNotIn("Link", response)

    def test_deleted_and_encrypted_rows_do_not_create_next_links(self):
        XForm.objects.filter(pk=self.xform.pk).update(is_managed=True)
        Instance.objects.filter(pk=self.ids[1]).update(deleted_at=timezone.now())
        cache.set(f"xfm-submissions-deleting-{self.xform.pk}", [self.ids[2]])
        Instance.objects.filter(pk=self.ids[3]).update(is_encrypted=True)
        for params in ({}, {"sort": '{"endtime":-1}', "fields": '["_id"]'}):
            with self.subTest(params=params):
                response = self.get({"page_size": 1, **params})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([row["_id"] for row in response.data], self.ids[:1])
                self.assertNotIn("Link", response)

    def test_shared_form_and_merged_dataset(self):
        XForm.objects.filter(pk=self.xform.pk).update(shared_data=True)
        response = self.get(headers={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["_id"] for row in response.data], self.ids[:2])

        merged = self._create_merged_dataset(make_submissions=True)
        response = self.get({"page_size": 1}, pk=merged.pk)
        self.assertEqual(response.status_code, 200)
        first_id = response.data[0]["_id"]
        next_url = self.links(response)["next"]
        self.assertEqual(urlsplit(next_url).path, f"/api/v1/data/{merged.pk}")
        response = self.get(url=next_url, pk=merged.pk)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data[0]["_id"], first_id)
        self.assertNotIn("next", self.links(response))

    def test_xml_pages_and_streams_do_not_run_count_or_etag_queries(self):
        for url, format_params, headers in self.xml_requests():
            for streaming in (False, True):
                with self.subTest(
                    url=url,
                    format_params=format_params,
                    headers=headers,
                    streaming=streaming,
                ):
                    self.assert_count_free_xml_page(
                        url, format_params, headers, streaming
                    )

    def xml_requests(self):
        return (
            (f"{self.url}.xml", {}, {}),
            (self.url, {"format": "xml"}, {}),
            (self.url, {}, {"HTTP_ACCEPT": "application/xml"}),
        )

    def assert_count_free_xml_page(self, url, format_params, headers, streaming):
        with override_settings(STREAM_DATA=streaming), patch(
            "onadata.apps.api.viewsets.data_viewset.query_count",
            side_effect=AssertionError("Unexpected submission count"),
        ), patch(
            "onadata.apps.api.viewsets.data_viewset.get_etag_hash_from_query",
            side_effect=AssertionError("Unexpected ETag query"),
        ), patch.object(
            DataInstanceXMLSerializer,
            "to_representation",
            autospec=True,
            side_effect=DataInstanceXMLSerializer.to_representation,
        ) as serialize, CaptureQueriesContext(
            connection
        ) as queries:
            response = Client().get(
                url,
                {
                    "include_count": "false",
                    "page": 2,
                    "page_size": 2,
                    "sort": '{"endtime":1}',
                    **format_params,
                },
                **self.extra,
                **headers,
            )
            self.assert_xml_page(response, self.ids[2:], streaming)
            self.assertTrue(response["ETag"].startswith('W/"'))
            self.assertEqual(serialize.call_count, len(self.ids[2:]))
        instance_sql = [
            query["sql"]
            for query in queries
            if 'FROM "logger_instance"' in query["sql"]
        ]
        self.assertEqual(len(instance_sql), 1, instance_sql)

    def assert_xml_page(self, response, ids, streaming):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.streaming, streaming)
        self.assertTrue(response["Content-Type"].startswith("application/xml"))
        content = (
            b"".join(response.streaming_content) if streaming else response.content
        )
        root = ET.fromstring(content)
        self.assertEqual(root.tag, "submission-batch")
        self.assertEqual([int(row.attrib["objectID"]) for row in root], ids)

    def test_legacy_xml_accept_keeps_fields_projection(self):
        client = Client()
        params = {"fields": '["endtime"]'}
        expected = [instance.json["endtime"] for instance in self.instances]
        response = client.get(
            self.url, params, HTTP_ACCEPT="application/xml", **self.extra
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/xml"))
        root = ET.fromstring(response.content)
        self.assertEqual([item.findtext("endtime") for item in root], expected)

        with override_settings(STREAM_DATA=True):
            response = client.get(
                self.url, params, HTTP_ACCEPT="application/xml", **self.extra
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response["Content-Type"].startswith("application/json"))
            data = json.loads(b"".join(response.streaming_content))
            self.assertEqual(data, [{"endtime": value} for value in expected])
