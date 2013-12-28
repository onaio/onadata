from odk_logger.models import Instance
from main.tests.test_base import MainTestCase


class TestInstance(MainTestCase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._publish_transportation_form_and_submit_instance()

    def test_stores_json(self):
        instances = Instance.objects.all()

        for instance in instances:
            self.assertNotEqual(instance.json, {})
