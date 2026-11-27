# -*- coding: utf-8 -*-
"""
Tests that each gate passes the accounts owning what it touches, so an
organisation requiring two-factor for an action refuses a user with no factor
there.

Every refusal runs under ``skip_gate``, so the organisation's requirement is
the only reason for it. Each refusal has a matching test in which the same
request goes through because the organisation does not require the action.
"""

import json
import os

from django.conf import settings
from django.urls import reverse

from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.tests.viewsets.test_merged_xform_viewset import MD
from onadata.apps.api.tests.viewsets.test_stepup_org_two_factor import (
    OrgTwoFactorTestCase,
)
from onadata.apps.api.tests.viewsets.test_stepup_sharing_gates import (
    gating,
)
from onadata.apps.api.viewsets.dataview_viewset import DataViewViewSet
from onadata.apps.api.viewsets.merged_xform_viewset import MergedXFormViewSet
from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet
from onadata.apps.api.viewsets.open_data_viewset import OpenDataViewSet
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import (
    DataView,
    Instance,
    MergedXForm,
    OpenData,
    Project,
    XForm,
)
from onadata.apps.logger.models.open_data import get_or_create_opendata
from onadata.apps.main.models import MetaData, UserProfile
from onadata.apps.restservice.models import RestService
from onadata.apps.restservice.views import add_service
from onadata.apps.restservice.viewsets.restservices_viewset import RestServicesViewSet
from onadata.libs.permissions import ManagerRole, OwnerRole
from onadata.libs.stepup.gate import has_second_factor
from onadata.libs.stepup.policy import (
    GATE_CHANGE_WEBHOOK,
    GATE_PUBLISH_DATA,
    GATE_REQUIRE_AUTH,
    GATE_SHARE_FORM_ADMIN,
    GATE_TRANSFER_PROJECT,
)
from onadata.libs.utils.user_auth import get_user_default_project

ENROL_REQUIRED_PAGE = "Set up two-factor authentication before making this change."
TUTORIAL = os.path.join(
    settings.PROJECT_ROOT, "libs", "tests", "utils", "fixtures", "tutorial.xlsx"
)
SERVICE_URL = "https://example.com/hook"
OTHER_URL = "https://elsewhere.example.org/hook"


def _url(kind, pk):
    return f"http://testserver/api/v1/{kind}/{pk}"


class OrgWiringTestCase(OrgTwoFactorTestCase):
    """``self.user`` owns ``denoinc`` and has no second factor. ``denoinc``
    owns ``self.org_project``."""

    def setUp(self):
        super().setUp()
        self.assertFalse(has_second_factor(self.user))
        self._project_create({"name": "org project", "owner": self.org_url})
        self.org_project = self.project
        self.assert_org_owns(self.org_project.organization)

    def assert_org_owns(self, account, organization=None):
        self.assertEqual(account, (organization or self.organization).user)

    def assert_page_enrol_required(self, response):
        self.assertContains(response, ENROL_REQUIRED_PAGE, status_code=403)

    def _require_of(self, organization, actions):
        OrganizationProfile.objects.filter(pk=organization.pk).update(
            two_factor_required_actions=actions
        )
        organization.refresh_from_db()
        self.assertEqual(organization.two_factor_required_actions, actions)

    def _other_org(self):
        """A second organisation ``self.user`` owns. ``self.organization``
        stays ``denoinc``."""
        home = self.organization
        self._org_create({"org": "otherinc"})
        other, self.organization = self.organization, home
        return other

    def _personal_form_in_org_project(self, xlsform_path=None):
        """A form ``self.user`` owns, in a project ``denoinc`` owns."""
        self._project_create({"name": "personal"})
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        XForm.objects.filter(pk=self.xform.pk).update(project=self.org_project)
        self.xform.refresh_from_db()
        self.assertEqual(self.xform.user, self.user)
        self.assert_org_owns(self.xform.project.organization)
        return self.xform


