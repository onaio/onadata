import glob
import os

from django.conf import settings
from django.urls import reverse

from flaky import flaky

from onadata.apps.logger.import_tools import import_instances_from_zip
from onadata.apps.logger.models import Instance
from onadata.apps.logger.views import bulksubmission
from onadata.apps.main.tests.test_base import TestBase

CUR_PATH = os.path.abspath(__file__)
CUR_DIR = os.path.dirname(CUR_PATH)
DB_FIXTURES_PATH = os.path.join(CUR_DIR, "data_from_sdcard")


def images_count(username="bob"):
    images = glob.glob(
        os.path.join(settings.MEDIA_ROOT, username, "attachments", "*", "*")
    )
    return len(images)


class TestImportingDatabase(TestBase):
    def setUp(self):
        TestBase.setUp(self)
        self._publish_xls_file(
            os.path.join(
                settings.PROJECT_ROOT,
                "apps",
                "logger",
                "fixtures",
                "test_forms",
                "tutorial.xlsx",
            )
        )

    def tearDown(self):
        # delete everything we imported
        Instance.objects.all().delete()  # ?
        if settings.TESTING_MODE:
            images = glob.glob(
                os.path.join(
                    settings.MEDIA_ROOT, self.user.username, "attachments", "*", "*"
                )
            )
            for image in images:
                os.remove(image)

    @flaky
    def test_importing_b1_and_b2(self):
        """
        b1 and b2 are from the *same phone* at different times. (this
        might not be a realistic test)

        b1:
        1 photo survey (completed)
        1 simple survey (not marked complete)

        b2:
        1 photo survey (duplicate, completed)
        1 simple survey (marked as complete)
        """
        # import from sd card
        initial_instance_count = Instance.objects.count()
        initial_image_count = images_count()

        import_instances_from_zip(
            os.path.join(DB_FIXTURES_PATH, "bulk_submission.zip"), self.user
        )

        instance_count = Instance.objects.count()
        image_count = images_count()
        # Images are not duplicated
        # TODO: Figure out how to get this test passing.
        self.assertEqual(image_count, initial_image_count + 2)

        # Instance count should have incremented
        # by 1 (or 2) based on the b1 & b2 data sets
        self.assertEqual(instance_count, initial_instance_count + 2)

    def test_badzipfile_import(self):
        total, success, errors = import_instances_from_zip(
            os.path.join(CUR_DIR, "Water_Translated_2011_03_10.xml"), self.user
        )
        self.assertEqual(total, 0)
        self.assertEqual(success, 0)
        expected_errors = ["File is not a zip file"]
        self.assertEqual(errors, expected_errors)

    def test_bulk_import_post(self):
        zip_file_path = os.path.join(
            DB_FIXTURES_PATH, "bulk_submission_w_extra_instance.zip"
        )
        url = reverse(bulksubmission, kwargs={"username": self.user.username})
        with open(zip_file_path, "rb") as zip_file:
            post_data = {"zip_submission_file": zip_file}
            response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)

    def test_bulk_import_post_with_username_in_uppercase(self):
        zip_file_path = os.path.join(
            DB_FIXTURES_PATH, "bulk_submission_w_extra_instance.zip"
        )
        url = reverse(bulksubmission, kwargs={"username": self.user.username.upper()})
        with open(zip_file_path, "rb") as zip_file:
            post_data = {"zip_submission_file": zip_file}
            response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
