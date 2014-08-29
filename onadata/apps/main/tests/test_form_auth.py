from django.core.urlresolvers import reverse

from onadata.apps.main.views import login_redirect
from test_base import TestBase


class TestFormAuth(TestBase):

    def setUp(self):
        TestBase.setUp(self)

    def test_login_redirect_redirects(self):
        response = self.client.get(reverse(login_redirect))
        self.assertEquals(response.status_code, 302)
