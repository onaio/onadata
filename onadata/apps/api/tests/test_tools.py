from datetime import datetime
from mock import patch
from nose.tools import raises

from onadata.apps.api.tools import get_form_submissions_grouped_by_field
from onadata.apps.main.tests.test_base import TestBase


class TestTools(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()

    @patch('django.utils.timezone.now')
    def test_get_form_submissions_grouped_by_field(self, mock_time):
        mock_time.return_value = datetime.now()
        self._make_submissions()

        count_key = 'count'
        fields = ['_submission_time', '_xform_id_string']

        xform = self.user.xforms.all()[0]
        count = len(xform.surveys.all())

        for field in fields:
            result = get_form_submissions_grouped_by_field(xform, field)[0]

            self.assertEqual([field, count_key], sorted(result.keys()))
            self.assertEqual(result[count_key], count)

    @patch('django.utils.timezone.now')
    def test_get_form_submissions_grouped_by_field_sets_name(self, mock_time):
        mock_time.return_value = datetime.now()
        self._make_submissions()

        count_key = 'count'
        fields = ['_submission_time', '_xform_id_string']
        name = '_my_name'

        xform = self.user.xforms.all()[0]
        count = len(xform.surveys.all())

        for field in fields:
            result = get_form_submissions_grouped_by_field(
                xform, field, name)[0]

            self.assertEqual([name, count_key], sorted(result.keys()))
            self.assertEqual(result[count_key], count)

    @raises(ValueError)
    def test_get_form_submissions_grouped_by_field_bad_field(self):
        self._make_submissions()

        field = '_bad_field'
        xform = self.user.xforms.all()[0]

        get_form_submissions_grouped_by_field(xform, field)
