"""Tests for view add_submission_with"""

from unittest.mock import Mock, patch

from django.urls import reverse

from onadata.apps.logger.models.xform import XForm
from onadata.apps.main.tests.test_base import TestBase


class AddSubmissionWithTestCase(TestBase):
    """Tests for view add_submission_with"""

    @patch("onadata.apps.viewer.views.requests.post")
    def test_deleted_twin_ignored(self, mock_post):
        """A soft-deleted form whose id_string matches is ignored"""
        mock_post.return_value = Mock(
            text='{"url": "https://enketo.example.com/instance"}'
        )
        id_string = "x" * 95
        md = """
        | survey |
        |        | type     | name     | label    |
        |        | geopoint | location | Location |
        """
        dd = self._publish_markdown(md, self.user, id_string=id_string)
        xform = XForm.objects.get(pk=dd.pk)
        xform.soft_delete(self.user)
        self._publish_markdown(md, self.user, id_string=id_string)

        url = reverse(
            "add_submission_with",
            kwargs={"username": self.user.username, "id_string": id_string},
        )
        response = self.client.get(url, {"coordinates": "-1.28 36.82"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"url": "https://enketo.example.com/instance"}
        )
