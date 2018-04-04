import os
import string
import random
from builtins import range

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import XForm
from onadata.apps.sms_support.parser import process_incoming_smses


class TestBaseSMS(TestBase):

    def setUp(self):
        TestBase.setUp(self)

    def setup_form(self, allow_sms=True):
        self.id_string = 'sms_test_form'
        self.sms_keyword = 'test'
        self.username = 'auser'
        self.password = 'auser'
        self.this_directory = os.path.dirname(__file__)

        # init FH
        self._create_user_and_login(username=self.username,
                                    password=self.password)

        # create a test form and activate SMS Support.
        self._publish_xls_file_and_set_xform(os.path.join(self.this_directory,
                                                          'fixtures',
                                                          'sms_tutorial.xls'))

        if allow_sms:
            xform = XForm.objects.get(id_string=self.id_string)
            xform.allows_sms = True
            xform.save()
            self.xform = xform

    def random_identity(self):
        return ''.join([random.choice(string.digits + string.ascii_letters)
                        for x in range(8)])

    def response_for_text(self, username, text,
                          id_string=None, identity=None):
        if identity is None:
            identity = self.random_identity()

        return process_incoming_smses(username=username,
                                      id_string=None,
                                      incomings=[(identity, text)])[0]
