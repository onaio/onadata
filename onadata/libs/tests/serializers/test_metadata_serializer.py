# -*- coding: utf-8 -*-
"""
Test onadata.libs.serializers.metadata_serializer
"""

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer


class TestMetaDataViewSerializer(TestAbstractViewSet):
    """
    Test MetaDataSerializer
    """

    def test_data_value_is_required(self):
        """
        Test media `data_value` is required.
        """
        data = {}
        serializer = MetaDataSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors['data_value'],
                         [u'This field is required.'])

    def test_media_url_validation(self):
        """
        Test media `data_value` url.
        """
        self._login_user_and_profile()
        self._publish_form_with_hxl_support()
        data = {
            'data_value': 'http://example.com',
            'data_type': 'media',
            'xform': self.xform.pk
        }
        serializer = MetaDataSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            serializer.errors['data_value'],
            [(u"Cannot get filename from URL %(data_value)s. URL should "
              u"include the filename e.g %(data_value)s/data.csv" % data)])
