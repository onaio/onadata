# -*- coding=utf-8 -*-
# pylint: disable=too-many-lines
"""
Main views.
"""
import json
import os
from datetime import datetime

from bson import json_util
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.storage import default_storage, get_storage_class
from django.core.urlresolvers import reverse
from django.db import IntegrityError, OperationalError
from django.http import (HttpResponse, HttpResponseBadRequest,
                         HttpResponseForbidden, HttpResponseNotFound,
                         HttpResponseRedirect, HttpResponseServerError)
from django.shortcuts import get_object_or_404, render
from django.template import RequestContext, loader
from django.utils.translation import ugettext as _
from django.views.decorators.http import (require_GET, require_http_methods,
                                          require_POST)
from guardian.shortcuts import assign_perm, remove_perm
from oauth2_provider.views.base import AuthorizationView
from rest_framework.authtoken.models import Token

from onadata.apps.logger.models import Instance, XForm
from onadata.apps.logger.models.xform import get_forms_shared_with_user
from onadata.apps.logger.views import enter_data
from onadata.apps.logger.xform_instance_parser import XLSFormError
from onadata.apps.main.forms import (ActivateSMSSupportForm, DataLicenseForm,
                                     ExternalExportForm, FormLicenseForm,
                                     MapboxLayerForm, MediaForm,
                                     PermissionForm, QuickConverter,
                                     QuickConverterFile, QuickConverterURL,
                                     SourceForm, SupportDocForm,
                                     UserProfileForm)
from onadata.apps.main.models import AuditLog, MetaData, UserProfile
from onadata.apps.sms_support.autodoc import get_autodoc_for
from onadata.apps.sms_support.providers import providers_doc
from onadata.apps.sms_support.tools import (check_form_sms_compatibility,
                                            is_sms_related)
from onadata.apps.viewer.models.data_dictionary import (DataDictionary,
                                                        upload_to)
from onadata.apps.viewer.models.parsed_instance import (DATETIME_FORMAT,
                                                        query_data)
from onadata.apps.viewer.views import attachment_url
from onadata.libs.exceptions import EnketoError
from onadata.libs.utils.decorators import is_owner
from onadata.libs.utils.export_tools import upload_template_for_external_export
from onadata.libs.utils.log import Actions, audit_log
from onadata.libs.utils.logger_tools import (publish_form,
                                             response_with_mimetype_and_name)
from onadata.libs.utils.qrcode import generate_qrcode
from onadata.libs.utils.user_auth import (add_cors_headers, check_and_set_user,
                                          check_and_set_user_and_form,
                                          get_user_default_project,
                                          get_xform_and_perms,
                                          get_xform_users_with_perms,
                                          has_permission,
                                          helper_auth_helper, set_profile_data)
from onadata.libs.utils.viewer_tools import (enketo_url,
                                             get_enketo_preview_url, get_form)


def home(request):
    if request.user.username:
        return HttpResponseRedirect(
            reverse(profile, kwargs={'username': request.user.username}))

    return render(request, 'home.html')


@login_required
def login_redirect(request):
    return HttpResponseRedirect(
        reverse(profile, kwargs={'username': request.user.username}))


@require_POST
@login_required
def clone_xlsform(request, username):
    """
    Copy a public/Shared form to a users list of forms.
    Eliminates the need to download Excel File and upload again.
    """
    to_username = request.user.username
    message = {'type': None, 'text': '....'}
    message_list = []

    def set_form():
        form_owner = request.POST.get('username')
        id_string = request.POST.get('id_string')
        xform = XForm.objects.get(user__username__iexact=form_owner,
                                  id_string__iexact=id_string,
                                  deleted_at__isnull=True)
        if len(id_string) > 0 and id_string[0].isdigit():
            id_string = '_' + id_string
        path = xform.xls.name
        if default_storage.exists(path):
            project = get_user_default_project(request.user)
            xls_file = upload_to(None, '%s%s.xls' % (
                id_string, XForm.CLONED_SUFFIX), to_username)
            xls_data = default_storage.open(path)
            xls_file = default_storage.save(xls_file, xls_data)
            survey = DataDictionary.objects.create(
                user=request.user,
                xls=xls_file,
                project=project
            ).survey
            # log to cloner's account
            audit = {}
            audit_log(
                Actions.FORM_CLONED, request.user, request.user,
                _("Cloned form '%(id_string)s'.") %
                {
                    'id_string': survey.id_string,
                }, audit, request)
            clone_form_url = reverse(
                show, kwargs={
                    'username': to_username,
                    'id_string': xform.id_string + XForm.CLONED_SUFFIX})
            return {
                'type': 'alert-success',
                'text': _(
                    u'Successfully cloned to %(form_url)s into your '
                    u'%(profile_url)s') % {
                        'form_url': u'<a href="%(url)s">%(id_string)s</a> ' % {
                            'id_string': survey.id_string,
                            'url': clone_form_url
                        },
                        'profile_url': u'<a href="%s">profile</a>.' % reverse(
                            profile, kwargs={'username': to_username})}}

    form_result = publish_form(set_form)
    if form_result['type'] == 'alert-success':
        # comment the following condition (and else)
        # when we want to enable sms check for all.
        # until then, it checks if form barely related to sms
        if is_sms_related(form_result.get('form_o')):
            form_result_sms = check_form_sms_compatibility(form_result)
            message_list = [form_result, form_result_sms]
        else:
            message = form_result
    else:
        message = form_result

    context = RequestContext(request, {
        'message': message, 'message_list': message_list})

    if request.is_ajax():
        res = loader.render_to_string(
            'message.html',
            context_instance=context
        ).replace("'", r"\'").replace('\n', '')

        return HttpResponse(
            "$('#mfeedback').html('%s').show();" % res)
    else:
        return HttpResponse(message['text'])


