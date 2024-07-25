# -*- coding: utf-8 -*-
"""
User authentication utility functions.
"""
import base64
import re
from functools import wraps

from django.apps import apps
from django.contrib.auth import authenticate, get_user_model
from django.contrib.sites.models import Site
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from guardian.shortcuts import assign_perm, get_perms_for_model
from rest_framework.authtoken.models import Token

from onadata.apps.api.models.team import Team
from onadata.apps.api.models.temp_token import TempToken
from onadata.apps.logger.models.note import Note
from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.viewer_tools import get_form

# pylint: disable=invalid-name
User = get_user_model()
UserProfile = apps.get_model("main", "UserProfile")
OrganizationProfile = apps.get_model("api", "OrganizationProfile")
MergedXForm = apps.get_model("logger", "MergedXForm")


class HttpResponseNotAuthorized(HttpResponse):
    """HttpResponse that sets basic authentication prompt."""

    status_code = 401

    def __init__(self, *args, **kwargs):
        HttpResponse.__init__(self)
        self["WWW-Authenticate"] = f'Basic realm="{Site.objects.get_current().name}"'


def check_and_set_user(request, username):
    """Returns a User object or a string to redirect."""
    if username != request.user.username:
        return f"/{username}"
    content_user = None
    try:
        content_user = User.objects.get(username=username)
    except User.DoesNotExist:
        return "/"
    return content_user


def set_profile_data(data, content_user):
    """Set user profile data."""
    # create empty profile if none exists
    profile, _created = UserProfile.objects.get_or_create(user=content_user)
    location = ""
    if profile.city:
        location = profile.city
    if profile.country:
        if profile.city:
            location += ", "
        location += profile.country
    forms = content_user.xforms.filter(shared__exact=1)
    num_forms = forms.count()
    user_instances = profile.num_of_submissions
    home_page = profile.home_page
    if home_page and re.match("http", home_page) is None:
        home_page = f"http://{home_page}"

    data.update(
        {
            "location": location,
            "user_instances": user_instances,
            "home_page": home_page,
            "num_forms": num_forms,
            "forms": forms,
            "profile": profile,
            "content_user": content_user,
        }
    )


def has_permission(xform, owner, request, shared=False):
    """Checks if the ``request.user`` has the necessary permissions to an ``xform``."""
    user = request.user
    return (
        shared
        or xform.shared_data  # noqa W503
        or (  # noqa W503
            hasattr(request, "session")
            and request.session.get("public_link") == xform.uuid  # noqa W503
        )
        or owner == user  # noqa W503
        or user.has_perm("logger.view_xform", xform)  # noqa W503
        or user.has_perm("logger.change_xform", xform)  # noqa W503
    )


def has_edit_permission(xform, owner, request, shared=False):
    """Checks if the ``request.user`` has edit permissions to the ``xform``."""
    user = request.user
    return (
        (shared and xform.shared_data)
        or owner == user  # noqa W503
        or user.has_perm("logger.change_xform", xform)  # noqa W503
    )


def check_and_set_user_and_form(username, id_string, request):
    """Checks and returns an `xform` and `owner` if ``request.user`` has permission."""
    xform_kwargs = {"id_string__iexact": id_string, "user__username__iexact": username}

    xform = get_form(xform_kwargs)
    owner = User.objects.get(username=username)
    return [xform, owner] if has_permission(xform, owner, request) else [False, False]


def check_and_set_form_by_id_string(username, id_string, request):
    """Checks xform by ``id_string`` and returns an `xform` if ``request.user``
    has permission."""
    xform_kwargs = {"id_string__iexact": id_string, "user__username__iexact": username}

    xform = get_form(xform_kwargs)
    return xform if has_permission(xform, xform.user, request) else False


def check_and_set_form_by_id(pk, request):
    """Checks xform by ``pk`` and returns an `xform` if ``request.user``
    has permission."""
    xform = get_object_or_404(XForm, pk=pk)
    return xform if has_permission(xform, xform.user, request) else False


