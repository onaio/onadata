# -*- coding: utf-8 -*-
"""
Test onadata.libs.serializers.project_serializer
"""

from unittest.mock import MagicMock

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache

from rest_framework import serializers
from rest_framework.test import APIRequestFactory

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.logger.models import Project
from onadata.libs.serializers.project_serializer import (
    BaseProjectSerializer,
    ProjectSerializer,
)
from onadata.libs.utils.cache_tools import PROJ_OWNER_CACHE, safe_key


class TestBaseProjectSerializer(TestAbstractViewSet):
    """
    Test onadata.libs.serializers.project_serializer
    """

    def setUp(self):
        self.factory = APIRequestFactory()
        self._login_user_and_profile()
        self.serializer = BaseProjectSerializer()

        self._org_create()
        data = {
            "name": "demo",
            "owner": "http://testserver/api/v1/users/%s"
            % self.organization.user.username,
            "metadata": {
                "description": "Some description",
                "location": "Naivasha, Kenya",
                "category": "governance",
            },
            "public": False,
        }
        # Create the project
        self._project_create(data)

    def test_get_current_user_role(self):
        request = self.factory.get("/", **self.extra)
        request.user = self.user
        serializer = BaseProjectSerializer(self.project, context={"request": request})
        self.assertEqual(serializer.data["current_user_role"], "owner")

        # Is none if user is anonymous
        request.user = AnonymousUser()
        serializer = BaseProjectSerializer(self.project, context={"request": request})
        self.assertIsNone(serializer.data["current_user_role"])


class TestProjectSerializer(TestAbstractViewSet):
    def setUp(self):
        self.serializer = ProjectSerializer()
        self.factory = APIRequestFactory()
        self._login_user_and_profile()

    def test_get_users_none(self):
        perms = self.serializer.get_users(None)
        self.assertEqual(perms, None)

    def test_get_project_forms(self):
        # create a project with a form
        self._publish_xls_form_to_project()

        project = Project.objects.last()
        form = project.xform_set.last()

        request = self.factory.get("/", **self.extra)
        request.user = self.user

        serializer = ProjectSerializer(project)
        serializer.context["request"] = request

        self.assertEqual(len(serializer.data["forms"]), 1)
        self.assertEqual(serializer.data["forms"][0]["encrypted"], False)
        self.assertEqual(serializer.data["num_datasets"], 1)

        # delete form in project
        form.delete()

        # Check that project has no forms
        self.assertIsNone(project.xform_set.last())
        serializer = ProjectSerializer(project, context={"request": request})
        self.assertEqual(len(serializer.data["forms"]), 0)
        self.assertEqual(serializer.data["num_datasets"], 0)

    def test_create_duplicate_projects(self):
        validated_data = {
            "name": "demo",
            "organization": self.user,
            "metadata": {
                "description": "Some description",
                "location": "Naivasha, Kenya",
                "category": "governance",
            },
            "public": False,
        }

        # create first project
        request = MagicMock(user=self.user)
        serializer = ProjectSerializer(context={"request": request})
        project = serializer.create(validated_data)
        self.assertEqual(project.name, "demo")
        self.assertEqual(project.organization, self.user)

        # create another project with same data
        with self.assertRaises(serializers.ValidationError) as e:
            serializer.create(validated_data)
        self.assertEqual(
            e.exception.detail,
            ["The fields name, organization must make a unique set."],
        )

    def test_new_project_set_to_cache(self):
        """
        Test that newly created project is set to cache
        """
        data = {
            "name": "demo",
            "owner": "http://testserver/api/v1/users/%s" % self.user,
            "metadata": {
                "description": "Some description",
                "location": "Naivasha, Kenya",
                "category": "governance",
            },
            "public": False,
        }
        # clear cache
        cache.delete(safe_key(f"{PROJ_OWNER_CACHE}1"))
        self.assertIsNone(cache.get(safe_key(f"{PROJ_OWNER_CACHE}1")))

        # Create the project
        self._project_create(data)
        self.assertIsNotNone(self.project_data)

        request = self.factory.get("/", **self.extra)
        request.user = self.user

        serializer = ProjectSerializer(self.project, context={"request": request}).data
        self.assertEqual(cache.get(f"{PROJ_OWNER_CACHE}{self.project.pk}"), serializer)

        # clear cache
        cache.delete(safe_key(f"{PROJ_OWNER_CACHE}{self.project.pk}"))

    def test_get_current_user_role(self):
        self._publish_xls_form_to_project()

        request = self.factory.get("/", **self.extra)
        request.user = self.user
        serializer = ProjectSerializer(self.project, context={"request": request})
        self.assertEqual(serializer.data["current_user_role"], "owner")

        # Is none if user is anonymous
        request.user = AnonymousUser()
        serializer = ProjectSerializer(self.project, context={"request": request})
        self.assertIsNone(serializer.data["current_user_role"])