def profile(request, username):
    content_user = get_object_or_404(User, username__iexact=username)
    form = QuickConverter()
    data = {'form': form}

    # xlsform submission...
    if request.method == 'POST' and request.user.is_authenticated():
        def set_form():
            form = QuickConverter(request.POST, request.FILES)
            survey = form.publish(request.user).survey
            audit = {}
            audit_log(
                Actions.FORM_PUBLISHED, request.user, content_user,
                _("Published form '%(id_string)s'.") %
                {
                    'id_string': survey.id_string,
                }, audit, request)
            enketo_webform_url = reverse(
                enter_data,
                kwargs={'username': username, 'id_string': survey.id_string}
            )
            return {
                'type': 'alert-success',
                'preview_url': reverse(enketo_preview, kwargs={
                    'username': username,
                    'id_string': survey.id_string
                }),
                'text': _(u'Successfully published %(form_id)s.'
                          u' <a href="%(form_url)s">Enter Web Form</a>'
                          u' or <a href="#preview-modal" data-toggle="modal">'
                          u'Preview Web Form</a>') % {
                              'form_id': survey.id_string,
                              'form_url': enketo_webform_url
                          },
                'form_o': survey
            }
        form_result = publish_form(set_form)
        if form_result['type'] == 'alert-success':
            # comment the following condition (and else)
            # when we want to enable sms check for all.
            # until then, it checks if form barely related to sms
            if is_sms_related(form_result.get('form_o')):
                form_result_sms = check_form_sms_compatibility(form_result)
                data['message_list'] = [form_result, form_result_sms]
            else:
                data['message'] = form_result
        else:
            data['message'] = form_result

    # profile view...
    # for the same user -> dashboard
    if content_user == request.user:
        show_dashboard = True
        all_forms = content_user.xforms.filter(deleted_at__isnull=True).count()
        form = QuickConverterFile()
        form_url = QuickConverterURL()

        request_url = request.build_absolute_uri(
            "/%s" % request.user.username)
        url = request_url.replace('http://', 'https://')
        xforms = XForm.objects.filter(user=content_user,
                                      deleted_at__isnull=True)\
            .select_related('user').only(
                'id', 'id_string', 'downloadable', 'shared', 'shared_data',
                'user__username', 'num_of_submissions', 'title',
                'last_submission_time', 'instances_with_geopoints',
                'encrypted', 'date_created')
        user_xforms = xforms
        # forms shared with user
        forms_shared_with = get_forms_shared_with_user(content_user).only(
            'id', 'id_string', 'downloadable', 'shared', 'shared_data',
            'user__username', 'num_of_submissions', 'title',
            'last_submission_time', 'instances_with_geopoints', 'encrypted',
            'date_created')
        xforms_list = [
            {
                'id': 'published',
                'xforms': user_xforms,
                'title': _(u"Published Forms"),
                'small': _("Export, map, and view submissions.")
            },
            {
                'id': 'shared',
                'xforms': forms_shared_with,
                'title': _(u"Shared Forms"),
                'small': _("List of forms shared with you.")
            }
        ]
        data.update({
            'all_forms': all_forms,
            'show_dashboard': show_dashboard,
            'form': form,
            'form_url': form_url,
            'url': url,
            'user_xforms': user_xforms,
            'xforms_list': xforms_list,
            'forms_shared_with': forms_shared_with
        })
    # for any other user -> profile
    set_profile_data(data, content_user)

    try:
        resp = render(request, "profile.html", data)
    except XLSFormError as e:
        resp = HttpResponseBadRequest(e.__str__())

    return resp


def members_list(request):
    if not request.user.is_staff and not request.user.is_superuser:
        return HttpResponseForbidden(_(u'Forbidden.'))
    users = User.objects.all()
    template = 'people.html'

    return render(request, template, {'template': template, 'users': users})


@login_required
def profile_settings(request, username):
    if request.user.username != username:
        return HttpResponseNotFound("Page not found")
    content_user = check_and_set_user(request, username)
    profile, created = UserProfile.objects.get_or_create(user=content_user)
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            # get user
            # user.email = cleaned_email
            form.instance.user.email = form.cleaned_data['email']
            form.instance.user.save()
            form.save()
            # todo: add string rep. of settings to see what changed
            audit = {}
            audit_log(
                Actions.PROFILE_SETTINGS_UPDATED, request.user, content_user,
                _("Profile settings updated."), audit, request)
            return HttpResponseRedirect(reverse(
                public_profile, kwargs={'username': request.user.username}
            ))
    else:
        form = UserProfileForm(
            instance=profile, initial={"email": content_user.email})

    return render(request, "settings.html",
                  {'content_user': content_user, 'form': form})


@require_GET
def public_profile(request, username):
    content_user = check_and_set_user(request, username)
    if isinstance(content_user, HttpResponseRedirect):
        return content_user
    data = {}
    set_profile_data(data, content_user)
    data['is_owner'] = request.user == content_user
    audit = {}
    audit_log(
        Actions.PUBLIC_PROFILE_ACCESSED, request.user, content_user,
        _("Public profile accessed."), audit, request)

    return render(request, "profile.html", data)


