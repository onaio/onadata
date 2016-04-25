from rest_framework.test import APIRequestFactory

from onadata.apps.restservice.models import RestService
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.libs.serializers.google_serializer import GoogleSheetsSerializer


class TestGoogleSheetSerializer(TestAbstractViewSet):

    def setUp(self):
        self.factory = APIRequestFactory()
        self._login_user_and_profile()

    def test_create_google_sheet_webhook(self):
        # create a project with a form
        self._publish_xls_form_to_project()

        pre_count = RestService.objects.filter(xform=self.xform).count()

        data = {
            "xform": self.xform.pk,
            "name": "googlesheets",
            "google_sheet_title": "Data-sync",
            "send_existing_data": False,
            "sync_updates": False
        }

        serializer = GoogleSheetsSerializer(data=data)
        serializer.save()

        count = RestService.objects.filter(xform=self.xform).count()

        self.assertEqual(pre_count + 1, count)

        gsheet_details = MetaData.get_gsheet_details(self.xform)
        self.assertEqual({
            'GSHEET_TITLE': 'Data-sync',
            'UPDATE_OR_DELETE_GSHEET_DATA': 'False'}, gsheet_details)
