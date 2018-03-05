# -*- coding=utf-8 -*-
"""
Test Renderer module.
"""
from django.test import TestCase

from onadata.libs.renderers.renderers import floip_rows_list


class TestRenderers(TestCase):
    """
    Test Renderer class.
    """

    def test_floip_rows_list(self):
        """
        Test floip_rows_list() function.
        """
        data = {
            '_id': 1,
            '_submission_time': '2018-03-05T13:57:26',
            'name': 'Bob Bob',
            'age': 10
        }
        expected_data = [
            ['2018-03-05T13:57:26', 8, None, 1, 'age', 10, None],
            ['2018-03-05T13:57:26', 19, None, 1, 'name', 'Bob Bob', None]
        ]  # yapf: disable
        result = [_ for _ in floip_rows_list(data)]
        self.assertEquals(result, expected_data)