@login_required
def dashboard(request):
    content_user = request.user
    data = {
        'form': QuickConverter(),
        'content_user': content_user,
        'url': request.build_absolute_uri("/%s" % request.user.username)
    }
    set_profile_data(data, content_user)

    return render(request, "dashboard.html", data)


def redirect_to_public_link(request, uuid):
    xform = get_object_or_404(XForm, uuid=uuid, deleted_at__isnull=True)
    request.session['public_link'] = \
        xform.uuid if MetaData.public_link(xform) else False

    return HttpResponseRedirect(reverse(show, kwargs={
        'username': xform.user.username,
        'id_string': xform.id_string
    }))


def set_xform_owner_data(data, xform, request, username, id_string):
    data['sms_support_form'] = ActivateSMSSupportForm(
        initial={'enable_sms_support': xform.allows_sms,
                 'sms_id_string': xform.sms_id_string})
    if not xform.allows_sms:
        data['sms_compatible'] = check_form_sms_compatibility(
            None, json_survey=json.loads(xform.json))
    else:
        url_root = request.build_absolute_uri('/')[:-1]
        data['sms_providers_doc'] = providers_doc(
            url_root=url_root,
            username=username,
            id_string=id_string)
        data['url_root'] = url_root

    data['form_license_form'] = FormLicenseForm(
        initial={'value': data['form_license']})
    data['data_license_form'] = DataLicenseForm(
        initial={'value': data['data_license']})
    data['doc_form'] = SupportDocForm()
    data['source_form'] = SourceForm()
    data['media_form'] = MediaForm()
    data['mapbox_layer_form'] = MapboxLayerForm()
    data['external_export_form'] = ExternalExportForm()
    users_with_perms = []

    for perm in get_xform_users_with_perms(xform).items():
        has_perm = []
        if 'change_xform' in perm[1]:
            has_perm.append(_(u"Can Edit"))
        if 'view_xform' in perm[1]:
            has_perm.append(_(u"Can View"))
        if 'report_xform' in perm[1]:
            has_perm.append(_(u"Can submit to"))
        users_with_perms.append((perm[0], u" | ".join(has_perm)))
    data['users_with_perms'] = users_with_perms
    data['permission_form'] = PermissionForm(username)


@require_GET
def show(request, username=None, id_string=None, uuid=None):
    if uuid:
        return redirect_to_public_link(request, uuid)

    xform, is_owner, can_edit, can_view = get_xform_and_perms(
        username, id_string, request)
    # no access
    if not (xform.shared or can_view or request.session.get('public_link')):
        return HttpResponseRedirect(reverse(home))

    data = {}
    data['cloned'] = len(
        XForm.objects.filter(user__username__iexact=request.user.username,
                             id_string__iexact=id_string + XForm.CLONED_SUFFIX,
                             deleted_at__isnull=True)
    ) > 0
    try:
        data['public_link'] = MetaData.public_link(xform)
        data['is_owner'] = is_owner
        data['can_edit'] = can_edit
        data['can_view'] = can_view or request.session.get('public_link')
        data['xform'] = xform
        data['content_user'] = xform.user
        data['base_url'] = "https://%s" % request.get_host()
        data['source'] = MetaData.source(xform)
        data['form_license'] = MetaData.form_license(xform)
        data['data_license'] = MetaData.data_license(xform)
        data['supporting_docs'] = MetaData.supporting_docs(xform)
        data['media_upload'] = MetaData.media_upload(xform)
        data['mapbox_layer'] = MetaData.mapbox_layer_upload(xform)
        data['external_export'] = MetaData.external_export(xform)
    except XLSFormError as e:
        return HttpResponseBadRequest(e.__str__())

    if is_owner:
        set_xform_owner_data(data, xform, request, username, id_string)

    if xform.allows_sms:
        data['sms_support_doc'] = get_autodoc_for(xform)

    return render(request, "show.html", data)


@login_required
@require_GET
def api_token(request, username=None):
    if request.user.username == username:
        user = get_object_or_404(User, username=username)
        data = {}
        data['token_key'], created = Token.objects.get_or_create(user=user)

        return render(request, "api_token.html", data)

    return HttpResponseForbidden(_(u'Permission denied.'))