@gating(GATE_PUBLISH_DATA)
class TestDataViewOwners(OrgWiringTestCase):
    def setUp(self):
        super().setUp()
        self._publish_xls_form_to_project(xlsform_path=TUTORIAL)
        self.org_form = self.xform
        self.assert_org_owns(self.org_form.user)
        self.assertFalse(self.org_form.shared_data)
        self._project_create({"name": "open org project", "owner": self.org_url})
        Project.objects.filter(pk=self.project.pk).update(shared=True)
        self.public_project = Project.objects.get(pk=self.project.pk)
        self.assertTrue(self.public_project.shared)
        self.assert_org_owns(self.public_project.organization)

    def _create(self, project, xform=None):
        view = DataViewViewSet.as_view({"post": "create"})
        data = {
            "name": "My DataView",
            "xform": _url("forms", (xform or self.org_form).pk),
            "project": _url("projects", project.pk),
            "columns": '["name", "age"]',
            "query": "[]",
        }
        return view(self.factory.post("/", data=data, **self.extra))

    def _move(self, dataview, project):
        view = DataViewViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/", data={"project": _url("projects", project.pk)}, **self.extra
        )
        return view(request, pk=dataview.pk)

    def _private_dataview(self):
        return DataView.objects.create(
            name="existing",
            xform=self.org_form,
            project=self.org_project,
            columns=["name"],
        )

    def test_creating_a_public_dataview_is_refused_when_the_org_requires_it(self):
        self._require([GATE_PUBLISH_DATA])

        self.assert_enrol_required(self._create(self.public_project))
        self.assertFalse(DataView.objects.exists())

    def test_creating_a_public_dataview_goes_through_when_not_required(self):
        self._require([GATE_TRANSFER_PROJECT])

        response = self._create(self.public_project)

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(DataView.objects.get().project, self.public_project)

    def test_moving_a_dataview_into_public_is_refused_when_the_org_requires_it(self):
        dataview = self._private_dataview()
        self._require([GATE_PUBLISH_DATA])

        self.assert_enrol_required(self._move(dataview, self.public_project))
        dataview.refresh_from_db()
        self.assertEqual(dataview.project, self.org_project)

    def test_moving_a_dataview_into_public_goes_through_when_not_required(self):
        dataview = self._private_dataview()
        self._require([])

        response = self._move(dataview, self.public_project)

        self.assertEqual(response.status_code, 200, response.data)
        dataview.refresh_from_db()
        self.assertEqual(dataview.project, self.public_project)

    def test_the_dataview_projects_org_counts_for_a_personal_form(self):
        self._project_create({"name": "personal"})
        self._publish_xls_form_to_project(xlsform_path=TUTORIAL)
        personal_form = self.xform
        self.assertEqual(personal_form.user, self.user)
        self.assertEqual(personal_form.project.organization, self.user)
        self._require([GATE_PUBLISH_DATA])

        self.assert_enrol_required(self._create(self.public_project, personal_form))
        self.assertFalse(DataView.objects.exists())
        self._require([])
        response = self._create(self.public_project, personal_form)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(DataView.objects.get().xform, personal_form)


@gating(GATE_TRANSFER_PROJECT)
class TestMergedXFormOwners(OrgWiringTestCase):
    def _merge(self, project, xforms):
        view = MergedXFormViewSet.as_view({"post": "create"})
        data = {
            "xforms": [_url("forms", xform.pk) for xform in xforms],
            "name": "Merged Dataset",
            "project": _url("projects", project.pk),
        }
        return view(self.factory.post("/", data=data, **self.extra))

    def _personal_forms(self):
        project = get_user_default_project(self.user)
        forms = [
            self._publish_markdown(MD, self.user, project=project, id_string=name)
            for name in ("a", "b")
        ]
        for xform in forms:
            self.assertEqual(xform.user, self.user)
        return forms

    def test_merging_into_an_org_project_is_refused_when_the_org_requires_it(self):
        forms = self._personal_forms()
        self._require([GATE_TRANSFER_PROJECT])

        self.assert_enrol_required(self._merge(self.org_project, forms))
        self.assertFalse(MergedXForm.objects.exists())

    def test_merging_into_an_org_project_goes_through_when_not_required(self):
        forms = self._personal_forms()
        self._require([])

        response = self._merge(self.org_project, forms)

        self.assertEqual(response.status_code, 201, response.data)
        merged = MergedXForm.objects.get(pk=response.data["id"])
        self.assertEqual(merged.project, self.org_project)

    def _personal_forms_in_org_project(self):
        """Forms ``self.user`` owns, in a project ``denoinc`` owns, so only
        their project names ``denoinc``."""
        forms = self._personal_forms()
        XForm.objects.filter(pk__in=[xform.pk for xform in forms]).update(
            project=self.org_project
        )
        for xform in forms:
            xform.refresh_from_db()
            self.assertEqual(xform.user, self.user)
            self.assert_org_owns(xform.project.organization)
            self.assertFalse(xform.shared_data)
        return forms

    def _own_public_project(self):
        project = get_user_default_project(self.user)
        Project.objects.filter(pk=project.pk).update(shared=True)
        project.refresh_from_db()
        self.assertEqual(project.organization, self.user)
        self.assertTrue(project.shared)
        return project

    @gating(GATE_PUBLISH_DATA)
    def test_the_source_forms_project_org_refuses_a_public_merge(self):
        forms = self._personal_forms_in_org_project()
        public = self._own_public_project()
        self._require([GATE_PUBLISH_DATA])

        self.assert_enrol_required(self._merge(public, forms))
        self.assertFalse(MergedXForm.objects.exists())

    @gating(GATE_PUBLISH_DATA)
    def test_a_public_merge_of_org_project_forms_goes_through_when_not_required(
        self,
    ):
        forms = self._personal_forms_in_org_project()
        public = self._own_public_project()
        self._require([GATE_TRANSFER_PROJECT])

        response = self._merge(public, forms)

        self.assertEqual(response.status_code, 201, response.data)
        merged = MergedXForm.objects.get(pk=response.data["id"])
        self.assertEqual(merged.project, public)


