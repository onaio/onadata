import os
from unittest import skip

from django.core.urlresolvers import reverse
from django.core.files.storage import get_storage_class
from pyxform.errors import PyXFormError

from onadata.apps.main.views import show
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import XForm
from onadata.libs.utils.logger_tools import XLSFormError


class TestFormErrors(TestBase):

    def _create_xform(self):
        self.xls_path = os.path.join(
            self.this_directory, "fixtures",
            "transportation", "transportation.xls")
        count = XForm.objects.count()
        self._publish_xls_file(self.xls_path)
        self.assertEqual(XForm.objects.count(), count + 1)
        self.xform = XForm.objects.all()[0]

    def test_bad_id_string(self):
        self._create_user_and_login()
        count = XForm.objects.count()
        xls_path = os.path.join(self.this_directory, "fixtures",
                                "transportation", "transportation.bad_id.xls")
        self.assertRaises(XLSFormError, self._publish_xls_file, xls_path)
        self.assertEquals(XForm.objects.count(), count)

    @skip
    def test_dl_no_xls(self):
        """
        Exports are built from the JSON form structure so we dont need the
        xls to generate an export
        """
        self._create_xform()
        self.xform.shared_data = True
        self.xform.save()
        default_storage = get_storage_class()()
        path = self.xform.xls.name
        self.assertEqual(default_storage.exists(path), True)
        default_storage.delete(path)
        self.assertEqual(default_storage.exists(path), False)
        url = reverse('xls_export', kwargs={'username': self.user.username,
                      'id_string': self.xform.id_string})
        response = self.anon.get(url)
        self.assertEqual(response.status_code, 404)

    def test_dl_xls_not_file(self):
        self._create_xform()
        self.xform.xls = "blah"
        self.xform.save()
        url = reverse('xls_export', kwargs={'username': self.user.username,
                      'id_string': self.xform.id_string})
        response = self.anon.get(url)
        self.assertEqual(response.status_code, 403)

    def test_nonexist_id_string(self):
        url = reverse(show, kwargs={'username': self.user.username,
                                    'id_string': '4444'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        response = self.anon.get(url)
        self.assertEqual(response.status_code, 404)

    def test_empty_submission(self):
        xls_path = os.path.join(
            self.this_directory, "fixtures",
            "transportation", "transportation.xls")
        xml_path = os.path.join(
            self.this_directory, "fixtures",
            "transportation", "transportation_empty_submission.xml")
        self._publish_xls_file(xls_path)
        self._make_submission(xml_path)
        self.assertTrue(self.response.status_code, 400)

    def test_submission_deactivated(self):
        self._create_xform()
        self.xform.downloadable = False
        self.xform.save()
        xml_path = os.path.join(
            self.this_directory, "fixtures",
            "transportation", "transportation_empty_submission.xml")
        self._make_submission(xml_path)
        self.assertTrue(self.response.status_code, 400)

    def test_spaced_xlsform(self):
        self._create_xform()
        count = XForm.objects.count()
        self.xform.save()
        xls_path = os.path.join(self.this_directory, "fixtures",
                                "transportation", "tutorial .xls")
        msg = u"The name 'tutorial ' is an invalid xml tag. Names must begin"\
            u" with a letter, colon, or underscore, subsequent characters "\
            u"can include numbers, dashes, and periods"
        self.assertRaisesMessage(
            PyXFormError, msg, self._publish_xls_file, xls_path)
        self.assertEquals(XForm.objects.count(), count)