def get_xform_and_perms(username, id_string, request):
    """Returns the `xform` with the matching ``id_string``, and the permissions the
    ``request.user`` has."""
    xform_kwargs = {"id_string__iexact": id_string, "user__username__iexact": username}

    xform = get_form(xform_kwargs)
    is_owner = xform.user == request.user
    can_edit = is_owner or request.user.has_perm("logger.change_xform", xform)
    can_view = can_edit or request.user.has_perm("logger.view_xform", xform)
    return [xform, is_owner, can_edit, can_view]


def get_xform_users_with_perms(xform):
    """Similar to django-guadian's get_users_with_perms here the query makes
    use of the xformuserobjectpermission_set to return a dictionary of users
    with a list of permissions to the XForm object. The query in use is not as
    expensive as the one in use with get_users_with_perms
    """
    user_perms = {}
    for p in (
        xform.xformuserobjectpermission_set.all()
        .select_related("user", "permission")
        .only("user", "permission__codename", "content_object_id")
    ):
        if p.user.username not in user_perms:
            user_perms[p.user] = []
        user_perms[p.user].append(p.permission.codename)

    return user_perms


def helper_auth_helper(request):
    """Authenticates a user via basic authentication."""
    if request.user and request.user.is_authenticated:
        return None
        # source, http://djangosnippets.org/snippets/243/
    if "HTTP_AUTHORIZATION" in request.META:
        auth = request.headers["Authorization"].split()
        if len(auth) == 2 and auth[0].lower() == "basic":
            uname, passwd = (
                base64.b64decode(auth[1].encode("utf-8")).decode("utf-8").split(":")
            )
            user = authenticate(username=uname, password=passwd)
            if user:
                request.user = user
                return None

    return HttpResponseNotAuthorized()


def basic_http_auth(func):
    """A basic authentication decorator."""

    @wraps(func)
    def _inner(request, *args, **kwargs):
        result = helper_auth_helper(request)
        if result is not None:
            return result
        return func(request, *args, **kwargs)

    return _inner


def http_auth_string(username, password):
    """Return a basic authentication string with username and password."""
    credentials = (
        base64.b64encode(f"{username}:{password}".encode("utf-8"))
        .decode("utf-8")
        .strip()
    )
    auth_string = f"Basic {credentials}"

    return auth_string


def add_cors_headers(response):
    """Add CORS headers to the HttpResponse ``response`` instance."""
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "GET"
    response["Access-Control-Allow-Headers"] = (
        "Accept, Origin, X-Requested-With, Authorization"
    )
    response["Content-Type"] = "application/json"

    return response


def set_api_permissions_for_user(user):
    """Sets the permissions to allow a ``user`` to access the APU."""
    models = [UserProfile, XForm, MergedXForm, Project, Team, OrganizationProfile, Note]
    for model in models:
        for perm in get_perms_for_model(model):
            assign_perm(f"{perm.content_type.app_label}.{perm.codename}", user)


def get_user_default_project(user):
    """Return's the ``user``'s default project, creates it if it does not exist.'"""
    name = f"{user.username}'s Project"
    user_projects = user.project_owner.filter(name=name, organization=user)

    if user_projects:
        project = user_projects[0]
    else:
        metadata = {"description": "Default Project"}
        project = Project.objects.create(
            name=name, organization=user, created_by=user, metadata=metadata
        )

    return project


def invalidate_and_regen_tokens(user):
    """
    Invalidates a users Access and Temp tokens and
    generates new ones
    """
    try:
        TempToken.objects.filter(user=user).delete()
    except TempToken.DoesNotExist:
        pass

    try:
        Token.objects.filter(user=user).delete()
    except Token.DoesNotExist:
        pass

    access_token = Token.objects.create(user=user).key
    temp_token = TempToken.objects.create(user=user).key

    return {"access_token": access_token, "temp_token": temp_token}
