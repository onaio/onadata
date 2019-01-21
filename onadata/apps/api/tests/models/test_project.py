import os

from onadata.apps.api import tools
from onadata.apps.api.tests.models.test_abstract_models import\
    TestAbstractModels

from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.project import Project
from onadata.apps.logger.xform_instance_parser import XLSFormError

from onadata.apps.main.tests.test_base import TestBase


class TestProject(TestAbstractModels, TestBase):

    def test_create_organization_project(self):
        organization = self._create_organization("modilabs", self.user)
        project_name = "demo"
        project = self._create_project(organization, project_name, self.user)
        self.assertIsInstance(project, Project)
        self.assertEqual(project.name, project_name)

        user_deno = self._create_user('deno', 'deno')
        project = tools.create_organization_project(
            organization, project_name, user_deno)
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
        sample_xml = """<?xml version="1.0" ?><h:html xmlns="http://www.w3.org/2002/xforms" xmlns:ev="http://www.w3.org/2001/xml-events" xmlns:h="http://www.w3.org/1999/xhtml" xmlns:jr="http://openrosa.org/javarosa" xmlns:xsd="http://www.w3.org/2001/XMLSchema"><h:head><h:title>Phone</h:title><model><instance><phone id="Phone_2011-02-04_00-09-18"><device_id/><start/><end/><visible_id/><phone_number/><status/><note/></phone></instance><bind jr:preload="property" jr:preloadParams="deviceid" nodeset="/phone/device_id" required="true()" type="string"/><bind jr:preload="timestamp" jr:preloadParams="start" nodeset="/phone/start" required="true()" type="dateTime"/><bind jr:preload="timestamp" jr:preloadParams="end" nodeset="/phone/end" required="true()" type="dateTime"/><bind constraint="regex(., '^\d{3}$')" jr:constraintMsg="Please enter the three digit string from the back of the phone." nodeset="/phone/visible_id" required="true()" type="string"/><bind nodeset="/phone/phone_number" required="true()" type="string"/><bind nodeset="/phone/status" required="true()" type="select1"/><bind nodeset="/phone/note" required="true()" type="string"/></model></h:head><h:body><input ref="/phone/visible_id"><label>What is the three digit label on the back of this phone?</label></input><input ref="/phone/phone_number"><label>What is the current phone number to call this phone?</label></input><select1 ref="/phone/status"><label>What is the status of this phone?</label><item><label>Functional</label><value>fuctional</value></item><item><label>Broken</label><value>broken</value></item></select1><input ref="/phone/note"><label>Please enter any comments about this phone.</label></input></h:body></h:html>""" # noqa
        XForm.objects.create(
            user=self.user,
            xml=sample_xml,
            id_string='domestic_animals',
            title='domestic_animals_in_kenyan_homes',
            project=project
        )
        project.soft_delete()
        self.assertEquals(
            1, Project.objects.filter(deleted_at__isnull=False).count())
        self.assertEquals(
            1, XForm.objects.filter(deleted_at__isnull=False).count())

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
        sample_json = '{"default_language": "default", ' \
                      '"id_string": "Water_2011_03_17", "children": [], ' \
                      '"name": "Water_2011_03_17", ' \
                      '"title": "Water_2011_03_17", "type": "survey"}'
        f = open(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '../../../',
            'logger/tests/',
            "Water_Translated_2011_03_10.xml"
        ))
        xml = f.read()
        f.close()
        xform = XForm.objects.create(
            xml=xml, user=self.user, json=sample_json, project=project)

        f = open(os.path.join(os.path.dirname(
            os.path.abspath(__file__)),
            '../../../',
            'logger/tests/',
            'Water_Translated_2011_03_10_2011-03-10_14-38-28.xml')
        )
        xml = f.read()
        f.close()
        Instance.objects.create(xml=xml, user=self.user, xform=xform)

        # try and slice the RawQueryset in order to have it evaluated
        try:
            XForm.objects.raw(
                "UPDATE logger_xform SET id_string='a New ID String' \
                WHERE id={};".format(xform.id))[0]
        except TypeError:
            pass
        xform_refetch = XForm.objects.all()[0]
        self.assertEqual('a New ID String', xform_refetch.id_string)

        with self.assertRaises(XLSFormError):
            project.soft_delete()
            self.assertEquals(1, Project.objects.filter(
                deleted_at__isnull=True).count())
            self.assertIsNone(project.deleted_at)

            self.assertEquals(1, XForm.objects.filter(
                project=project, deleted_at__isnull=True).count())

        # Try deleting the Xform; it should also roll back due to the exception
        with self.assertRaises(XLSFormError):
            XForm.objects.all()[0].soft_delete()
            self.assertEquals(1, XForm.objects.filter(
                deleted_at__isnull=True).count())
            self.assertIsNone(XForm.objects.all()[0].deleted_at)
