from onadata.apps.main.tests.test_base import TestBase


class TestUserLogin(TestBase):
    def test_any_case_login_ok(self):
        username = 'bob'
        password = 'bobbob'
        self._create_user(username, password)
        self._login('BOB', password)

    def test_username_is_made_lower_case(self):
        username = 'ROBERT'
        password = 'bobbob'
        self._create_user(username, password)
        self._login('robert', password)

    def test_redirect_if_logged_in(self):
        self._create_user_and_login()
        response = self.client.get('')
        self.assertEqual(response.status_code, 302)
