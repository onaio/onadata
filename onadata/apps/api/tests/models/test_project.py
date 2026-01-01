import os

from onadata.apps.api import tools
from onadata.apps.api.tests.models.test_abstract_models import TestAbstractModels
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.xform_instance_parser import XLSFormError
from onadata.apps.main.tests.test_base import TestBase


class TestProject(TestAbstractModels, TestBase):
    def test_create_organization_project(self):
        organization = self._create_organization("modilabs", self.user)
        project_name = "demo"
        project = self._create_project(organization, project_name, self.user)
        self.assertIsInstance(project, Project)
        self.assertEqual(project.name, project_name)

        user_deno = self._create_user("deno", "deno")
        project = tools.create_organization_project(
            organization, project_name, user_deno
        )
        self.assertIsNone(project)

    def test_project_soft_delete_works_when_no_exception_is_raised(self):
        """
        Testing transaction.atomic on Project.soft_delete.

        One should be able to soft_delete a project when no exceptions are
        raised during the soft_deletion.
        """
        organization = self._create_organization("modilabs", self.user)
        project_name = "demo"
        project = self._create_project(organization, project_name, self.user)
        md = """
        | survey  |
        |         | type              | name  | label   |
        |         | select one fruits | fruit | Fruit   |
        | choices |
        |         | list name         | name   | label  |
        |         | fruits            | orange | Orange |
        |         | fruits            | mango  | Mango  |
        """
        self._publish_markdown(md, self.user, id_string="a", project=project)
        project.soft_delete()
        self.assertEqual(
            1, Project.objects.filter(pk=project.pk, deleted_at__isnull=False).count()
        )
        self.assertEqual(
            1, XForm.objects.filter(project=project, deleted_at__isnull=False).count()
        )

    def test_project_detetion_reverts_when_an_exception_raised(self):
        """
        Testing transaction.atomic on Project.soft_delete.

        The database should roll back changes made during the soft_delete
        of a project if deleting its linked XForms fail.

        This works on the premise that in STRICT mode XForm id_strings
        should not have spaces in them.
        """
        organization = self._create_organization("modilabs", self.user)
        project_name = "demo"
        project = self._create_project(organization, project_name, self.user)
        sample_json = (
            '{"default_language": "default", '
            '"id_string": "Water_2011_03_17", "children": '
            '[{"type": "text", "name": "location", "label": "Location"}], '
            '"name": "Water_2011_03_17", '
            '"title": "Water_2011_03_17", "type": "survey"}'
        )
        with open(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "../../../",
                "logger/tests/",
                "Water_Translated_2011_03_10.xml",
            )
        ) as f:
            xml = f.read()
        xform = XForm.objects.create(
            xml=xml, user=self.user, json=sample_json, project=project
        )

        with open(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "../../../",
                "logger/tests/",
                "Water_Translated_2011_03_10_2011-03-10_14-38-28.xml",
            )
        ) as f:
            xml = f.read()
        Instance.objects.create(xml=xml, user=self.user, xform=xform)

        # try and slice the RawQueryset in order to have it evaluated
        try:
            XForm.objects.raw(
                "UPDATE logger_xform SET id_string='a New ID String' \
                WHERE id={};".format(
                    xform.id
                )
            )[0]
        except TypeError:
            pass
        xform_refetch = XForm.objects.all()[0]
        self.assertEqual("a New ID String", xform_refetch.id_string)

        with self.assertRaises(XLSFormError):
            project.soft_delete()
            self.assertEqual(1, Project.objects.filter(deleted_at__isnull=True).count())
            self.assertIsNone(project.deleted_at)

            self.assertEqual(
                1,
                XForm.objects.filter(project=project, deleted_at__isnull=True).count(),
            )

        # Try deleting the Xform; it should also roll back due to the exception
        with self.assertRaises(XLSFormError):
            XForm.objects.all()[0].soft_delete()
            self.assertEqual(1, XForm.objects.filter(deleted_at__isnull=True).count())
            self.assertIsNone(XForm.objects.all()[0].deleted_at)
