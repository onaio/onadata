import os
from onadata.apps.logger.models.instance import Instance
from onadata.apps.viewer.models.parsed_instance import (
    get_where_clause, get_sql_with_params
)

from onadata.apps.main.tests.test_base import TestBase


class TestParsedInstance(TestBase):
    def test_get_where_clause_with_json_query(self):
        query = '{"name": "bla"}'
        where, where_params = get_where_clause(query)
        self.assertEqual(where, [u"json->>%s = %s"])
        self.assertEqual(where_params, ["name", "bla"])

    def test_get_where_clause_with_string_query(self):
        query = 'bla'
        where, where_params = get_where_clause(query)
        self.assertEqual(where, [u"json::text ~* cast(%s as text)"])
        self.assertEqual(where_params, ["bla"])

    def test_get_where_clause_with_integer(self):
        query = '11'
        where, where_params = get_where_clause(query)
        self.assertEqual(where, [u"json::text ~* cast(%s as text)"])
        self.assertEqual(where_params, [11])

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
            'transport_2011-07-25_19-05-51',
            'transport_2011-07-25_19-05-52'
        ]

        for a in transport_instances_with_different_version:
            self._make_submission(os.path.join(
                self.this_directory, 'fixtures',
                'transportation', 'instances', a, a + '.xml'))

        instances = Instance.objects.filter(
            xform__id_string=self.xform.id_string
        )
        instances_count = instances.count()
        self.assertEqual(instances_count, 4)

        # retrieve based on updated form version
        sql, params, records = get_sql_with_params(
            xform=self.xform, query='{"_version": "20170517"}'
        )

        self.assertEqual(2, records.count())

        # retrived record based on initial form version
        sql, params, records = get_sql_with_params(
            xform=self.xform, query='{"_version": "%s"}' % initial_version
        )
        self.assertEqual(2, records.count())
