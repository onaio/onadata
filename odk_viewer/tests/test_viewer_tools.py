import os
from main.tests.test_base import MainTestCase
from utils.viewer_tools import XFormParser

class TestViewerTools(MainTestCase):
    def test_xform_parser_get_control_dict(self):
        xform_path = os.path.join(os.path.dirname(__file__),
            "fixtures", "household_survey_xform.xml")
        with open(xform_path, "r") as f:
            xml = f.read()
        parser = XFormParser(xml=xml)
        control_dict = parser.get_control_dict()
        expected_control_dict = {
            u'/survey_broken_csv_export/Date': u'DATE',
            u'/survey_broken_csv_export/member/name': u'NAME',
            u'/survey_broken_csv_export/member/image': u'Photo',
            u'/survey_broken_csv_export/address': u'ADDRESS',
            u'/survey_broken_csv_export/no_of_family_member': u'Number of Family Member',
            u'/survey_broken_csv_export/electricity': u'Do you have elecricity meter in your house ?',
            u'/survey_broken_csv_export/source': u'from where you get electricity ?',
            u'/survey_broken_csv_export/photo': u'take picture of the power sourse',
            u'/survey_broken_csv_export/gps': u'GPS'
        }
        self.maxDiff = None
        self.assertEqual(control_dict, expected_control_dict)