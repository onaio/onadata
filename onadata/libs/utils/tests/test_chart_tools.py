import os
import unittest

from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.chart_tools import build_chart_data_for_field,\
    build_chart_data, utc_time_string_for_javascript, calculate_ranges


def find_field_by_name(dd, field_name):
        return filter(
            lambda f: f.name == field_name, [e for e in dd.survey_elements])[0]


class TestChartTools(TestBase):

    def setUp(self):
        super(TestChartTools, self).setUp()
        # create an xform
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "api", "tests", "fixtures", "forms",
                            "tutorial", "tutorial.xls")
        self._publish_xls_file_and_set_xform(path)
        # make a couple of submissions
        for i in range(1, 3):
            path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                "apps", "api", "tests", "fixtures", "forms",
                                "tutorial", "instances", "{}.xml".format(i))
            self._make_submission(path)

    def test_build_chart_data_for_field_on_submission_time(self):
        data = build_chart_data_for_field(self.xform, '_submission_time')
        self.assertEqual(data['field_name'], '_submission_time')
        self.assertEqual(data['field_type'], 'datetime')
        self.assertEqual(data['data_type'], 'time_based')

    def test_build_chart_data_for_field_on_select_one(self):
        dd = self.xform.data_dictionary()
        field = find_field_by_name(dd, 'gender')
        data = build_chart_data_for_field(self.xform, field)
        self.assertEqual(data['field_name'], 'gender')
        self.assertEqual(data['field_type'], 'select one')
        self.assertEqual(data['data_type'], 'categorized')
        # map the list to a dict
        values = dict([(d['gender'], d['count'], ) for d in data['data']])
        self.assertEqual(values, {
            'Male': 1,
            'Female': 1
        })

    def test_build_chart_data_for_field_on_grouped_field(self):
        dd = self.xform.data_dictionary()
        field = find_field_by_name(dd, 'a_text')
        data = build_chart_data_for_field(self.xform, field)
        self.assertEqual(data['field_name'], 'a_group-a_text')
        self.assertEqual(data['field_xpath'], 'a_text')
        self.assertEqual(data['field_type'], 'text')
        self.assertEqual(data['data_type'], 'categorized')

    def test_build_chart_data_output(self):
        data = build_chart_data(self.xform)
        self.assertIsInstance(data, list)
        # check expected fields
        expected_fields = sorted(['_submission_time', 'pizza_type', 'age',
                                  'gender', 'date', 'pizza_fan', 'net_worth',
                                  'start_time', 'end_time', 'today'])
        data_field_names = sorted([f['field_name'] for f in data])
        self.assertEqual(expected_fields, data_field_names)

    def test_build_chart_data_strips_none_from_dates(self):
        # make the 3rd submission that doesnt have a date
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "api", "tests", "fixtures", "forms",
                            "tutorial", "instances", "3.xml")
        self._make_submission(path)
        dd = self.xform.data_dictionary()
        field = find_field_by_name(dd, 'date')
        data = build_chart_data_for_field(self.xform, field)
        # create a list with comparisons to the dict values
        values = [d['date'] is not None for d in data['data']]
        self.assertTrue(all(values))

    def test_build_chart_data_for_field_with_language(self):
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "main", "tests", "fixtures",
                            "good_eats_multilang", "good_eats_multilang.xls")
        self._publish_xls_file_and_set_xform(path)
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "main", "tests", "fixtures",
                            "good_eats_multilang", "1.xml")
        self._make_submission(path)
        dd = self.xform.data_dictionary()
        field = find_field_by_name(dd, 'food_type')
        data = build_chart_data_for_field(self.xform, field, language_index=1)
        self.assertEqual(data['field_label'], u"Type of Eat")

    def test_build_chart_data_for_field_with_language_on_non_lang_field(self):
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "main", "tests", "fixtures",
                            "good_eats_multilang", "good_eats_multilang.xls")
        self._publish_xls_file_and_set_xform(path)
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "main", "tests", "fixtures",
                            "good_eats_multilang", "1.xml")
        self._make_submission(path)
        dd = self.xform.data_dictionary()
        field = find_field_by_name(dd, 'submit_date')
        data = build_chart_data_for_field(self.xform, field, language_index=1)
        self.assertEqual(data['field_label'], 'submit_date')


class TestChartUtilFunctions(unittest.TestCase):

    def test_utc_time_string_for_javascript(self):
        time_str = '2014-01-16T12:07:23.322+03'
        expected_time_str = '2014-01-16T12:07:23.322+0300'
        result = utc_time_string_for_javascript(time_str)
        self.assertEqual(result, expected_time_str)

    def test_raise_value_error_if_no_match(self):
        time_str = '2014-01-16T12:07:23.322'
        self.assertRaises(ValueError, utc_time_string_for_javascript, time_str)

    def test_raise_value_error_if_bad_time_zone(self):
        time_str = '2014-01-16T12:07:23.322+033'
        self.assertRaises(ValueError, utc_time_string_for_javascript, time_str)

    def test_calculate_range_on_normal_values(self):
        requested_page = 0
        items_per_page = 2
        num_items = 8
        ranges = calculate_ranges(requested_page, items_per_page, num_items)
        self.assertEqual(ranges, (0, 2))

    def test_calculate_range_when_page_is_beyond_limit(self):
        requested_page = 10
        items_per_page = 5
        num_items = 41
        ranges = calculate_ranges(requested_page, items_per_page, num_items)
        self.assertEqual(ranges, (41, 41))
