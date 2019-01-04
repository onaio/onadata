from rest_framework.test import APIRequestFactory

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.libs.serializers.dataview_serializer import DataViewSerializer
from onadata.apps.logger.models import DataView


class TestDataViewSerializer(TestAbstractViewSet):

    def setUp(self):
        self._login_user_and_profile()
        self.factory = APIRequestFactory()

    def test_value_of_has_hxl_support_field(self):
        # age is the only field with hxl support in this context so any
        # dataview without the age column should have 'has_hxl_support'
        # set to False

        self._publish_form_with_hxl_support()
        name_and_columns = {
            'name_only': '["name"]',
            'age_only': '["age"]',
            'age_and_name': '["age", "name"]'
        }
        for name, columns in name_and_columns.items():
            data = {
                'name': name,
                'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
                'project': 'http://testserver/api/v1/projects/%s'
                           % self.project.pk,
                'columns': columns,
                'query': '[]'
            }

            self._create_dataview(data=data)

        request = self.factory.get('/', **self.extra)
        request.user = self.user

        def get_has_hxl_support_value(data_view_name):
            data_view = DataView.objects.get(name=data_view_name)
            data = DataViewSerializer(
                data_view, context={'request': request}
            ).data

            return data.get('has_hxl_support')

        self.assertFalse(get_has_hxl_support_value('name_only'))
        self.assertTrue(get_has_hxl_support_value('age_only'))
        self.assertTrue(get_has_hxl_support_value('age_and_name'))

    def test_name_and_xform_are_unique(self):
        """
        Test that we are preventing the creation of exactly the same dataview
        for the same form.
        """
        self._publish_form_with_hxl_support()
        request = self.factory.get('/', **self.extra)
        request.user = self.user

        payload = {
            'name': 'My DataView',
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project': 'http://testserver/api/v1/projects/%s'
                       % self.project.pk,
            'columns': '["name", "age"]',
            'query': '[]'
        }
        serializer = DataViewSerializer(
            data=payload, context={'request': request})
        is_valid = serializer.is_valid()
        self.assertTrue(is_valid)

        serializer.save()
        self.assertEquals(DataView.objects.count(), 1)

        # Try and save the same data again and confirm it fails
        serializer = DataViewSerializer(
            data=payload, context={'request': request})

        is_valid = serializer.is_valid()
        self.assertFalse(is_valid)

        expected_error_msg = 'The fields name, xform must make a unique set.'
        serializer.errors.get(
            'non_field_errors')[0].title() == expected_error_msg

        self.assertEquals(DataView.objects.count(), 1)