@gating(GATE_SHARE_FORM_ADMIN)
class TestShareFormOwners(OrgWiringTestCase):
    """Appointing a form owner or manager."""

    def setUp(self):
        super().setUp()
        self.alice = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        ).user

    def _org_form(self):
        self._publish_xls_form_to_project()
        self.assert_org_owns(self.xform.user)
        self.assert_org_owns(self.xform.project.organization)
        return self.xform

    def _share(self, xform, role):
        self.assertFalse(role.user_has_role(self.alice, xform))
        view = XFormViewSet.as_view({"post": "share"})
        request = self.factory.post(
            "/", data={"username": "alice", "role": role.name}, **self.extra
        )
        return view(request, pk=xform.pk)

    def test_sharing_as_manager_is_refused_when_the_org_requires_it(self):
        xform = self._org_form()
        self._require([GATE_SHARE_FORM_ADMIN])

        self.assert_enrol_required(self._share(xform, ManagerRole))
        self.assertFalse(ManagerRole.user_has_role(self.alice, xform))

    def test_sharing_as_manager_goes_through_when_not_required(self):
        xform = self._org_form()
        self._require([GATE_PUBLISH_DATA])

        response = self._share(xform, ManagerRole)

        self.assertEqual(response.status_code, 204, response.data)
        self.assertTrue(ManagerRole.user_has_role(self.alice, xform))

    def test_the_forms_project_org_counts_for_a_personal_form(self):
        xform = self._personal_form_in_org_project()
        self._require([GATE_SHARE_FORM_ADMIN])

        self.assert_enrol_required(self._share(xform, OwnerRole))
        self.assertFalse(OwnerRole.user_has_role(self.alice, xform))
        self._require([])
        self.assertEqual(self._share(xform, OwnerRole).status_code, 204)
        self.assertTrue(OwnerRole.user_has_role(self.alice, xform))


@gating(GATE_TRANSFER_PROJECT)
class TestXFormUpdateOwners(OrgWiringTestCase):
    """Moving a form by update counts the account it moves to."""

    def setUp(self):
        super().setUp()
        self._project_create({"name": "personal"})
        self.personal_project = self.project
        self._publish_xls_form_to_project()
        self.assertEqual(self.xform.user, self.user)
        self.assertEqual(self.xform.project, self.personal_project)
        self.assertEqual(self.personal_project.organization, self.user)
        self.assertFalse(self.org_project.shared)

    def _move(self, project):
        view = XFormViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/", data={"project": _url("projects", project.pk)}, **self.extra
        )
        return view(request, pk=self.xform.pk)

    def test_moving_into_an_org_project_is_refused_when_the_org_requires_it(self):
        self._require([GATE_TRANSFER_PROJECT])

        self.assert_enrol_required(self._move(self.org_project))
        self.xform.refresh_from_db()
        self.assertEqual(self.xform.project, self.personal_project)

    def test_moving_into_an_org_project_goes_through_when_not_required(self):
        self._require([GATE_PUBLISH_DATA])

        response = self._move(self.org_project)

        self.assertEqual(response.status_code, 200, response.data)
        self.xform.refresh_from_db()
        self.assertEqual(self.xform.project, self.org_project)


