# -*- coding: utf-8 -*-
"""
Test onadata.libs.utils.cache_tools module.
"""
from django.core.cache import cache
from django.contrib.auth.models import User
from django.http.request import HttpRequest
from unittest import TestCase

from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.logger.models.project import Project
from onadata.libs.utils.cache_tools import (
    PROJ_PERM_CACHE, PROJ_NUM_DATASET_CACHE, PROJ_SUB_DATE_CACHE,
    PROJ_FORMS_CACHE, PROJ_BASE_FORMS_CACHE, PROJ_OWNER_CACHE,
    safe_key, reset_project_cache, project_cache_prefixes)


class TestCacheTools(TestCase):
    """Test onadata.libs.utils.cache_tools module class"""

    def test_safe_key(self):
        """Test safe_key() function returns a hashed key"""
        self.assertEqual(
            safe_key("hello world"),
            "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9")

    def test_reset_project_cache(self):
        """
        Test reset_project_cache() function actually resets all project cache
        entries
        """
        bob = User.objects.create(username='bob', first_name='bob')
        UserProfile.objects.create(user=bob)
        project = Project.objects.create(
            name='Some Project', created_by=bob, organization=bob)

        # Set dummy values in cache
        for prefix in project_cache_prefixes:
            cache.set(f'{prefix}{project.pk}', 'stale')

        request = HttpRequest()
        request.user = bob
        request.META = {
            'SERVER_NAME': 'testserver',
            'SERVER_PORT': '80'
        }
        reset_project_cache(project, request)

        expected_project_cache = {
            'url': f'http://testserver/api/v1/projects/{project.pk}',
            'projectid': project.pk,
            'owner': 'http://testserver/api/v1/users/bob',
            'created_by': 'http://testserver/api/v1/users/bob',
            'metadata': {},
            'starred': False,
            'users': [{
                'is_org': False,
                'metadata': {},
                'first_name': 'bob',
                'last_name': '',
                'user': 'bob',
                'role': 'owner'
            }],
            'forms': [],
            'public': False,
            'tags': [],
            'num_datasets': 0,
            'last_submission_date': None,
            'teams': [],
            'data_views': [],
            'name': 'Some Project',
            'deleted_at': None
        }

        self.assertEqual(
            cache.get(f'{PROJ_PERM_CACHE}{project.pk}'),
            expected_project_cache['users'])
        self.assertEqual(
            cache.get(f'{PROJ_NUM_DATASET_CACHE}{project.pk}'),
            expected_project_cache['num_datasets'])
        self.assertEqual(
            cache.get(f'{PROJ_SUB_DATE_CACHE}{project.pk}'),
            expected_project_cache['last_submission_date'])
        self.assertEqual(
            cache.get(f'{PROJ_FORMS_CACHE}{project.pk}'),
            expected_project_cache['forms'])
        self.assertEqual(
            cache.get(f'{PROJ_BASE_FORMS_CACHE}{project.pk}'),
            None)

        project_cache = cache.get(f'{PROJ_OWNER_CACHE}{project.pk}')
        project_cache.pop('date_created')
        project_cache.pop('date_modified')
        project_cache.pop('project_qrcode')
        self.assertEqual(
            project_cache,
            expected_project_cache)
