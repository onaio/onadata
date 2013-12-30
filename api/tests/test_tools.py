from api.tools import get_form_submissions_grouped_by_field
from main.tests.test_base import MainTestCase


class TestTools(MainTestCase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()
        self._make_submissions()

    def test_form_submissions_grouped_by_field(self):
        xform = self.user.xforms.all()[0]
        field = '_status'
        count_key = 'count'
        count = len(xform.surveys.all())

        result = get_form_submissions_grouped_by_field(xform, field)[0]

        self.assertEqual([field, count_key], sorted(result.keys()))
        self.assertEqual(result[count_key], count)