@gating(GATE_REQUIRE_AUTH)
class TestOrgProfileOwners(OrgWiringTestCase):
    """An organisation's require_auth, toggled through its user profile."""

    def setUp(self):
        super().setUp()
        self.assert_org_owns(self._org_profile().user)
        self.assertFalse(self._org_profile().require_auth)

    def _org_profile(self):
        return UserProfile.objects.get(user__username=self.organization.user.username)

    def _toggle_require_auth(self):
        view = UserProfileViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/", data={"require_auth": True}, format="json", **self.extra
        )
        return view(request, user=self.organization.user.username)

    def test_toggling_require_auth_is_refused_when_the_org_requires_it(self):
        self._require([GATE_REQUIRE_AUTH])

        self.assert_enrol_required(self._toggle_require_auth())
        self.assertFalse(self._org_profile().require_auth)

    def test_toggling_require_auth_goes_through_when_not_required(self):
        self._require([GATE_PUBLISH_DATA])

        response = self._toggle_require_auth()

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(self._org_profile().require_auth)


@gating(GATE_PUBLISH_DATA)
class TestMetaDataOwners(OrgWiringTestCase):
    """A public link on a form, a project or a submission."""

    def setUp(self):
        super().setUp()
        self._publish_xls_form_to_project()
        self.assert_org_owns(self.xform.user)

    def _create_link(self, field, content_object):
        view = MetaDataViewSet.as_view({"post": "create"})
        data = {
            "data_type": "public_link",
            "data_value": "True",
            field: content_object.pk,
        }
        return view(self.factory.post("/", data=data, **self.extra))

    def _org_submission(self):
        survey = self.surveys[0]
        path = os.path.join(
            self.main_directory,
            "fixtures",
            "transportation",
            "instances",
            survey,
            f"{survey}.xml",
        )
        self._make_submission(path, username=self.organization.user.username)
        self.assertEqual(self.response.status_code, 201)
        instance = Instance.objects.get(xform=self.xform)
        self.assert_org_owns(instance.xform.user)
        return instance

    def _assert_link(self, content_object, on):
        self.assertEqual(bool(MetaData.public_link(content_object)), on)

    def test_a_form_link_is_refused_when_the_org_requires_it(self):
        self._require([GATE_PUBLISH_DATA])

        self.assert_enrol_required(self._create_link("xform", self.xform))
        self._assert_link(self.xform, False)

    def test_a_form_link_goes_through_when_not_required(self):
        self._require([])

        response = self._create_link("xform", self.xform)

        self.assertEqual(response.status_code, 201, response.data)
        self._assert_link(self.xform, True)

    def test_a_project_link_is_refused_when_the_org_requires_it(self):
        self._require([GATE_PUBLISH_DATA])

        self.assert_enrol_required(self._create_link("project", self.org_project))
        self._assert_link(self.org_project, False)

    def test_a_project_link_goes_through_when_not_required(self):
        self._require([])

        response = self._create_link("project", self.org_project)

        self.assertEqual(response.status_code, 201, response.data)
        self._assert_link(self.org_project, True)

    def test_a_submission_link_is_refused_when_its_forms_org_requires_it(self):
        instance = self._org_submission()
        self._require([GATE_PUBLISH_DATA])

        self.assert_enrol_required(self._create_link("instance", instance))
        self._assert_link(instance, False)

    def test_a_submission_link_goes_through_when_not_required(self):
        instance = self._org_submission()
        self._require([])

        response = self._create_link("instance", instance)

        self.assertEqual(response.status_code, 201, response.data)
        self._assert_link(instance, True)

    def test_the_forms_project_org_counts_for_a_personal_form(self):
        xform = self._personal_form_in_org_project()
        self._require([GATE_PUBLISH_DATA])

        self.assert_enrol_required(self._create_link("xform", xform))
        self._assert_link(xform, False)
        self._require([])
        self.assertEqual(self._create_link("xform", xform).status_code, 201)
        self._assert_link(xform, True)


