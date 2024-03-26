# import re
# from django.test import RequestFactory, TestCase
# from django.urls import resolve, reverse

# from django_digest.test import Client as DigestClient
# from django_digest.test import DigestAuth

# from onadata.apps.main.tests.test_base import TestBase
# from onadata.libs.permissions import DataEntryRole

# class TestUsernamePatterns(TestBase):
#     def setUp(self):
#         super().setUp()

#     def test_submission_list_view(self):
#         # Define test data
#         usernames = ["test_user", "user-with-hyphen", "user.with.dot"]
#         id_string = "sample_id_string"
        
#         # Define the URL pattern name
#         url_name = "form-list-username"
        
#         # Iterate over usernames
#         for username in usernames:
#             # Generate the URL with parameters
#             url = reverse(url_name, kwargs={'username': username})

#             # Check if the URL matches the expected pattern and resolves to the correct view
#             resolved = resolve(url)
#             import ipdb; ipdb.set_trace()

#             # Check if the resolved view has the correct resolver_match attribute
#             self.assertEqual(resolved.url_name, "form-list-username")
#             self.assertEqual(resolved.kwargs, {'username': username})


import re
from django.test import SimpleTestCase
from django.urls import resolve

class TestRoutePatternMatching(SimpleTestCase):
    def test_route_pattern_matching(self):
        # Define test data
        urls = [
            "/test_user/view/submissionList",
            "/forms/example_xform_pk/view/submissionList",
            "/projects/123/view/submissionList"
        ]

        # Define the expected regular expressions for route patterns
        patterns = [
            r"^(?P<username>[\w.@-]+)/view/submissionList$",
            r"^forms/(?P<xform_pk>\w+)/view/submissionList$",
            r"^projects/(?P<project_pk>\d+)/view/submissionList$"
        ]

        # Loop through each URL and corresponding pattern
        for url, pattern in zip(urls, patterns):
            # Resolve the URL and get the route pattern
            resolved = resolve(url)
            route_pattern = resolved.route
            import ipdb; ipdb.set_trace()

            # Test if the route pattern matches the expected regular expression
            with self.subTest(url=url, pattern=pattern):
                self.assertIsNotNone(re.match(pattern, url), f"The route pattern '{route_pattern}' does not match the expected regular expression '{pattern}'")


