#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import unittest

from decimal import Decimal

from rest_framework.exceptions import ParseError

from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.chart_tools import (
    build_chart_data_for_field,
    build_chart_data,
    calculate_ranges,
    get_choice_label,
    utc_time_string_for_javascript,
    get_field_choices,
    _flatten_multiple_dict_into_one
)
from onadata.apps.logger.models import XForm


def find_field_by_name(xform, field_name):
    return filter(
        lambda f: f.name == field_name, [e for e in xform.survey_elements])[0]


def find_field_by_xpath(xform, field_xpath):
    return filter(
        lambda f: f.get_abbreviated_xpath() == field_xpath,
        [e for e in xform.survey_elements])[0]


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

    def test_build_chart_data_for_field_on_submitted_by(self):
        data = build_chart_data_for_field(self.xform, '_submitted_by')
        self.assertEqual(data['field_name'], '_submitted_by')
        self.assertEqual(data['field_type'], 'text')
        self.assertEqual(data['data_type'], 'categorized')

    def test_build_chart_data_for_field_on_submitted_by_group_by(self):
        group_by_field = find_field_by_name(self.xform, 'pizza_fan')
        data = build_chart_data_for_field(self.xform, '_submitted_by',
                                          group_by=group_by_field)
        self.assertEqual(data['field_name'], '_submitted_by')
        self.assertEqual(data['field_type'], 'text')
        self.assertEqual(data['data_type'], 'categorized')
        self.assertEqual(data['grouped_by'], u'pizza_fan')
        self.assertEqual(data['data'],
                         [{'_submitted_by': u'bob',
                           'items': [{'count': 2L, u'pizza_fan': [u'No']}]}])

    def test_build_chart_data_for_field_on_duration(self):
        group_by_field = find_field_by_name(self.xform, 'pizza_fan')
        data = build_chart_data_for_field(self.xform, '_duration',
                                          group_by=group_by_field)
        self.assertEqual(data['field_name'], '_duration')
        self.assertEqual(data['field_type'], 'integer')
        self.assertEqual(data['data_type'], 'numeric')

    def test_build_chart_data_for_fields_with_accents(self):
        xls_path = os.path.join(
            self.this_directory, "fixtures",
            "sample_accent.xlsx")
        count = XForm.objects.count()
        self._publish_xls_file(xls_path)

        self.assertEquals(XForm.objects.count(), count + 1)

        xform = XForm.objects.all()[0]
        self.assertEqual(xform.title, "sample_accent")

        field = find_field_by_name(xform, u'tête')
        data = build_chart_data_for_field(self.xform, field)
        self.assertEqual(data['field_name'], u'tête')

        field = find_field_by_name(xform, u'té')
        data = build_chart_data_for_field(self.xform, field)
        self.assertEqual(data['field_name'], u'té')

        field = find_field_by_name(xform, u'père')
        data = build_chart_data_for_field(self.xform, field)
        self.assertEqual(data['field_name'], u'père')

    def test_build_chart_data_for_field_on_select_one(self):
        field_name = 'gender'
        field = find_field_by_name(self.xform, field_name)
        data = build_chart_data_for_field(self.xform, field)
        self.assertEqual(data['field_name'], field_name)
        self.assertEqual(data['field_type'], 'select one')
        self.assertEqual(data['data_type'], 'categorized')
        # map the list to a dict
        for d in data['data']:
            genders = d[field_name]
            count = d['count']
            self.assertEqual(type(genders), list)
            self.assertEqual(count, 1)

    def test_build_chart_data_for_field_on_grouped_field(self):
        field = find_field_by_xpath(self.xform, 'a_group/a_text')
        data = build_chart_data_for_field(self.xform, field)
        self.assertEqual(data['field_name'], 'a_text')
        self.assertEqual(data['field_xpath'], 'a_group/a_text')
        self.assertEqual(data['field_type'], 'text')
        self.assertEqual(data['data_type'], 'categorized')

    def test_build_chart_data_for_numeric_field_group_by_category_field(self):
        field = find_field_by_name(self.xform, 'net_worth')
        group_by_field = find_field_by_xpath(self.xform, 'pizza_type')
        data = build_chart_data_for_field(self.xform, field,
                                          group_by=group_by_field)

        self.assertEqual(data['field_name'], 'net_worth')
        self.assertEqual(data['field_xpath'], 'net_worth')
        self.assertEqual(data['field_type'], 'decimal')
        self.assertEqual(data['grouped_by'], 'pizza_type')
        self.assertEqual(data['data_type'], 'numeric')
        self.assertEqual(data['data'], [{'sum': 150000.0,
                                         'pizza_type': [],
                                         'mean': 75000.0}])

    def test_build_chart_data_calculate_field_group_by_category_field(self):
        field = find_field_by_name(self.xform, 'networth_calc')
        group_by_field = find_field_by_name(self.xform, 'pizza_fan')
        data = build_chart_data_for_field(self.xform, field,
                                          group_by=group_by_field)

        self.assertEqual(data['field_name'], 'networth_calc')
        self.assertEqual(data['field_xpath'], 'networth_calc')
        self.assertEqual(data['field_type'], 'calculate')
        self.assertEqual(data['grouped_by'], 'pizza_fan')
        self.assertEqual(data['data_type'], 'numeric')
        self.assertEqual(data['data'], [{'sum': 150000.0,
                                        'pizza_fan': [u'No'],
                                         'mean': 75000.0}])

    def test_build_chart_data_for_category_field_group_by_category_field(self):
        field = find_field_by_name(self.xform, 'gender')
        group_by_field = find_field_by_name(self.xform, 'pizza_fan')
        data = build_chart_data_for_field(self.xform, field,
                                          group_by=group_by_field)

        self.assertEqual(data['field_name'], 'gender')
        self.assertEqual(data['field_xpath'], 'gender')
        self.assertEqual(data['field_type'], 'select one')
        self.assertEqual(data['grouped_by'], 'pizza_fan')
        self.assertEqual(data['data_type'], 'categorized')
        self.assertEqual(data['data'], [
            {
                u'gender': [u'Male'],
                'items': [{'count': 1L, u'pizza_fan': [u'No']}]
            }, {
                u'gender': [u'Female'],
                'items': [{'count': 1L, u'pizza_fan': [u'No']}]
            }])

    def test_build_chart_category_field_group_by_category_field_in_group(self):
        field = find_field_by_name(self.xform, 'gender')
        group_by_field = find_field_by_xpath(self.xform, 'a_group/grouped')
        data = build_chart_data_for_field(self.xform, field,
                                          group_by=group_by_field)

        self.assertEqual(data['field_name'], 'gender')
        self.assertEqual(data['field_xpath'], 'gender')
        self.assertEqual(data['field_type'], 'select one')
        self.assertEqual(data['grouped_by'], 'a_group/grouped')
        self.assertEqual(data['data_type'], 'categorized')
        self.assertEqual(data['data'], [
            {u'gender': [u'Male'],
             'items': [{u'a_group/grouped': [u'Yes'], 'count': 1L}]},
            {u'gender': [u'Female'],
             'items': [{u'a_group/grouped': [u'Yes'], 'count': 1L}]}])

    def test_build_chart_data_cannot_group_by_field(self):
        field = find_field_by_name(self.xform, 'gender')
        group_by_field = find_field_by_xpath(self.xform, 'name')
        with self.assertRaises(ParseError) as e:
            build_chart_data_for_field(self.xform, field,
                                       group_by=group_by_field)

        self.assertEqual(str(e.exception), "Cannot group by name")

    def test_build_chart_data_output(self):
        data = build_chart_data(self.xform)
        self.assertIsInstance(data, list)
        # check expected fields
        expected_fields = sorted(['_submission_time', 'pizza_type', 'age',
                                  'gender', 'date', 'pizza_fan', 'net_worth',
                                  'start_time', 'end_time', 'today',
                                  'grouped'])
        data_field_names = sorted([f['field_name'] for f in data])
        self.assertEqual(expected_fields, data_field_names)

    def test_build_chart_data_strips_none_from_dates(self):
        # make the 3rd submission that doesnt have a date
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "api", "tests", "fixtures", "forms",
                            "tutorial", "instances", "3.xml")
        self._make_submission(path)
        field = find_field_by_name(self.xform, 'date')
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
        field = find_field_by_name(self.xform, 'food_type')
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
        field = find_field_by_name(self.xform, 'submit_date')
        data = build_chart_data_for_field(self.xform, field, language_index=1)
        self.assertEqual(data['field_label'], 'submit_date')

    def test_build_chart_data_with_nonexisting_field_xpath(self):
        # make the 3rd submission that doesnt have a date
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "api", "tests", "fixtures", "forms",
                            "tutorial", "instances", "3.xml")
        self._make_submission(path)
        field = find_field_by_name(self.xform, 'date')
        field.name = 'informed_consent/pas_denfants_elig/q7b'

        data = build_chart_data_for_field(self.xform, field)
        # create a list with comparisons to the dict values
        values = [d['date'] is not None for d in data['data']]
        self.assertTrue(all(values))

    def test_build_chart_data_with_field_name_with_lengh_65(self):
        # make the 3rd submission that doesnt have a date
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "api", "tests", "fixtures", "forms",
                            "tutorial", "instances", "3.xml")
        self._make_submission(path)
        field = find_field_by_name(self.xform, 'date')
        field.name = 'a' * 65

        data = build_chart_data_for_field(self.xform, field)
        self.assertEqual(data['field_name'], field.name)

    def mock_get_abbreviated_xpath(self):
        return 'informed_consent/pas_denfants_elig/date'

    def test_get_choice_label_with_single_select(self):
        choices = [{'control': {},
                    'name': 'Western Rural',
                    'label': 'Western Rural'},
                   {'control': {},
                    'name': 'Western Urban',
                    'label': 'Western Urban'}]
        string = 'Western Rural'

        self.assertEqual(get_choice_label(choices, string), [string])

    def test_get_choice_label_for_multi_select(self):
        pam = "PAM"
        croix_rouge = "Croix Rouge"

        choices = [{'control': {},
                    'name': '1',
                    'label': pam},
                   {'control': {},
                    'name': '2',
                    'label': croix_rouge},
                   {'control': {},
                    'name': '3',
                    'label': 'OXFAM'},
                   {'control': {},
                    'name': '4',
                    'label': 'Administration Locale'}]
        string = '1 2'

        self.assertEqual(get_choice_label(choices, string), [pam, croix_rouge])

    def test_get_choice_label_for_multi_select_with_spaces(self):
        """
        Select Multiple Fields with names with spaces will NEVER match
        their labels
        """
        pam = "PAM"
        croix_rouge = "Croix Rouge"
        both = "Sam Bla"

        choices = [{'control': {},
                    'name': pam,
                    'label': pam},
                   {'control': {},
                    'name': croix_rouge,
                    'label': croix_rouge},
                   {'control': {},
                    'name': both,
                    'label': both},
                   {'control': {},
                    'name': 'Administration Locale',
                    'label': 'Administration Locale'}]
        string = "{} {}".format(both, pam)

        self.assertNotIn(both, get_choice_label(choices, string))

    def test_get_choice_label_when_label_not_in_choice_list(self):
        choices = [{'control': {},
                    'name': 'Western Rural',
                    'label': 'Western Rural'},
                   {'control': {},
                    'name': 'Urban',
                    'label': 'Urban'},
                   {'control': {},
                    'name': 'Western Urban',
                    'label': 'Western Urban'}]
        string = 'Banadir'

        self.assertEqual(get_choice_label(choices, string), [string])

        string = 'Banadir Rural'

        self.assertEqual(get_choice_label(choices, string), [string])

        string = 'Banadir Urban'

        self.assertEqual(get_choice_label(choices, string), [string])

    def test_select_one_choices(self):
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "api", "tests", "fixtures", "forms",
                            "select_one_choices_test.xlsx")

        self._publish_xls_file_and_set_xform(path)

        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "api", "tests", "fixtures",
                            "select_one_choices_instance.xml")

        self._make_submission(path)

        field = find_field_by_name(self.xform, 'name_I')

        choices = get_field_choices(field, self.xform)
        data = build_chart_data_for_field(self.xform, field, choices=choices)

        expected_data = {
            'field_type': u'select one',
            'data_type': 'categorized',
            'field_xpath': u'name_I',
            'data': [
                {
                    'count': 1L,
                    'name_I': [u'Aynalem Tenaw']
                }
            ],
            'grouped_by': None,
            'field_label': u'Name of interviewer',
            'field_name': u'name_I'
        }

        self.assertEqual(data, expected_data)

    def test_select_one_choices_group_by(self):
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "api", "tests", "fixtures", "forms",
                            "select_one_choices_test.xlsx")

        self._publish_xls_file_and_set_xform(path)

        path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                            "apps", "api", "tests", "fixtures",
                            "select_one_choices_instance.xml")

        self._make_submission(path)

        group_by = find_field_by_name(self.xform, 'name_I')
        field = find_field_by_name(self.xform, 'toexppc')

        choices = get_field_choices(field, self.xform)

        data = build_chart_data_for_field(self.xform, field,
                                          choices=choices,
                                          group_by=group_by)

        expected_data = {
            'field_type': u'calculate',
            'data_type': 'numeric',
            'field_xpath': u'toexppc',
            'data': [
                {
                    'sum': Decimal('3.357142857142857'),
                    'name_I': [u'Aynalem Tenaw'],
                    'mean': Decimal('3.3571428571428570')
                }
            ],
            'grouped_by': u'name_I',
            'field_label': u'Total expenditure per capita',
            'field_name': u'toexppc'
        }

        self.assertEqual(data, expected_data)

    def test_build_chart_data_for_group_by_submitted_by(self):
        field = find_field_by_name(self.xform, 'gender')
        group_by_field = '_submitted_by'
        data = build_chart_data_for_field(self.xform, field,
                                          group_by=group_by_field)
        self.assertEqual(data['field_name'], 'gender')
        self.assertEqual(data['field_type'], 'select one')
        self.assertEqual(data['data_type'], 'categorized')
        self.assertEqual(data['grouped_by'], u'_submitted_by')
        self.assertEqual(data['data'],
                         [{
                             '_submitted_by': u'bob',
                             'count': 1L,
                             u'gender': [u'Male']
                         }, {
                             '_submitted_by': u'bob',
                             'count': 1L,
                             u'gender': [u'Female']
                         }
                         ])


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

    def test_flatten_multiple_dict_into_one(self):
        input_data = [{
            'count': 1L,
            'a_var': u'female',
            'a_super_group_name/extra_long_variable_name_to_see_if_postgresq':
            u'melon'
        }]
        expected_data = [{
            'items': [{
                'count': 1L,
                'a_super_group_name/extra_long_variable_name_to_see_if_postgresq': u'melon'  # noqa
            }],
            'a_var': u'female'
        }]
        group_by = 'a_super_group_name/extra_long_variable_name_to_see_if_postgresql_breaks_when_using_the_json_field_to_store_data'  # noqa
        result = _flatten_multiple_dict_into_one('a_var', group_by, input_data)
        self.maxDiff = None
        self.assertEqual(result, expected_data)
