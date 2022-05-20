# -*- coding: utf-8 -*-
"""
TestBaseSMS - base class for sms_support test cases.
"""
import os
import string
import random

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.logger.models import XForm
from onadata.apps.sms_support.parser import process_incoming_smses


def random_identity():
    """Returns some random digits and ascii_letters as string of length 8 used as an
    identity."""
    return "".join(
        [random.choice(string.digits + string.ascii_letters) for x in range(8)]  # nosec
    )


def response_for_text(username, text, id_string=None, identity=None):
    """Processes an SMS ``text`` and returns the results."""
    if identity is None:
        identity = random_identity()

    return process_incoming_smses(
        username=username, id_string=id_string, incomings=[(identity, text)]
    )[0]


class TestBaseSMS(TestBase):
    """
    TestBaseSMS - base class for sms_support test cases.
    """

    def setUp(self):
        TestBase.setUp(self)

    def setup_form(self, allow_sms=True):
        """Helper method to setup an SMS form."""
        # pylint: disable=attribute-defined-outside-init
        self.id_string = "sms_test_form"
        self.sms_keyword = "test"
        self.username = "auser"
        self.password = "auser"
        self.this_directory = os.path.dirname(__file__)

        # init FH
        self._create_user_and_login(username=self.username, password=self.password)

        # create a test form and activate SMS Support.
        self._publish_xls_file_and_set_xform(
            os.path.join(self.this_directory, "fixtures", "sms_tutorial.xlsx")
        )

        if allow_sms:
            xform = XForm.objects.get(id_string=self.id_string)
            xform.allows_sms = True
            xform.save()
            self.xform = xform
