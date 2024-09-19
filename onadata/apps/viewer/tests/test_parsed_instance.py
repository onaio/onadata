import os
from datetime import datetime

from rest_framework.exceptions import ParseError

from onadata.apps.logger.models.instance import Instance
from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.viewer.models.parsed_instance import (
    get_where_clause,
    get_sql_with_params,
    _parse_sort_fields,
)
from onadata.apps.viewer.parsed_instance_tools import _parse_where


class TestParsedInstance(TestBase):
    def test_parse_where_clause_simple_query(self):
        query = {"name": "bla", "age": {"$gt": 18}}
        known_integers = ["age"]
        known_decimals = []
        or_where = ["is_active = true"]
        or_params = []
        where, where_params = _parse_where(
            query, known_integers, known_decimals, or_where, or_params
        )

        expected_where = [
            "json->>%s = %s",
            "CAST(json->>%s AS INT) > %s",
            "is_active = true",
        ]
        expected_where_params = ["name", "bla", "age", "18"]

        self.assertEqual(where, expected_where)
        self.assertEqual(where_params, expected_where_params)

    def test_parse_where_with_date_value(self):
        query = {
            "created_at": {"$gte": datetime(2022, 1, 1), "$lte": datetime(2022, 12, 31)}
        }
        known_integers = []
        known_decimals = []
        or_where = []
        or_params = []
        expected_where = ["json->>%s >= %s", "json->>%s <= %s"]
        expected_params = [
            "created_at",
            "2022-01-01 00:00:00",
            "created_at",
            "2022-12-31 00:00:00",
        ]

        where, params = _parse_where(
            query, known_integers, known_decimals, or_where, or_params
        )

        self.assertEqual(where, expected_where)
        self.assertEqual(params, expected_params)

    def test_parse_where_with_null_value(self):
        query = {"name": None}
        known_integers = []
        known_decimals = []
        or_where = []
        or_params = []
        expected_where = ["json->>%s IS NULL"]
        expected_params = ["name"]

        where, params = _parse_where(
            query, known_integers, known_decimals, or_where, or_params
        )

        self.assertEqual(where, expected_where)
        self.assertEqual(params, expected_params)

    def test_get_where_clause_with_json_query(self):
        query = '{"name": "bla"}'
        where, where_params = get_where_clause(query)
        self.assertEqual(where, ["json->>%s = %s"])
        self.assertEqual(where_params, ["name", "bla"])

    def test_get_where_clause_with_string_query(self):
        query = "bla"
        where, where_params = get_where_clause(query)
        self.assertEqual(where, ["json::text ~* cast(%s as text)"])
        self.assertEqual(where_params, ["bla"])

    def test_get_where_clause_with_integer(self):
        query = "11"
        where, where_params = get_where_clause(query)
        self.assertEqual(where, ["json::text ~* cast(%s as text)"])
        self.assertEqual(where_params, [11])

    def test_get_where_clause_or_date_range(self):
        """OR operation get_where_clause with date range"""
        query = (
            '{"$or": [{"_submission_time":{"$gte": "2024-09-17T13:39:40.001694+00:00", '
            '"$lte": "2024-09-17T13:39:40.001694+00:00"}}, '
            '{"_last_edited":{"$gte": "2024-04-01T13:39:40.001694+00:00", '
            '"$lte": "2024-04-01T13:39:40.001694+00:00"}}, '
            '{"_date_modified":{"$gte": "2024-04-01T13:39:40.001694+00:00", '
            '"$lte": "2024-04-01T13:39:40.001694+00:00"}}]}'
        )
        where, where_params = get_where_clause(query)
        self.assertEqual(
            where,
            [
                (
                    "((date_created >= %s AND date_created <= %s) OR "
                    "(last_edited >= %s AND last_edited <= %s) OR "
                    "(date_modified >= %s AND date_modified <= %s))"
                )
            ],
        )
        self.assertEqual(
            where_params,
            [
                "2024-09-17 13:39:40.001694+00:00",
                "2024-09-17 13:39:40.001694+00:00",
                "2024-04-01 13:39:40.001694+00:00",
                "2024-04-01 13:39:40.001694+00:00",
                "2024-04-01 13:39:40.001694+00:00",
                "2024-04-01 13:39:40.001694+00:00",
            ],
        )

    def test_invalid_date_format(self):
        """Inavlid date format is handled"""
        for json_date_field in ["_submission_time", "_date_modified", "_last_edited"]:
            query = {json_date_field: {"$lte": "watermelon"}}

            with self.assertRaises(ParseError):
                get_where_clause(query)

    def test_retrieve_records_based_on_form_verion(self):
        self._create_user_and_login()
        self._publish_transportation_form()
        initial_version = self.xform.version

        # 0 and 1 are indexes in a list representing transport instances with
        # the same form version - same as the transport form
        for a in [0, 1]:
            self._submit_transport_instance(survey_at=a)

        # the instances below have a different form vresion
        transport_instances_with_different_version = [
            "transport_2011-07-25_19-05-51",
            "transport_2011-07-25_19-05-52",
        ]

        for a in transport_instances_with_different_version:
            self._make_submission(
                os.path.join(
                    self.this_directory,
                    "fixtures",
                    "transportation",
                    "instances",
                    a,
                    a + ".xml",
                )
            )

        instances = Instance.objects.filter(xform__id_string=self.xform.id_string)
        instances_count = instances.count()
        self.assertEqual(instances_count, 4)

        # retrieve based on updated form version
        sql, params = get_sql_with_params(
            xform=self.xform, query='{"_version": "20170517"}'
        )
        instances = Instance.objects.raw(sql, params)
        self.assertEqual(2, len([instance for instance in instances]))

        # retrived record based on initial form version
        sql, params = get_sql_with_params(
            xform=self.xform, query='{"_version": "%s"}' % initial_version
        )
        instances = Instance.objects.raw(sql, params)
        self.assertEqual(2, len([instance for instance in instances]))

    def test_retrieve_records_using_list_of_queries(self):
        self._create_user_and_login()
        self._publish_transportation_form()

        # 0 and 1 are indexes in a list representing transport instances with
        # the same form version - same as the transport form
        for a in [0, 1]:
            self._submit_transport_instance(survey_at=a)

        transport_instances_with_different_version = [
            "transport_2011-07-25_19-05-51",
            "transport_2011-07-25_19-05-52",
        ]

        # make submissions
        for a in transport_instances_with_different_version:
            self._make_submission(
                os.path.join(
                    self.this_directory,
                    "fixtures",
                    "transportation",
                    "instances",
                    a,
                    a + ".xml",
                )
            )

        instances = Instance.objects.filter(
            xform__id_string=self.xform.id_string
        ).order_by("id")
        instances_count = instances.count()
        self.assertEqual(instances_count, 4)

        # bob accesses all records

        sql, params = get_sql_with_params(
            xform=self.xform, query={"_submitted_by": "bob"}
        )
        instances = Instance.objects.raw(sql, params)
        self.assertEqual(4, len([instance for instance in instances]))

        # only three records with name ambulance
        sql, params = get_sql_with_params(
            xform=self.xform, query=[{"_submitted_by": "bob"}, "ambulance"]
        )
        ambulance_instances = Instance.objects.raw(sql, params)
        self.assertEqual(3, len([instance for instance in ambulance_instances]))

        # create user alice
        user_alice = self._create_user("alice", "alice")
        # create user profile and set require_auth to false for tests
        profile, _ = UserProfile.objects.get_or_create(user=user_alice)
        profile.require_auth = False
        profile.save()

        # change ownership of first two records
        for i in instances[:2]:
            i.user = user_alice
            i.save()
        self.xform.save()

        # bob accesses only two record
        sql, params = get_sql_with_params(
            xform=self.xform, query={"_submitted_by": "bob"}
        )
        instances = Instance.objects.raw(sql, params)
        self.assertEqual(2, len([instance for instance in instances]))

        # both remaining records have ambulance
        sql, params = get_sql_with_params(
            xform=self.xform, query=[{"_submitted_by": "bob"}, "ambulance"]
        )
        instances_debug = list(
            self.xform.instances.filter(user__username="bob").values_list(
                "json", flat=True
            )
        )
        instances = Instance.objects.raw(sql, params)
        all_instances_debug = [instance.json for instance in instances]
        self.assertEqual(
            2,
            len(all_instances_debug),
            "Fields do not have ambulance. "
            f"Fields submitted by bob are {instances_debug}."
            f"All instances {all_instances_debug}",
        )

    def test_parse_sort_fields_function(self):
        """
        Test that the _parse_sort_fields function works as intended
        """
        fields = ["name", "_submission_time", "-_date_modified"]
        expected_return = ["name", "date_created", "-date_modified"]
        self.assertEqual([i for i in _parse_sort_fields(fields)], expected_return)
