from nose.tools import raises

from onadata.apps.api.tools import get_form_submissions_grouped_by_field
from onadata.apps.main.tests.test_base import TestBase


class TestTools(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()
        self._make_submissions()

    def test_get_form_submissions_grouped_by_field(self):
        count_key = 'count'
        field = '_xform_id_string'

        xform = self.user.xforms.all()[0]
        count = len(xform.surveys.all())

        result = get_form_submissions_grouped_by_field(xform, field)[0]

        self.assertEqual([field, count_key], sorted(result.keys()))
        self.assertEqual(result[count_key], count)

    def test_get_form_submissions_grouped_by_field_sets_name(self):
        count_key = 'count'
        field = '_xform_id_string'
        name = '_my_name'

        xform = self.user.xforms.all()[0]
        count = len(xform.surveys.all())

        result = get_form_submissions_grouped_by_field(xform, field, name)[0]

        self.assertEqual([name, count_key], sorted(result.keys()))
        self.assertEqual(result[count_key], count)

    @raises(ValueError)
    def test_get_form_submissions_grouped_by_field_bad_field(self):
        field = '_bad_field'
        xform = self.user.xforms.all()[0]

        get_form_submissions_grouped_by_field(xform, field)
