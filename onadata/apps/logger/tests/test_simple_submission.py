from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory
from pyxform import SurveyElementBuilder

from onadata.apps.logger.xform_instance_parser import DuplicateInstance
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.libs.utils.logger_tools import (
    create_instance, safe_create_instance
)


class TempFileProxy(object):
    """
    create_instance will be looking for a file object,
    with "read" and "close" methods.
    """
    def __init__(self, content):
        self.content = content

    def read(self):
        return self.content

    def close(self):
        pass


class TestSimpleSubmission(TestCase):
    def _get_xml_for_form(self, xform):
        builder = SurveyElementBuilder()
        sss = builder.create_survey_element_from_json(xform.json)
        xform.xml = sss.to_xml()
        xform._mark_start_time_boolean()
        xform.save()

    def _submit_at_hour(self, hour):
        st_xml = '<?xml version=\'1.0\' ?><start_time id="start_time"><st'\
                 'art_time>2012-01-11T%d:00:00.000+00</start_time></start'\
                 '_time>' % hour
        try:
            create_instance(self.user.username, TempFileProxy(st_xml), [])
        except DuplicateInstance:
            pass

    def _submit_simple_yes(self):
        create_instance(self.user.username, TempFileProxy(
            '<?xml version=\'1.0\' ?><yes_or_no id="yes_or_no"><yesno>Yes<'
            '/yesno></yes_or_no>'), [])

    def setUp(self):
        self.user = User.objects.create(
            username="admin", email="sample@example.com")
        self.user.set_password("pass")
        self.xform1 = DataDictionary()
        self.xform1.user = self.user
        self.xform1.json = '{"id_string": "yes_or_no", "children": [{"name": '\
                           '"yesno", "label": "Yes or no?", "type": "text"}],'\
                           ' "name": "yes_or_no", "title": "yes_or_no", "type'\
                           '": "survey"}'.strip()
        self.xform2 = DataDictionary()
        self.xform2.user = self.user
        self.xform2.json = '{"id_string": "start_time", "children": [{"name":'\
                           '"start_time", "type": "start"}], "name": "start_t'\
                           'ime", "title": "start_time", "type": "survey"}'\
                           .strip()

        self._get_xml_for_form(self.xform1)
        self._get_xml_for_form(self.xform2)

    def test_start_time_boolean_properly_set(self):
        self.assertFalse(self.xform1.has_start_time)
        self.assertTrue(self.xform2.has_start_time)

    def test_simple_yes_submission(self):
        self.assertEquals(0, self.xform1.instances.count())

        self._submit_simple_yes()

        self.assertEquals(1, self.xform1.instances.count())

        self._submit_simple_yes()

        # a simple "yes" submission *SHOULD* increment the survey count
        self.assertEquals(2, self.xform1.instances.count())

    def test_start_time_submissions(self):
        """This test checks to make sure that instances
        *with start_time available* are marked as duplicates when the XML is a
        direct match.
        """
        self.assertEquals(0, self.xform2.instances.count())
        self._submit_at_hour(11)
        self.assertEquals(1, self.xform2.instances.count())
        self._submit_at_hour(12)
        self.assertEquals(2, self.xform2.instances.count())
        # an instance from 11 AM already exists in the database, so it
        # *SHOULD NOT* increment the survey count.
        self._submit_at_hour(11)
        self.assertEquals(2, self.xform2.instances.count())

    def test_corrupted_submission(self):
        """Test xml submissions that contain unicode characters.
        """
        xml = 'v\xee\xf3\xc0k\x91\x91\xae\xff\xff\xff\xff\xcf[$b\xd0\xc9\'uW\x80RP\xff\xff\xff\xff7\xd0\x03%F\xa7p\xa2\x87\xb6f\xb1\xff\xff\xff\xffg~\xf3O\xf3\x9b\xbc\xf6ej_$\xff\xff\xff\xff\x13\xe8\xa9D\xed\xfb\xe7\xa4d\x96>\xfa\xff\xff\xff\xff\xc7h"\x86\x14\\.\xdb\x8aoF\xa4\xff\xff\xff\xff\xcez\xff\x01\x0c\x9a\x94\x18\xe1\x03\x8e\xfa\xff\xff\xff\xff39P|\xf9n\x18F\xb1\xcb\xacd\xff\xff\xff\xff\xce>\x97i;1u\xcfI*\xf2\x8e\xff\xff\xff\xffFg\x9d\x0fR:\xcd*\x14\x85\xf0e\xff\xff\xff\xff\xd6\xdc\xda\x8eM\x06\xf1\xfc\xc1\xe8\xd6\xe0\xff\xff\xff\xff\xe7G\xe1\xa1l\x02T\n\xde\x1boJ\xff\xff\xff\xffz \x92\xbc\tR{#\xbb\x9f\xa6s\xff\xff\xff\xff\xa2\x8f(\xb6=\xe11\xfcV\xcf\xef\x0b\xff\xff\xff\xff\xa3\x83\x7ft\xd7\x05+)\xeb9\\*\xff\xff\xff\xff\xfe\x93\xb2\xa2\x06n;\x1b4\xaf\xa6\x93\xff\xff\xff\xff\xe7\xf7\x12Q\x83\xbb\x9a\xc8\xc8q34\xff\xff\xff\xffT2\xa5\x07\x9a\xc9\x89\xf8\x14Y\xab\x19\xff\xff\xff\xff\x16\xd0R\x1d\x06B\x95\xea\\\x1ftP\xff\xff\xff\xff\x94^\'\x01#oYV\xc5\\\xb7@\xff\xff\xff\xff !\x11\x00\x8b\xf3[\xde\xa2\x01\x9dl\xff\xff\xff\xff\xe7z\x92\xc3\x03\xd3\xb5B5 \xaa7\xff\xff\xff\xff\xff\xc3Q:\xa6\xb3\xa3\x1e\x90 \xa0\\\xff\xff\xff\xff\xff\x14<\x03Vr\xe8Z.Ql\xf5\xff\xff\xff\xffEx\xf7\x0b_\xa1\x7f\xfcG\xa4\x18\xcd\xff\xff\xff\xff1|~i\x00\xb3. ,1Q\x0e\xff\xff\xff\xff\x87a\x933Y\xd7\xe1B#\xa7a\xee\xff\xff\xff\xff\r\tJ\x18\xd0\xdb\x0b\xbe\x00\x91\x95\x9e\xff\xff\xff\xffHfW\xcd\x8f\xa9z6|\xc5\x171\xff\xff\xff\xff\xf5tP7\x93\x02Q|x\x17\xb1\xcb\xff\xff\xff\xffVb\x11\xa0*\xd9;\x0b\xf8\x1c\xd3c\xff\xff\xff\xff\x84\x82\xcer\x15\x99`5LmA\xd5\xff\xff\xff\xfft\xce\x8e\xcbw\xee\xf3\xc0w\xca\xb3\xfd\xff\xff\xff\xff\xb0\xaab\x92\xd4\x02\x84H3\x94\xa9~\xff\xff\xff\xff\xfe7\x18\xcaW=\x94\xbc|\x0f{\x84\xff\xff\xff\xff\xe8\xdf\xde?\x8b\xb7\x9dH3\xc1\xf2\xaa\xff\xff\xff\xff\xbe\x00\xba\xd7\xba6!\x95g\xb01\xf9\xff\xff\xff\xff\x93\xe3\x90YH9g\xf7\x97nhv\xff\xff\xff\xff\x82\xc7`\xaebn\x9d\x1e}\xba\x1e/\xff\xff\xff\xff\xbd\xe5\xa1\x05\x03\xf26\xa0\xe2\xc1*\x07\xff\xff\xff\xffny\x88\x9f\x19\xd2\xd0\xf7\x1de\xa7\xe0\xff\xff\xff\xff\xc4O&\x14\x8dVH\x90\x8b+\x03\xf9\xff\xff\xff\xff\xf69\xc2\xabo%\xcc/\xc9\xe4dP\xff\xff\xff\xff (\x08G\xebM\x03\x99Y\xb4\xb3\x1f\xff\xff\xff\xffzH\xd2\x19p#\xc5\xa4)\xfd\x05\x9a\xff\xff\xff\xffd\x86\xb2F\x15\x0f\xf4.\xfd\\\xd4#\xff\xff\xff\xff\xaf\xbe\xc6\x9di\xa0\xbc\xd5>cp\xe2\xff\xff\xff\xff&h\x91\xe9\xa0H\xdd\xaer\x87\x18E\xff\xff\xff\xffjg\x08E\x8f\xa4&\xab\xff\x98\x0ei\xff\xff\xff\xff\x01\xfd{"\xed\\\xa3M\x9e\xc3\xf8K\xff\xff\xff\xff\x87Y\x98T\xf0\xa6\xec\x98\xb3\xef\xa7\xaa\xff\xff\xff\xffA\xced\xfal\xd3\xd9\x06\xc6~\xee}\xff\xff\xff\xff:\x7f\xa2\x10\xc7\xadB,}PF%\xff\xff\xff\xff\xb2\xbc\n\x17%\x98\x904\x89\tF\x1f\xff\xff\xff\xff\xdc\xd8\xc6@#M\x87uf\x02\xc6g\xff\xff\xff\xffK\xaf\xb0-=l\x07\xe1Nv\xe4\xf4\xff\xff\xff\xff\xdb\x13\'Ne\xb2UT\x9a#\xb1^\xff\xff\xff\xff\xb2\rne\xd1\x9d\x88\xda\xbb!\xfa@\xff\xff\xff\xffflq\x0f\x01z]uh\'|?\xff\xff\xff\xff\xd5\'\x19\x865\xba\xf2\xe7\x8fR-\xcc\xff\xff\xff\xff\xce\xd6\xfdi\x04\x9b\xa7\tu\x05\xb7\xc8\xff\xff\xff\xff\xc3\xd0)\x11\xdd\xb1\xa5kp\xc9\xd5\xf7\xff\xff\xff\xff\xffU\x9f \xb7\xa1#3rup[\xff\xff\xff\xff\xfc='  # noqa

        request = RequestFactory().post('/')
        request.user = self.user
        error, instance = safe_create_instance(
            self.user.username, TempFileProxy(xml), None, None, request)
        text = 'File likely corrupted during transmission'
        self.assertContains(error, text, status_code=400)