@gating(GATE_PUBLISH_DATA)
class TestOpenDataOwners(OrgWiringTestCase):
    def setUp(self):
        super().setUp()
        self._publish_xls_form_to_project()
        self.assert_org_owns(self.xform.user)
        self.assertFalse(OpenData.objects.exists())

    def _request(self, method, action, data, **kwargs):
        view = OpenDataViewSet.as_view({method: action})
        request = getattr(self.factory, method)(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        return view(request, **kwargs)

    def _create(self, xform=None):
        payload = {
            "object_id": (xform or self.xform).pk,
            "name": "tableau",
            "data_type": "xform",
        }
        return self._request("post", "create", payload)

    def _inactive_link(self):
        open_data, _created = get_or_create_opendata(self.xform)
        OpenData.objects.filter(pk=open_data.pk).update(active=False)
        open_data.refresh_from_db()
        self.assertFalse(open_data.active)
        return open_data

    def _reactivate(self, open_data):
        return self._request(
            "patch", "partial_update", {"active": True}, uuid=open_data.uuid
        )

    def test_creating_a_link_is_refused_when_the_org_requires_it(self):
        self._require([GATE_PUBLISH_DATA])

        self.assert_enrol_required(self._create())
        self.assertFalse(OpenData.objects.exists())

    def test_creating_a_link_goes_through_when_not_required(self):
        self._require([])

        response = self._create()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(OpenData.objects.get(object_id=self.xform.pk).active)

    def test_reactivating_a_link_is_refused_when_the_org_requires_it(self):
        open_data = self._inactive_link()
        self._require([GATE_PUBLISH_DATA])

        self.assert_enrol_required(self._reactivate(open_data))
        open_data.refresh_from_db()
        self.assertFalse(open_data.active)

    def test_reactivating_a_link_goes_through_when_not_required(self):
        open_data = self._inactive_link()
        self._require([])

        response = self._reactivate(open_data)

        self.assertEqual(response.status_code, 200, response.data)
        open_data.refresh_from_db()
        self.assertTrue(open_data.active)

    def test_the_forms_project_org_counts_for_a_personal_form(self):
        xform = self._personal_form_in_org_project()
        self._require([GATE_PUBLISH_DATA])

        self.assert_enrol_required(self._create(xform))
        self.assertFalse(OpenData.objects.filter(object_id=xform.pk).exists())
        self._require([])
        self.assertEqual(self._create(xform).status_code, 201)
        self.assertTrue(OpenData.objects.filter(object_id=xform.pk).exists())


@gating(GATE_CHANGE_WEBHOOK)
class TestRestServiceOwners(OrgWiringTestCase):
    def setUp(self):
        super().setUp()
        self._publish_xls_form_to_project()
        self.assert_org_owns(self.xform.user)
        self.assertFalse(RestService.objects.exists())

    def _request(self, method, data, **kwargs):
        view = RestServicesViewSet.as_view(
            {"post": "create", "patch": "partial_update"}
        )
        request = getattr(self.factory, method)(
            "/", data=data, format="json", **self.extra
        )
        return view(request, **kwargs)

    def _create(self, xform=None):
        data = {
            "name": "generic_json",
            "service_url": SERVICE_URL,
            "xform": (xform or self.xform).pk,
        }
        return self._request("post", data)

    def _service(self):
        return RestService.objects.create(
            xform=self.xform, name="generic_json", service_url=SERVICE_URL
        )

    def _post_page(self):
        url = reverse(
            add_service,
            kwargs={
                "username": self.organization.user.username,
                "id_string": self.xform.id_string,
            },
        )
        return self.client.post(
            url, {"service_name": "generic_json", "service_url": SERVICE_URL}
        )

    def _service_urls(self):
        return list(RestService.objects.values_list("service_url", flat=True))

    def test_creating_a_webhook_is_refused_when_the_org_requires_it(self):
        self._require([GATE_CHANGE_WEBHOOK])

        self.assert_enrol_required(self._create())
        self.assertFalse(RestService.objects.exists())

    def test_creating_a_webhook_goes_through_when_not_required(self):
        self._require([])

        response = self._create()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self._service_urls(), [SERVICE_URL])

    def test_redirecting_a_webhook_is_refused_when_the_org_requires_it(self):
        service = self._service()
        self._require([GATE_CHANGE_WEBHOOK])

        response = self._request("patch", {"service_url": OTHER_URL}, pk=service.pk)

        self.assert_enrol_required(response)
        service.refresh_from_db()
        self.assertEqual(service.service_url, SERVICE_URL)

    def test_redirecting_a_webhook_goes_through_when_not_required(self):
        service = self._service()
        self._require([])

        response = self._request("patch", {"service_url": OTHER_URL}, pk=service.pk)

        self.assertEqual(response.status_code, 200, response.data)
        service.refresh_from_db()
        self.assertEqual(service.service_url, OTHER_URL)

    def test_the_forms_project_org_counts_for_a_personal_form(self):
        xform = self._personal_form_in_org_project()
        self._require([GATE_CHANGE_WEBHOOK])

        self.assert_enrol_required(self._create(xform))
        self.assertFalse(RestService.objects.exists())
        self._require([])
        self.assertEqual(self._create(xform).status_code, 201)
        self.assertEqual(self._service_urls(), [SERVICE_URL])

    def test_the_page_refuses_a_webhook_when_the_org_requires_it(self):
        self._require([GATE_CHANGE_WEBHOOK])

        self.assert_page_enrol_required(self._post_page())
        self.assertFalse(RestService.objects.exists())

    def test_the_page_adds_a_webhook_when_not_required(self):
        self._require([])

        response = self._post_page()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._service_urls(), [SERVICE_URL])