@require_http_methods(["GET", "OPTIONS"])
def api(request, username=None, id_string=None):
    """
    Returns all results as JSON.  If a parameter string is passed,
    it takes the 'query' parameter, converts this string to a dictionary, an
    that is then used as a MongoDB query string.

    NOTE: only a specific set of operators are allow, currently $or and $and.
    Please send a request if you'd like another operator to be enabled.

    NOTE: Your query must be valid JSON, double check it here,
    http://json.parser.online.fr/

    E.g. api?query='{"last_name": "Smith"}'
    """
    if request.method == "OPTIONS":
        response = HttpResponse()
        add_cors_headers(response)

        return response

    helper_auth_helper(request)
    helper_auth_helper(request)
    xform, owner = check_and_set_user_and_form(username, id_string, request)

    if not xform:
        return HttpResponseForbidden(_(u'Not shared.'))

    query = request.GET.get('query')
    total_records = xform.num_of_submissions

    try:
        args = {
            'xform': xform,
            'query': query,
            'fields': request.GET.get('fields'),
            'sort': request.GET.get('sort')
        }

        if 'page' in request.GET:
            page = int(request.GET.get('page'))
            page_size = request.GET.get('page_size', request.GET.get('limit'))

            if page_size:
                page_size = int(page_size)
            else:
                page_size = 100

            start_index = (page - 1) * page_size
            args["start_index"] = start_index

            args["limit"] = page_size

        if query:
            count_args = args.copy()
            count_args['count'] = True
            count_results = [i for i in query_data(**count_args)]

            if len(count_results):
                total_records = count_results[0].get('count', total_records)

        if 'start' in request.GET:
            args["start_index"] = int(request.GET.get('start'))

        if 'limit' in request.GET:
            args["limit"] = int(request.GET.get('limit'))

        if 'count' in request.GET:
            args["count"] = True if int(request.GET.get('count')) > 0\
                else False

        cursor = query_data(**args)
    except (ValueError, TypeError) as e:
        return HttpResponseBadRequest(e.__str__())

    try:
        response_text = json_util.dumps([i for i in cursor])
    except OperationalError:
        return HttpResponseServerError()

    if 'callback' in request.GET and request.GET.get('callback') != '':
        callback = request.GET.get('callback')
        response_text = ("%s(%s)" % (callback, response_text))

    response = HttpResponse(response_text, content_type='application/json')
    add_cors_headers(response)

    return response


@require_GET
def public_api(request, username, id_string):
    """
    Returns public information about the form as JSON
    """
    xform = get_form({
        'user__username__iexact': username,
        'id_string__iexact': id_string
    })

    _DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
    exports = {
        'username': xform.user.username,
        'id_string': xform.id_string,
        'bamboo_dataset': xform.bamboo_dataset,
        'shared': xform.shared,
        'shared_data': xform.shared_data,
        'downloadable': xform.downloadable,
        'title': xform.title,
        'date_created': xform.date_created.strftime(_DATETIME_FORMAT),
        'date_modified': xform.date_modified.strftime(_DATETIME_FORMAT),
        'uuid': xform.uuid,
    }
    response_text = json.dumps(exports)

    return HttpResponse(response_text, content_type='application/json')


