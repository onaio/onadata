from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import Instance, Note


class TestNote(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()

    def test_no_created_by(self):
        self._publish_transportation_form_and_submit_instance()
        instance = Instance.objects.first()
        note = Note(
            instance=instance,
            instance_field="",
            created_by=None,
        )
        note.save()
        try:
            note.get_data()
        except AttributeError:
            self.fail("note.get_data() raised AttributeError unexpectedly!")
