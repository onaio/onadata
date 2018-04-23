# -*- coding=utf-8 -*-
"""
Test Renderer module.
"""
from collections import OrderedDict

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
        data = OrderedDict([
            ('_id', 1),
            ('_submission_time', '2018-03-05T13:57:26'),
            ('name', 'Bob Bob'),
            ('age', 10)
        ])
        expected_data = [
            ['2018-03-05T13:57:26', 13, None, 1, 'name', 'Bob Bob', None],
            ['2018-03-05T13:57:26', 19, None, 1, 'age', 10, None]
        ]  # yapf: disable
        result = [_ for _ in floip_rows_list(data)]
        self.assertEquals(result, expected_data)