@login_required
def edit(request, username, id_string):
    xform = XForm.objects.get(user__username__iexact=username,
                              id_string__iexact=id_string,
                              deleted_at__isnull=True)
    owner = xform.user

    if username == request.user.username or\
            request.user.has_perm('logger.change_xform', xform):
        if request.POST.get('description') or\
                request.POST.get('description') == '':
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Description for '%(id_string)s' updated from "
                  "'%(old_description)s' to '%(new_description)s'.") %
                {
                    'id_string': xform.id_string,
                    'old_description': xform.description,
                    'new_description': request.POST['description']
                }, audit, request)
            xform.description = request.POST['description']
        elif request.POST.get('title'):
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Title for '%(id_string)s' updated from "
                  "'%(old_title)s' to '%(new_title)s'.") %
                {
                    'id_string': xform.id_string,
                    'old_title': xform.title,
                    'new_title': request.POST.get('title')
                }, audit, request)
            xform.title = request.POST['title']
        elif request.POST.get('toggle_shared'):
            if request.POST['toggle_shared'] == 'data':
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_UPDATED, request.user, owner,
                    _("Data sharing updated for '%(id_string)s' from "
                      "'%(old_shared)s' to '%(new_shared)s'.") %
                    {
                        'id_string': xform.id_string,
                        'old_shared':
                        _("shared") if xform.shared_data else _("not shared"),
                        'new_shared':
                        _("shared")
                        if not xform.shared_data else _("not shared")
                    }, audit, request)
                xform.shared_data = not xform.shared_data
            elif request.POST['toggle_shared'] == 'form':
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_UPDATED, request.user, owner,
                    _("Form sharing for '%(id_string)s' updated "
                      "from '%(old_shared)s' to '%(new_shared)s'.") %
                    {
                        'id_string': xform.id_string,
                        'old_shared':
                        _("shared") if xform.shared else _("not shared"),
                        'new_shared':
                        _("shared") if not xform.shared else _("not shared")
                    }, audit, request)
                xform.shared = not xform.shared
            elif request.POST['toggle_shared'] == 'active':
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_UPDATED, request.user, owner,
                    _("Active status for '%(id_string)s' updated from "
                      "'%(old_shared)s' to '%(new_shared)s'.") %
                    {
                        'id_string': xform.id_string,
                        'old_shared':
                        _("shared") if xform.downloadable else _("not shared"),
                        'new_shared':
                        _("shared")
                        if not xform.downloadable else _("not shared")
                    }, audit, request)
                xform.downloadable = not xform.downloadable
        elif request.POST.get('form-license'):
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Form License for '%(id_string)s' updated to "
                  "'%(form_license)s'.") %
                {
                    'id_string': xform.id_string,
                    'form_license': request.POST['form-license'],
                }, audit, request)
            MetaData.form_license(xform, request.POST['form-license'])
        elif request.POST.get('data-license'):
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Data license for '%(id_string)s' updated to "
                  "'%(data_license)s'.") %
                {
                    'id_string': xform.id_string,
                    'data_license': request.POST['data-license'],
                }, audit, request)
            MetaData.data_license(xform, request.POST['data-license'])
        elif request.POST.get('source') or request.FILES.get('source'):
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Source for '%(id_string)s' updated to '%(source)s'.") %
                {
                    'id_string': xform.id_string,
                    'source': request.POST.get('source'),
                }, audit, request)
            MetaData.source(xform, request.POST.get('source'),
                            request.FILES.get('source'))
        elif request.POST.get('enable_sms_support_trigger') is not None:
            sms_support_form = ActivateSMSSupportForm(request.POST)
            if sms_support_form.is_valid():
                audit = {
                    'xform': xform.id_string
                }
                enabled = \
                    sms_support_form.cleaned_data.get('enable_sms_support')
                if enabled:
                    audit_action = Actions.SMS_SUPPORT_ACTIVATED
                    audit_message = _(u"SMS Support Activated on")
                else:
                    audit_action = Actions.SMS_SUPPORT_DEACTIVATED
                    audit_message = _(u"SMS Support Deactivated on")
                audit_log(
                    audit_action, request.user, owner,
                    audit_message
                    % {'id_string': xform.id_string}, audit, request)
                # stored previous states to be able to rollback form status
                # in case we can't save.
                pe = xform.allows_sms
                pid = xform.sms_id_string
                xform.allows_sms = enabled
                xform.sms_id_string = \
                    sms_support_form.cleaned_data.get('sms_id_string')
                compat = check_form_sms_compatibility(None,
                                                      json.loads(xform.json))
                if compat['type'] == 'alert-error':
                    xform.allows_sms = False
                    xform.sms_id_string = pid
                try:
                    xform.save()
                except IntegrityError:
                    # unfortunately, there's no feedback mechanism here
                    xform.allows_sms = pe
                    xform.sms_id_string = pid

        elif request.POST.get('media_url'):
            uri = request.POST.get('media_url')
            MetaData.media_add_uri(xform, uri)
        elif request.FILES.get('media'):
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Media added to '%(id_string)s'.") %
                {
                    'id_string': xform.id_string
                }, audit, request)
            for aFile in request.FILES.getlist("media"):
                MetaData.media_upload(xform, aFile)
        elif request.POST.get('map_name'):
            mapbox_layer = MapboxLayerForm(request.POST)
            if mapbox_layer.is_valid():
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_UPDATED, request.user, owner,
                    _("Map layer added to '%(id_string)s'.") %
                    {
                        'id_string': xform.id_string
                    }, audit, request)
                MetaData.mapbox_layer_upload(xform, mapbox_layer.cleaned_data)
        elif request.FILES.get('doc'):
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Supporting document added to '%(id_string)s'.") %
                {
                    'id_string': xform.id_string
                }, audit, request)
            MetaData.supporting_docs(xform, request.FILES.get('doc'))
        elif request.POST.get("template_token") \
                and request.POST.get("template_token"):
            template_name = request.POST.get("template_name")
            template_token = request.POST.get("template_token")
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("External export added to '%(id_string)s'.") %
                {
                    'id_string': xform.id_string
                }, audit, request)
            merged = template_name + '|' + template_token
            MetaData.external_export(xform, merged)
        elif request.POST.get("external_url") \
                and request.FILES.get("xls_template"):
            template_upload_name = request.POST.get("template_upload_name")
            external_url = request.POST.get("external_url")
            xls_template = request.FILES.get("xls_template")

            result = upload_template_for_external_export(external_url,
                                                         xls_template)
            status_code = result.split('|')[0]
            token = result.split('|')[1]
            if status_code == '201':
                data_value =\
                    template_upload_name + '|' + external_url + '/xls/' + token
                MetaData.external_export(xform, data_value=data_value)

        xform.update()

        if request.is_ajax():
            return HttpResponse(_(u'Updated succeeded.'))
        else:
            return HttpResponseRedirect(reverse(show, kwargs={
                'username': username,
                'id_string': id_string
            }))

    return HttpResponseForbidden(_(u'Update failed.'))


def getting_started(request):
    template = 'getting_started.html'

    return render(request, 'base.html', {'template': template})


def support(request):
    template = 'support.html'

    return render(request, 'base.html', {'template': template})


def faq(request):
    template = 'faq.html'

    return render(request, 'base.html', {'template': template})


def xls2xform(request):
    template = 'xls2xform.html'

    return render(request, 'base.html', {'template': template})


def tutorial(request):
    template = 'tutorial.html'
    username = request.user.username if request.user.username else \
        'your-user-name'
    url = request.build_absolute_uri("/%s" % username)

    return render(request, 'base.html', {'template': template, 'url': url})


def resources(request):
    if 'fr' in request.LANGUAGE_CODE.lower():
        deck_id = 'a351f6b0a3730130c98b12e3c5740641'
    else:
        deck_id = '1a33a070416b01307b8022000a1de118'

    return render(request, 'resources.html', {'deck_id': deck_id})


def about_us(request):
    a_flatpage = '/about-us/'
    username = request.user.username if request.user.username else \
        'your-user-name'
    url = request.build_absolute_uri("/%s" % username)

    return render(request, 'base.html', {'a_flatpage': a_flatpage, 'url': url})


def privacy(request):
    template = 'privacy.html'

    return render(request, 'base.html', {'template': template})


def tos(request):
    template = 'tos.html'

    return render(request, 'base.html', {'template': template})


def syntax(request):
    template = 'syntax.html'

    return render(request, 'base.html', {'template': template})


