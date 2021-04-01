from unittest import TestCase
from onadata.libs.models.sorting import json_order_by, json_order_by_params


class TestSorting(TestCase):
    def test_json_order_by(self):
        """
        Test that the json_order_by function works as intended
        1. Generates correct SQL ORDER BY query for JSON Fields
        2. Generates correct SQL ORDER BY query for none JSON fields;
           Includes the model field in the generated SQL
        """
        sort_list = ['name', '-qstn1', 'date_created']
        expected_return = (
            "ORDER BY  json->>%s ASC, json->>%s"
            " DESC, json->>%s ASC")
        self.assertEqual(json_order_by(sort_list), expected_return)

        sort_list = ['name', '-qstn1', '-date_created', 'date_modified']
        none_json_fields = {
            'date_created': 'created',
            'date_modified': 'last_modified'
        }
        model_name = "logger_instance"
        expected_return = (
            'ORDER BY  json->>%s ASC, json->>%s DESC,'
            '"logger_instance"."created" DESC,'
            '"logger_instance"."last_modified" ASC')
        self.assertEqual(
            json_order_by(sort_list, none_json_fields, model_name),
            expected_return)

    def test_json_order_by_params(self):
        """
        Test that the json_order_by_params works as intended
        1. Returns the correct JSON fields; without the - symbol
        2. Excludes none JSON fields in the return; The json_order_by function
           returns an SQL Statement with the fields in built
        """
        sort_list = ['name', 'qstn1', 'date_created']
        expected_return = ['name', 'qstn1', 'date_created']
        self.assertEqual(json_order_by_params(sort_list), expected_return)

        sort_list = ['name', '-qstn1', '-date_created', 'date_modified']
        none_json_fields = {
            'date_created': 'created',
            'date_modified': 'last_modified'
        }
        expected_return = ['name', 'qstn1']
        self.assertEqual(
            json_order_by_params(sort_list, none_json_fields), expected_return)
