from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.odk_logger.models import Instance


class TestInstance(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._publish_transportation_form_and_submit_instance()

    def test_stores_json(self):
        instances = Instance.objects.all()

        for instance in instances:
            self.assertNotEqual(instance.json, {})