def form_gallery(request):
    """
    Return a list of urls for all the shared xls files. This could be
    made a lot prettier.
    """
    data = {}
    if request.user.is_authenticated():
        data['loggedin_user'] = request.user
    data['shared_forms'] = XForm.objects.filter(shared=True,
                                                deleted_at__isnull=True)
    # build list of shared forms with cloned suffix
    id_strings_with_cloned_suffix = [
        x.id_string + XForm.CLONED_SUFFIX for x in data['shared_forms']
    ]
    # build list of id_strings for forms this user has cloned
    data['cloned'] = [
        x.id_string.split(XForm.CLONED_SUFFIX)[0]
        for x in XForm.objects.filter(
            user__username__iexact=request.user.username,
            id_string__in=id_strings_with_cloned_suffix,
            deleted_at__isnull=True
        )
    ]

    return render(request, 'form_gallery.html', data)


def download_metadata(request, username, id_string, data_id):
    xform = get_form({
        'user__username__iexact': username,
        'id_string__iexact': id_string
    })

    owner = xform.user
    if username == request.user.username or xform.shared:
        data = get_object_or_404(MetaData, pk=data_id)
        file_path = data.data_file.name
        filename, extension = os.path.splitext(file_path.split('/')[-1])
        extension = extension.strip('.')
        dfs = get_storage_class()()
        if dfs.exists(file_path):
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Document '%(filename)s' for '%(id_string)s' downloaded.") %
                {
                    'id_string': xform.id_string,
                    'filename': "%s.%s" % (filename, extension)
                }, audit, request)
            response = response_with_mimetype_and_name(
                data.data_file_type,
                filename, extension=extension, show_date=False,
                file_path=file_path)
            return response
        else:
            return HttpResponseNotFound()

    return HttpResponseForbidden(_(u'Permission denied.'))


@login_required()
def delete_metadata(request, username, id_string, data_id):
    xform = get_form({
        'user__username__iexact': username,
        'id_string__iexact': id_string
    })

    owner = xform.user
    data = get_object_or_404(MetaData, pk=data_id)
    dfs = get_storage_class()()
    req_username = request.user.username
    if request.GET.get('del', False) and username == req_username:
        try:
            dfs.delete(data.data_file.name)
            data.delete()
            audit = {
                'xform': xform.id_string
            }
            audit_log(
                Actions.FORM_UPDATED, request.user, owner,
                _("Document '%(filename)s' deleted from '%(id_string)s'.") %
                {
                    'id_string': xform.id_string,
                    'filename': os.path.basename(data.data_file.name)
                }, audit, request)
            return HttpResponseRedirect(reverse(show, kwargs={
                'username': username,
                'id_string': id_string
            }))
        except Exception:
            return HttpResponseServerError()
    elif (request.GET.get('map_name_del', False) or
          request.GET.get('external_del', False)) and username == req_username:
        data.delete()
        audit = {
            'xform': xform.id_string
        }
        audit_log(
            Actions.FORM_UPDATED, request.user, owner,
            _("Map layer deleted from '%(id_string)s'.") %
            {
                'id_string': xform.id_string,
            }, audit, request)
        return HttpResponseRedirect(reverse(show, kwargs={
            'username': username,
            'id_string': id_string
        }))

    return HttpResponseForbidden(_(u'Permission denied.'))


def download_media_data(request, username, id_string, data_id):
    xform = get_object_or_404(
        XForm, user__username__iexact=username, deleted_at__isnull=True,
        id_string__iexact=id_string)
    owner = xform.user
    data = get_object_or_404(MetaData, id=data_id)
    dfs = get_storage_class()()
    if request.GET.get('del', False):
        if username == request.user.username:
            try:
                # ensure filename is not an empty string
                if data.data_file.name != '':
                    dfs.delete(data.data_file.name)

                data.delete()
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_UPDATED, request.user, owner,
                    _("Media download '%(filename)s' deleted from "
                      "'%(id_string)s'.") %
                    {
                        'id_string': xform.id_string,
                        'filename': os.path.basename(data.data_file.name)
                    }, audit, request)
                return HttpResponseRedirect(reverse(show, kwargs={
                    'username': username,
                    'id_string': id_string
                }))
            except Exception as e:
                return HttpResponseServerError(e)
    else:
        if username:  # == request.user.username or xform.shared:
            if data.data_file.name == '' and data.data_value is not None:
                return HttpResponseRedirect(data.data_value)

            file_path = data.data_file.name
            filename, extension = os.path.splitext(file_path.split('/')[-1])
            extension = extension.strip('.')
            if dfs.exists(file_path):
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_UPDATED, request.user, owner,
                    _("Media '%(filename)s' downloaded from '%(id_string)s'.")
                    % {
                        'id_string': xform.id_string,
                        'filename': os.path.basename(file_path)
                    }, audit, request)
                response = response_with_mimetype_and_name(
                    data.data_file_type,
                    filename, extension=extension, show_date=False,
                    file_path=file_path)
                return response
            else:
                return HttpResponseNotFound()

    return HttpResponseForbidden(_(u'Permission denied.'))


