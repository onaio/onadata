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
            ['2018-03-05T13:57:26+00:00', 13, None, 1, 'name', 'Bob Bob',
             None],
            ['2018-03-05T13:57:26+00:00', 19, None, 1, 'age', 10, None]
        ]  # yapf: disable
        result = [_ for _ in floip_rows_list(data)]
        self.assertEquals(result, expected_data)

    def test_floip_rows_list_w_flow_fields(self):  # pylint: disable=C0103
        """
        Test floip_rows_list() function with sessionID and contactID
        """
        data = OrderedDict([
            ('_id', 1),
            ('_submission_time', '2018-03-05T13:57:26'),
            ('meta/contactID', '789'),
            ('meta/sessionID', '345'),
            ('name', 'Bob Bob'),
            ('age', 10)
        ])
        expected_data = [
            ['2018-03-05T13:57:26+00:00', 26, '789', '345', 'name', 'Bob Bob',
             None],
            ['2018-03-05T13:57:26+00:00', 34, '789', '345', 'age', 10, None]
        ]  # yapf: disable
        result = [_ for _ in floip_rows_list(data)]
        self.assertEquals(result, expected_data)
