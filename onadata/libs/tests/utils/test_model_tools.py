from unittest import TestCase

from django.contrib.auth import get_user_model

from onadata.libs.utils.model_tools import queryset_iterator


class TestsForModelTools(TestCase):
    def test_queryset_iterator(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username='test', password='test', email='test@test.com')
        user_model.objects.create_user(
            username='test_2', password='test_2', email='test_2@test.com')
        user_model.objects.create_user(
            username='test_3', password='test_3', email='test@test_3.com')
        self.assertEquals(
            'generator',
            queryset_iterator(
                user_model.objects.all(), chunksize=1).__class__.__name__
        )