def form_photos(request, username, id_string):
    xform, owner = check_and_set_user_and_form(username, id_string, request)

    if not xform:
        return HttpResponseForbidden(_(u'Not shared.'))

    data = {}
    data['form_view'] = True
    data['content_user'] = owner
    data['xform'] = xform
    image_urls = []

    for instance in xform.instances.filter(deleted_at__isnull=True):
        for attachment in instance.attachments.all():
            # skip if not image e.g video or file
            if not attachment.mimetype.startswith('image'):
                continue

            data = {}

            for i in [u'small', u'medium', u'large', u'original']:
                url = reverse(attachment_url, kwargs={'size': i})
                url = '%s?media_file=%s' % (url, attachment.media_file.name)
                data[i] = url

            image_urls.append(data)

    image_urls = json.dumps(image_urls)

    data['images'] = image_urls
    data['profile'], created = UserProfile.objects.get_or_create(user=owner)

    return render(request, 'form_photos.html', data)


@require_POST
def set_perm(request, username, id_string):
    xform = get_form({
        'user__username__iexact': username,
        'id_string__iexact': id_string
    })

    owner = xform.user
    if username != request.user.username\
            and not has_permission(xform, username, request):
        return HttpResponseForbidden(_(u'Permission denied.'))

    try:
        perm_type = request.POST['perm_type']
        for_user = request.POST['for_user']
    except KeyError:
        return HttpResponseBadRequest()

    if perm_type in ['edit', 'view', 'report', 'remove']:
        try:
            user = User.objects.get(username=for_user)
        except User.DoesNotExist:
            messages.add_message(
                request, messages.INFO,
                _(u"Wrong username <b>%s</b>." % for_user),
                extra_tags='alert-error')
        else:
            if perm_type == 'edit' and\
                    not user.has_perm('change_xform', xform):
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_PERMISSIONS_UPDATED, request.user, owner,
                    _("Edit permissions on '%(id_string)s' assigned to "
                      "'%(for_user)s'.") %
                    {
                        'id_string': xform.id_string,
                        'for_user': for_user
                    }, audit, request)
                assign_perm('change_xform', user, xform)
            elif perm_type == 'view' and\
                    not user.has_perm('view_xform', xform):
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_PERMISSIONS_UPDATED, request.user, owner,
                    _("View permissions on '%(id_string)s' "
                      "assigned to '%(for_user)s'.") %
                    {
                        'id_string': xform.id_string,
                        'for_user': for_user
                    }, audit, request)
                assign_perm('view_xform', user, xform)
            elif perm_type == 'report' and\
                    not user.has_perm('report_xform', xform):
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_PERMISSIONS_UPDATED, request.user, owner,
                    _("Report permissions on '%(id_string)s' "
                      "assigned to '%(for_user)s'.") %
                    {
                        'id_string': xform.id_string,
                        'for_user': for_user
                    }, audit, request)
                assign_perm('report_xform', user, xform)
            elif perm_type == 'remove':
                audit = {
                    'xform': xform.id_string
                }
                audit_log(
                    Actions.FORM_PERMISSIONS_UPDATED, request.user, owner,
                    _("All permissions on '%(id_string)s' "
                      "removed from '%(for_user)s'.") %
                    {
                        'id_string': xform.id_string,
                        'for_user': for_user
                    }, audit, request)
                remove_perm('change_xform', user, xform)
                remove_perm('view_xform', user, xform)
                remove_perm('report_xform', user, xform)
    elif perm_type == 'link':
        current = MetaData.public_link(xform)
        if for_user == 'all':
            MetaData.public_link(xform, True)
        elif for_user == 'none':
            MetaData.public_link(xform, False)
        elif for_user == 'toggle':
            MetaData.public_link(xform, not current)
        audit = {
            'xform': xform.id_string
        }
        audit_log(
            Actions.FORM_PERMISSIONS_UPDATED, request.user, owner,
            _("Public link on '%(id_string)s' %(action)s.") %
            {
                'id_string': xform.id_string,
                'action':
                "created" if for_user == "all" or
                (for_user == "toggle" and not current) else "removed"
            }, audit, request)

    if request.is_ajax():
        return HttpResponse(
            json.dumps(
                {'status': 'success'}), content_type='application/json')

    return HttpResponseRedirect(reverse(show, kwargs={
        'username': username,
        'id_string': id_string
    }))


@require_POST
@login_required
def delete_data(request, username=None, id_string=None):
    xform, owner = check_and_set_user_and_form(username, id_string, request)
    response_text = u''
    if not xform:
        return HttpResponseForbidden(_(u'Not shared.'))

    data_id = request.POST.get('id')
    if not data_id:
        return HttpResponseBadRequest(_(u"id must be specified"))

    Instance.set_deleted_at(data_id, user=request.user)
    audit = {
        'xform': xform.id_string
    }
    audit_log(
        Actions.SUBMISSION_DELETED, request.user, owner,
        _("Deleted submission with id '%(record_id)s' on '%(id_string)s'.") %
        {
            'id_string': xform.id_string,
            'record_id': data_id
        }, audit, request)
    response_text = json.dumps({"success": "Deleted data %s" % data_id})
    if 'callback' in request.GET and request.GET.get('callback') != '':
        callback = request.GET.get('callback')
        response_text = ("%s(%s)" % (callback, response_text))

    return HttpResponse(response_text, content_type='application/json')


