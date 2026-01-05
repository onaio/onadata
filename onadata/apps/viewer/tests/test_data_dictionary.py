"""Tests for onadata.apps.viewer.models.data_dictionary"""

import json

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import override_settings

from onadata.apps.logger.models.entity_list import EntityList
from onadata.apps.logger.models.follow_up_form import FollowUpForm
from onadata.apps.logger.models.kms import KMSKey
from onadata.apps.logger.models.registration_form import RegistrationForm
from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import ROLES
from onadata.libs.utils.user_auth import get_user_default_project


class DataDictionaryTestCase(TestBase):
    """Tests for model DataDictionary"""

    def setUp(self):
        super().setUp()

        self.project = get_user_default_project(self.user)
        self.registration_form = """
        | survey   |
        |          | type               | name                                       | label                    | save_to                                    |
        |          | geopoint           | location                                   | Tree location            | geometry                                   |
        |          | select_one species | species                                    | Tree species             | species                                    |
        |          | integer            | circumference                              | Tree circumference in cm | circumference_cm                           |
        |          | text               | intake_notes                               | Intake notes             |                                            |
        | choices  |                    |                                            |                          |                                            |
        |          | list_name          | name                                       | label                    |                                            |
        |          | species            | wallaba                                    | Wallaba                  |                                            |
        |          | species            | mora                                       | Mora                     |                                            |
        |          | species            | purpleheart                                | Purpleheart              |                                            |
        |          | species            | greenheart                                 | Greenheart               |                                            |
        | settings |                    |                                            |                          |                                            |
        |          | form_title         | form_id                                    | version                  | instance_name                              |
        |          | Trees registration | trees_registration                         | 2022110901               | concat(${circumference}, "cm ", ${species})|
        | entities |                    |                                            |                          |                                            |
        |          | list_name          | label                                      |                          |                                            |
        |          | trees              | concat(${circumference}, "cm ", ${species})|                          |                                            |"""
        self.follow_up_form = """
        | survey  |
        |         | type                           | name            | label                            | required |
        |         | select_one_from_file trees.csv | tree            | Select the tree you are visiting | yes      |
        | settings|                                |                 |                                  |          |
        |         | form_title                     | form_id         |  version                         |          |
        |         | Trees follow-up                | trees_follow_up |  2022111801                      |          |
        """

    def _replace_form(self, markdown, data_dict):
        survey, workbook_json = self.md_to_pyxform_survey_and_json(
            markdown, kwargs={"name": "data"}
        )
        data_dict.xml = survey.to_xml()
        data_dict.json = workbook_json
        data_dict.save()

    def test_create_registration_form(self):
        """Registration form created successfully"""
        xform = self._publish_markdown(self.registration_form, self.user)

        self.assertTrue(EntityList.objects.filter(name="trees").exists())
        self.assertTrue(
            RegistrationForm.objects.filter(
                xform=xform, entity_list__name="trees"
            ).exists()
        )

        reg_form = RegistrationForm.objects.get(xform=xform, entity_list__name="trees")

        self.assertEqual(
            reg_form.get_save_to(),
            {
                "geometry": "location",
                "species": "species",
                "circumference_cm": "circumference",
            },
        )
        self.assertTrue(reg_form.is_active)

    def test_create_registration_w_props_within_group(self):
        """Registration form with properties within group works"""
        md = """
        | survey   |
        |          | type               | name                                       | label                    | save_to                                    |
        |          | begin_group       | tree_details                                | Tree Details             |                                            |
        |          | geopoint           | location                                   | Tree location            | geometry                                   |
        |          | select_one species | species                                    | Tree species             | species                                    |
        |          | integer            | circumference                              | Tree circumference in cm | circumference_cm                           |
        |          | end_group         |                                             |                          |                                            |
        |          | text               | intake_notes                               | Intake notes             |                                            |
        | choices  |                    |                                            |                          |                                            |
        |          | list_name          | name                                       | label                    |                                            |
        |          | species            | wallaba                                    | Wallaba                  |                                            |
        |          | species            | mora                                       | Mora                     |                                            |
        |          | species            | purpleheart                                | Purpleheart              |                                            |
        |          | species            | greenheart                                 | Greenheart               |                                            |
        | settings |                    |                                            |                          |                                            |
        |          | form_title         | form_id                                    | version                  | instance_name                              |
        |          | Trees registration | trees_registration                         | 2022110901               | concat(${circumference}, "cm ", ${species})|
        | entities |                    |                                            |                          |                                            |
        |          | list_name          | label                                      |                          |                                            |
        |          | trees              | concat(${circumference}, "cm ", ${species})|                          |                                            |
        """
        xform = self._publish_markdown(md, self.user)

        self.assertTrue(EntityList.objects.filter(name="trees").exists())
        self.assertTrue(
            RegistrationForm.objects.filter(
                xform=xform, entity_list__name="trees"
            ).exists()
        )

        reg_form = RegistrationForm.objects.get(xform=xform, entity_list__name="trees")

        self.assertEqual(
            reg_form.get_save_to(),
            {
                "geometry": "location",
                "species": "species",
                "circumference_cm": "circumference",
            },
        )
        self.assertTrue(reg_form.is_active)

    def test_create_follow_up_form(self):
        """Follow up form created successfully"""
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        xform = self._publish_markdown(self.follow_up_form, self.user)

        self.assertTrue(
            FollowUpForm.objects.filter(entity_list__name="trees", xform=xform).exists()
        )
        self.assertTrue(
            MetaData.objects.filter(
                object_id=xform.pk,
                data_type="media",
                data_value=f"entity_list {entity_list.pk} trees",
            ).exists()
        )

        follow_up_form = FollowUpForm.objects.get(
            entity_list__name="trees", xform=xform
        )

        self.assertTrue(follow_up_form.is_active)

    def test_create_follow_up_w_props_within_group(self):
        """Follow up form with dataset within group works"""
        md = """
        | survey  |
        |         | type                           | name            | label                            | required |
        |         | begin_group                    | tree_details    | Tree Details                    |          |
        |         | select_one_from_file trees.csv | tree            | Select the tree you are visiting | yes      |
        |         | end_group                      |                 |                                  |          |
        | settings|                                |                 |                                  |          |
        |         | form_title                     | form_id         |  version                         |          |
        |         | Trees follow-up                | trees_follow_up |  2022111801                      |          |
        """
        # Simulate existing trees dataset
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        xform = self._publish_markdown(md, self.user)

        self.assertTrue(
            FollowUpForm.objects.filter(entity_list__name="trees", xform=xform).exists()
        )
        self.assertTrue(
            MetaData.objects.filter(
                object_id=xform.pk,
                data_type="media",
                data_value=f"entity_list {entity_list.pk} trees",
            ).exists()
        )

        follow_up_form = FollowUpForm.objects.get(
            entity_list__name="trees", xform=xform
        )

        self.assertTrue(follow_up_form.is_active)

    def test_create_follow_w_select_multiple(self):
        """A form with select multiple form EntityList works"""
        md = """
        | survey  |
        |         | type                           | name            | label                            | required |
        |         | select_multiple trees.csv      | trees           | Select the trees you are visiting | yes      |
        | settings|                                |                 |                                  |          |
        |         | form_title                     | form_id         |  version                         |          |
        |         | Trees follow-up                | trees_follow_up |  2022111801                      |          |
        """
        # Simulate existing trees dataset
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        xform = self._publish_markdown(md, self.user)

        self.assertTrue(
            FollowUpForm.objects.filter(entity_list__name="trees", xform=xform).exists()
        )
        self.assertTrue(
            MetaData.objects.filter(
                object_id=xform.pk,
                data_type="media",
                data_value=f"entity_list {entity_list.pk} trees",
            ).exists()
        )

    def test_follow_up_form_list_not_found(self):
        """Entity list not found when publishing followup form"""
        self._publish_markdown(self.follow_up_form, self.user)
        self.assertEqual(XForm.objects.count(), 1)
        self.assertEqual(FollowUpForm.objects.count(), 0)

    def test_replace_form_entities_save_to(self):
        """Replacing entity properties works"""
        data_dict = self._publish_markdown(self.registration_form, self.user)
        registration_form = RegistrationForm.objects.first()
        self.assertEqual(
            registration_form.get_save_to(),
            {
                "geometry": "location",
                "species": "species",
                "circumference_cm": "circumference",
            },
        )
        md = """
        | survey   |
        |          | type               | name                                       | label                    | save_to                                    |
        |          | geopoint           | location                                   | Tree location            | location                                   |
        |          | select_one species | species                                    | Tree species             | species                                    |
        |          | integer            | circumference                              | Tree circumference in cm |                                            |
        |          | text               | intake_notes                               | Intake notes             |                                            |
        | choices  |                    |                                            |                          |                                            |
        |          | list_name          | name                                       | label                    |                                            |
        |          | species            | wallaba                                    | Wallaba                  |                                            |
        |          | species            | mora                                       | Mora                     |                                            |
        |          | species            | purpleheart                                | Purpleheart              |                                            |
        |          | species            | greenheart                                 | Greenheart               |                                            |
        | settings |                    |                                            |                          |                                            |
        |          | form_title         | form_id                                    | version                  | instance_name                              |
        |          | Trees registration | trees_registration                         | 2022110901               | concat(${circumference}, "cm ", ${species})|
        | entities |                    |                                            |                          |                                            |
        |          | list_name          | label                                      |                          |                                            |
        |          | trees              | concat(${circumference}, "cm ", ${species})|                          |                                            |"""
        self._replace_form(md, data_dict)
        registration_form.refresh_from_db()
        self.assertEqual(
            registration_form.get_save_to(),
            {
                "location": "location",
                "species": "species",
            },
        )

    def test_replace_form_entities_list_name(self):
        """Replacing entities list_name works"""
        data_dict = self._publish_markdown(self.registration_form, self.user)
        # name changed entities list_name to `trees_registration`
        md = """
        | survey   |
        |          | type               | name                                       | label                    | save_to                                    |
        |          | geopoint           | location                                   | Tree location            | geometry                                   |
        |          | select_one species | species                                    | Tree species             | species                                    |
        |          | integer            | circumference                              | Tree circumference in cm | circumference_cm                           |
        |          | text               | intake_notes                               | Intake notes             |                                            |
        | choices  |                    |                                            |                          |                                            |
        |          | list_name          | name                                       | label                    |                                            |
        |          | species            | wallaba                                    | Wallaba                  |                                            |
        |          | species            | mora                                       | Mora                     |                                            |
        |          | species            | purpleheart                                | Purpleheart              |                                            |
        |          | species            | greenheart                                 | Greenheart               |                                            |
        | settings |                    |                                            |                          |                                            |
        |          | form_title         | form_id                                    | version                  | instance_name                              |
        |          | Trees registration | trees_registration                         | 2022110901               | concat(${circumference}, "cm ", ${species})|
        | entities |                    |                                            |                          |                                            |
        |          | list_name          | label                                      |                          |                                            |
        |          | trees_registration | concat(${circumference}, "cm ", ${species})|                          |                                            |"""
        self._replace_form(md, data_dict)
        # A new EntityList is created
        self.assertTrue(EntityList.objects.filter(name="trees_registration").exists())
        # A new RegistrationForm referencing the new entity list is
        # created for the XForm
        latest_form = XForm.objects.all().order_by("-pk").first()
        self.assertTrue(
            RegistrationForm.objects.filter(
                entity_list__name="trees_registration", xform=latest_form
            ).exists()
        )
        # RegistrationForm contributing to the previous EntityList
        # should be disabled
        registration_forms = RegistrationForm.objects.all().order_by("pk")
        prev_registration_form = registration_forms[0]
        new_registration_form = registration_forms[1]
        self.assertFalse(prev_registration_form.is_active)
        self.assertTrue(new_registration_form.is_active)

    def test_replace_form_remove_entities(self):
        """Removing entities definition disables registration form"""
        data_dict = self._publish_markdown(self.registration_form, self.user)
        md = """
        | survey   |
        |          | type               | name               | label                    |                                            |
        |          | geopoint           | location           | Tree location            |                                            |
        |          | select_one species | species            | Tree species             |                                            |
        |          | integer            | circumference      | Tree circumference in cm |                                            |
        |          | text               | intake_notes       | Intake notes             |                                            |
        | choices  |                    |                    |                          |                                            |
        |          | list_name          | name               | label                    |                                            |
        |          | species            | wallaba            | Wallaba                  |                                            |
        |          | species            | mora               | Mora                     |                                            |
        |          | species            | purpleheart        | Purpleheart              |                                            |
        |          | species            | greenheart         | Greenheart               |                                            |
        | settings |                    |                    |                          |                                            |
        |          | form_title         | form_id            | version                  | instance_name                              |
        |          | Trees registration | trees_registration | 2022110901               | concat(${circumference}, "cm ", ${species})|"""
        self._replace_form(md, data_dict)
        registration_form = RegistrationForm.objects.first()
        self.assertFalse(registration_form.is_active)

    def test_registration_form_reactivated(self):
        """Existing RegistrationForm if disabled is activated"""
        data_dict = self._publish_markdown(self.registration_form, self.user)
        registration_form = RegistrationForm.objects.first()
        # Disable registration form
        registration_form.is_active = False
        registration_form.save()
        registration_form.refresh_from_db()
        self.assertFalse(registration_form.is_active)
        # Replace
        self._replace_form(self.registration_form, data_dict)
        registration_form.refresh_from_db()
        self.assertTrue(registration_form.is_active)

    def test_followup_form_remove_dataset(self):
        """FollowUpForm is deactivated if entity dataset reference removed"""
        # Simulate existing trees dataset
        EntityList.objects.create(name="trees", project=self.project)
        data_dict = self._publish_markdown(self.follow_up_form, self.user)
        follow_up_form = FollowUpForm.objects.filter(entity_list__name="trees").first()
        self.assertTrue(follow_up_form.is_active)
        # Replace
        md = """
        | survey  |
        |         | type            | name             | label                         |
        |         | text            | tree             | What is the name of the tree? |
        |         | integer         | circumference    | Tree circumeference in cm     |
        | settings|                 |                  |                               |
        |         | form_title      | form_id          |  version                      |
        |         | Trees follow-up | trees_follow_up  |  2022111801                   |
        """
        self._replace_form(md, data_dict)
        follow_up_form.refresh_from_db()
        self.assertFalse(follow_up_form.is_active)

    def test_reactivate_followup_form(self):
        """FollowUpForm is re-activated if previously activated

        If entity dataset is referenced again, deactivate FollowUpForm
        is re-activated
        """
        # Simulate existing deactivate FollowUpForm
        md = """
        | survey  |
        |         | type            | name           | label                         |
        |         | text            | tree           | What is the name of the tree? |
        |         | integer         | circumference  | Tree circumeference in cm     |
        | settings|                 |                |                               |
        |         | form_title      | form_id        |  version                      |
        |         | Trees follow-up | trees_follow_up|  2022111801                   |
        """
        data_dict = self._publish_markdown(md, self.user)
        entity_list = EntityList.objects.create(name="trees", project=self.project)
        xform = XForm.objects.first()
        form = FollowUpForm.objects.create(
            entity_list=entity_list, xform=xform, is_active=False
        )
        self.assertFalse(form.is_active)
        # Replace
        self._replace_form(self.follow_up_form, data_dict)
        form.refresh_from_db()
        self.assertTrue(form.is_active)

    def test_cache_invalidated(self):
        """Various caches are invalidated when form is created/replaced"""
        cache_keys = [
            f"ps-project_forms-{self.project.pk}",
            f"ps-project_base_forms-{self.project.pk}",
            f"xfm-list-{self.project.pk}-Project-anon",
        ]

        for role in ROLES:
            cache_keys.append(f"xfm-list-{self.project.pk}-Project-{role}")

        for key in cache_keys:
            cache.set(key, "data")

        data_dict = self._publish_markdown(self.registration_form, self.user)

        for key in cache_keys:
            self.assertIsNone(cache.get(key))

        # Reset caches
        xform = XForm.objects.get(pk=data_dict.pk)
        cache_keys.append(f"xfm-list-{xform.pk}-XForm-anon")

        for role in ROLES:
            cache_keys.append(f"xfm-list-{xform.pk}-XForm-{role}")

        for key in cache_keys:
            cache.set(key, "data")

        # Replace form
        self._replace_form(self.follow_up_form, data_dict)

        for key in cache_keys:
            self.assertIsNone(cache.get(key))

    def test_kms_encryption(self):
        """XForm is auto-encrypted using managed key."""
        org = self._create_organization(
            username="valigetta", name="Valigetta Inc", created_by=self.user
        )
        content_type = ContentType.objects.get_for_model(org)
        kms_key = KMSKey.objects.create(
            key_id="fake-key-id",
            description="Key-2025-04-03",
            public_key="fake-pub-key",
            content_type=content_type,
            object_id=org.pk,
            provider=KMSKey.KMSProvider.AWS,
        )
        md = """
        | survey  |
        |         | type        | name           | label      |
        |         | text        | name           | First Name |
        |         | text        | age            | Age        |
        | settings|             |                |            |
        |         | form_title  | form_id        |            |
        |         | Students    | students       |            |
        """
        # XForm is encrypted if config is enabled
        with override_settings(KMS_AUTO_ENCRYPT_XFORM=True):
            xform = self._publish_markdown(md, org.user, id_string="a")
            xform.refresh_from_db()

            self.assertTrue(xform.encrypted)
            self.assertTrue(xform.is_managed)

        # XForm is not encrypted if config disabled
        with override_settings(KMS_AUTO_ENCRYPT_XFORM=False):
            xform = self._publish_markdown(md, org.user, id_string="b")
            xform.refresh_from_db()

            self.assertFalse(xform.encrypted)

        # XForm is not encrypted if config missing
        xform = self._publish_markdown(md, org.user, id_string="c")
        xform.refresh_from_db()

        self.assertFalse(xform.encrypted)

        # XForm is not encrypted if owner is not organization
        with override_settings(KMS_AUTO_ENCRYPT_XFORM=True):
            xform = self._publish_markdown(md, self.user, id_string="d")
            xform.refresh_from_db()

            self.assertFalse(xform.encrypted)

        # XForm is not encrypted if already encrypted and
        # KMS_OVERRIDE_CUSTOM_ENCRYPTION is False
        with override_settings(
            KMS_AUTO_ENCRYPT_XFORM=True, KMS_OVERRIDE_CUSTOM_ENCRYPTION=False
        ):
            custom_md = """
            | survey  |
            |         | type        | name           | label      |
            |         | text        | name           | First Name |
            |         | text        | age            | Age        |
            | settings|             |                |            |
            |         | form_title  | form_id        | public_key |
            |         | Students    | students       | fake-pub   |
            """
            xform = self._publish_markdown(custom_md, org.user, id_string="e")
            xform.refresh_from_db()

            self.assertTrue(xform.encrypted)
            self.assertFalse(xform.is_managed)

        # XForm is encrypted if already encrypted and
        # KMS_OVERRIDE_CUSTOM_ENCRYPTION is True
        with override_settings(
            KMS_AUTO_ENCRYPT_XFORM=True, KMS_OVERRIDE_CUSTOM_ENCRYPTION=True
        ):
            xform = self._publish_markdown(custom_md, org.user, id_string="f")
            xform.refresh_from_db()

            self.assertTrue(xform.encrypted)
            self.assertTrue(xform.is_managed)

        # Initial XForm version is updated when XForm is encrypted
        md = """
        | survey  |
        |         | type        | name           | label      |
        |         | text        | name           | First Name |
        |         | text        | age            | Age        |
        | settings|             |                |            |
        |         | form_title  | form_id        | version    |
        |         | Students    | students       | 202504221539|
        """
        with override_settings(KMS_AUTO_ENCRYPT_XFORM=True):
            xform = self._publish_markdown(md, org.user, id_string="g")
            xform.refresh_from_db()

            self.assertTrue(xform.encrypted)
            self.assertTrue(xform.is_managed)
            self.assertNotEqual(xform.version, "202504221539")

        # XForm is not encrypted if KMSKey missing
        kms_key.delete()

        with override_settings(KMS_AUTO_ENCRYPT_XFORM=True):
            xform = self._publish_markdown(md, org.user, id_string="h")
            xform.refresh_from_db()

            self.assertFalse(xform.encrypted)
