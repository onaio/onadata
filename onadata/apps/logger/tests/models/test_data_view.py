from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models.data_view import append_where_list


class TestDataView(TestBase):
    def test_append_where_list(self):
        json_str = 'json->>%s'
        self.assertEqual(
            append_where_list('<>', [], json_str),
            [u'json->>%s <> %s']
        )
        self.assertEqual(
            append_where_list('!=', [], json_str),
            [u'json->>%s <> %s']
        )
        self.assertEqual(
            append_where_list('=', [], json_str),
            [u'json->>%s = %s']
        )
        self.assertEqual(
            append_where_list('>', [], json_str),
            [u'json->>%s > %s']
        )
        self.assertEqual(
            append_where_list('<', [], json_str),
            [u'json->>%s < %s']
        )
        self.assertEqual(
            append_where_list('>=', [], json_str),
            [u'json->>%s >= %s']
        )
        self.assertEqual(
            append_where_list('<=', [], json_str),
            [u'json->>%s <= %s']
        )