@require_POST
@is_owner
def update_xform(request, username, id_string):
    xform_kwargs = {
        'id_string__iexact': id_string,
        'user__username__iexact': username
    }

    xform = get_form(xform_kwargs)
    owner = xform.user

    def set_form():
        form = QuickConverter(request.POST, request.FILES)
        survey = form.publish(request.user, id_string).survey
        enketo_webform_url = reverse(
            enter_data,
            kwargs={'username': username, 'id_string': survey.id_string}
        )
        audit = {
            'xform': xform.id_string
        }
        audit_log(
            Actions.FORM_XLS_UPDATED, request.user, owner,
            _("XLS for '%(id_string)s' updated.") %
            {
                'id_string': xform.id_string,
            }, audit, request)
        return {
            'type': 'alert-success',
            'text': _(u'Successfully published %(form_id)s.'
                      u' <a href="%(form_url)s">Enter Web Form</a>'
                      u' or <a href="#preview-modal" data-toggle="modal">'
                      u'Preview Web Form</a>')
                    % {'form_id': survey.id_string,
                       'form_url': enketo_webform_url}
        }
    message = publish_form(set_form)
    messages.add_message(
        request, messages.INFO, message['text'], extra_tags=message['type'])

    return HttpResponseRedirect(reverse(show, kwargs={
        'username': username,
        'id_string': id_string
    }))


@is_owner
def activity(request, username):
    owner = get_object_or_404(User, username=username)

    return render(request, 'activity.html', {'user': owner})


def activity_fields(request):
    fields = [
        {
            'id': 'created_on',
            'label': _('Performed On'),
            'type': 'datetime',
            'searchable': False
        },
        {
            'id': 'action',
            'label': _('Action'),
            'type': 'string',
            'searchable': True,
            'options': sorted([Actions[e] for e in Actions.enums])
        },
        {
            'id': 'user',
            'label': 'Performed By',
            'type': 'string',
            'searchable': True
        },
        {
            'id': 'msg',
            'label': 'Description',
            'type': 'string',
            'searchable': True
        },
    ]
    response_text = json.dumps(fields)

    return HttpResponse(response_text, content_type='application/json')


@is_owner
def activity_api(request, username):
    from bson.objectid import ObjectId

    def stringify_unknowns(obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.strftime(DATETIME_FORMAT)
        return None
    try:
        fields = request.GET.get('fields')
        query = request.GET.get('query')
        sort = request.GET.get('sort')
        query_args = {
            'username': username,
            'query': json.loads(query) if query else {},
            'fields': json.loads(fields) if fields else [],
            'sort': json.loads(sort) if sort else [],
        }
        if 'start' in request.GET:
            query_args["start"] = int(request.GET.get('start'))
        if 'limit' in request.GET:
            query_args["limit"] = int(request.GET.get('limit'))
        if 'count' in request.GET:
            query_args["count"] = True \
                if int(request.GET.get('count')) > 0 else False
        cursor = AuditLog.query_data(**query_args)
    except ValueError as e:
        return HttpResponseBadRequest(e.__str__())

    records = list(record for record in cursor)
    response_text = json.dumps(records, default=stringify_unknowns)
    if 'callback' in request.GET and request.GET.get('callback') != '':
        callback = request.GET.get('callback')
        response_text = ("%s(%s)" % (callback, response_text))

    return HttpResponse(response_text, content_type='application/json')


def qrcode(request, username, id_string):
    xform_kwargs = {
        'id_string__iexact': id_string,
        'user__username__iexact': username
    }

    xform = get_form(xform_kwargs)
    try:
        formhub_url = "http://%s/" % request.META['HTTP_HOST']
    except KeyError:
        formhub_url = "http://formhub.org/"
    formhub_url = formhub_url + username + '/%s' % xform.pk

    if settings.TESTING_MODE:
        formhub_url = "https://{}/{}".format(settings.TEST_HTTP_HOST,
                                             settings.TEST_USERNAME)

    results = _(u"Unexpected Error occured: No QRCODE generated")
    status = 200
    try:
        url = enketo_url(formhub_url, id_string)
    except Exception as e:
        error_msg = _(u"Error Generating QRCODE: %s" % e)
        results = """<div class="alert alert-error">%s</div>""" % error_msg
        status = 400
    else:
        if url:
            image = generate_qrcode(url)
            results = """<img class="qrcode" src="%s" alt="%s" />
                    </br><a href="%s" target="_blank">%s</a>""" \
                % (image, url, url, url)
        else:
            status = 400

    return HttpResponse(results, content_type='text/html', status=status)


def enketo_preview(request, username, id_string):
    xform = get_form({
        'user__username__iexact': username,
        'id_string__iexact': id_string
    })

    owner = xform.user
    if not has_permission(xform, owner, request, xform.shared):
        return HttpResponseForbidden(_(u'Not shared.'))

    try:
        enketo_preview_url = get_enketo_preview_url(request,
                                                    owner.username,
                                                    xform.id_string,
                                                    xform_pk=xform.pk)
    except EnketoError as e:
        return HttpResponse(e)

    return HttpResponseRedirect(enketo_preview_url)


@require_GET
@login_required
def username_list(request):
    data = []
    query = request.GET.get('query', None)
    if query:
        users = User.objects.values('username')\
            .filter(username__startswith=query, is_active=True, pk__gte=0)
        data = [user['username'] for user in users]

    return HttpResponse(json.dumps(data), content_type='application/json')


class OnaAuthorizationView(AuthorizationView):

    """
    Overrides the AuthorizationView provided by oauth2_provider
    and adds the user to the context
    """

    def get_context_data(self, **kwargs):
        context = super(OnaAuthorizationView, self).get_context_data(**kwargs)
        context['user'] = self.request.user
        context['request_path'] = self.request.get_full_path()
        return context
