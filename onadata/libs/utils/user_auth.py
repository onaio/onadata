import base64
import re
from functools import wraps

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from guardian.shortcuts import assign_perm, get_perms_for_model

from onadata.apps.api.models import OrganizationProfile, Team
from onadata.apps.logger.models import MergedXForm, Note, Project, XForm
from onadata.apps.main.models import UserProfile
from onadata.libs.utils.viewer_tools import get_form


class HttpResponseNotAuthorized(HttpResponse):
    status_code = 401

    def __init__(self):
        HttpResponse.__init__(self)
        self['WWW-Authenticate'] =\
            'Basic realm="%s"' % Site.objects.get_current().name


def check_and_set_user(request, username):
    if username != request.user.username:
        return HttpResponseRedirect("/%s" % username)
    content_user = None
    try:
        content_user = User.objects.get(username=username)
    except User.DoesNotExist:
        return HttpResponseRedirect("/")
    return content_user


def set_profile_data(data, content_user):
    # create empty profile if none exists
    profile, created = UserProfile.objects\
        .get_or_create(user=content_user)
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
        home_page = "http://%s" % home_page

    data.update({
        'location': location,
        'user_instances': user_instances,
        'home_page': home_page,
        'num_forms': num_forms,
        'forms': forms,
        'profile': profile,
        'content_user': content_user
    })


def has_permission(xform, owner, request, shared=False):
    user = request.user
    return shared or xform.shared_data or\
        (hasattr(request, 'session') and
         request.session.get('public_link') == xform.uuid) or\
        owner == user or\
        user.has_perm('logger.view_xform', xform) or\
        user.has_perm('logger.change_xform', xform)


def has_edit_permission(xform, owner, request, shared=False):
    user = request.user
    return (shared and xform.shared_data) or owner == user or\
        user.has_perm('logger.change_xform', xform)


def check_and_set_user_and_form(username, id_string, request):
    xform_kwargs = {
        'id_string__iexact': id_string,
        'user__username__iexact': username
    }

    xform = get_form(xform_kwargs)
    owner = User.objects.get(username=username)
    return [xform, owner] if has_permission(xform, owner, request)\
        else [False, False]


def check_and_set_form_by_id_string(username, id_string, request):
    xform_kwargs = {
        'id_string__iexact': id_string,
        'user__username__iexact': username
    }

    xform = get_form(xform_kwargs)
    return xform if has_permission(xform, xform.user, request)\
        else False


def check_and_set_form_by_id(pk, request):
    xform = get_object_or_404(XForm, pk=pk)
    return xform if has_permission(xform, xform.user, request)\
        else False


def get_xform_and_perms(username, id_string, request):
    xform_kwargs = {
        'id_string__iexact': id_string,
        'user__username__iexact': username
    }

    xform = get_form(xform_kwargs)
    is_owner = xform.user == request.user
    can_edit = is_owner or\
        request.user.has_perm('logger.change_xform', xform)
    can_view = can_edit or\
        request.user.has_perm('logger.view_xform', xform)
    return [xform, is_owner, can_edit, can_view]


def get_xform_users_with_perms(xform):
    """Similar to django-guadian's get_users_with_perms here the query makes
    use of the xformuserobjectpermission_set to return a dictionary of users
    with a list of permissions to the XForm object. The query in use is not as
    expensive as the one in use with get_users_with_perms
    """
    user_perms = {}
    for p in xform.xformuserobjectpermission_set.all().select_related(
            'user', 'permission').only('user', 'permission__codename',
                                       'content_object_id'):
        if p.user.username not in user_perms:
            user_perms[p.user] = []
        user_perms[p.user].append(p.permission.codename)

    return user_perms


def helper_auth_helper(request):
    if request.user and request.user.is_authenticated():
        return None
        # source, http://djangosnippets.org/snippets/243/
    if 'HTTP_AUTHORIZATION' in request.META:
        auth = request.META['HTTP_AUTHORIZATION'].split()
        if len(auth) == 2 and auth[0].lower() == "basic":
            uname, passwd = base64.b64decode(auth[1].encode(
                'utf-8')).decode('utf-8').split(':')
            user = authenticate(username=uname, password=passwd)
            if user:
                request.user = user
                return None
    response = HttpResponseNotAuthorized()
    return response


def basic_http_auth(func):
    @wraps(func)
    def inner(request, *args, **kwargs):
        result = helper_auth_helper(request)
        if result is not None:
            return result
        return func(request, *args, **kwargs)

    return inner


def http_auth_string(username, password):
    credentials = base64.b64encode((
        '%s:%s' % (username, password)).encode('utf-8')
        ).decode('utf-8').strip()
    auth_string = 'Basic %s' % credentials
    return auth_string


def add_cors_headers(response):
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET'
    response['Access-Control-Allow-Headers'] = ('Accept, Origin,'
                                                ' X-Requested-With,'
                                                ' Authorization')
    response['Content-Type'] = 'application/json'
    return response


def set_api_permissions_for_user(user):
    models = [
        UserProfile, XForm, MergedXForm, Project, Team, OrganizationProfile,
        Note
    ]
    for model in models:
        for perm in get_perms_for_model(model):
            assign_perm('%s.%s' % (perm.content_type.app_label, perm.codename),
                        user)


def get_user_default_project(user):
    name = u"{}'s Project".format(user.username)
    user_projects = user.project_owner.filter(name=name, organization=user)

    if user_projects:
        project = user_projects[0]
    else:
        metadata = {'description': 'Default Project'}
        project = Project.objects.create(
            name=name, organization=user, created_by=user, metadata=metadata)

    return project
