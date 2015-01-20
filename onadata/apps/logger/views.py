from datetime import datetime
import json
import os
import tempfile

import pytz

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.contrib import messages
from django.core.exceptions import MultipleObjectsReturned
from django.core.files.storage import get_storage_class
from django.core.files import File
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseBadRequest, \
    HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.template import loader
from django.template import RequestContext
from django.utils import six
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django_digest import HttpDigestAuthenticator

from onadata.apps.main.models import UserProfile, MetaData
from onadata.apps.logger.import_tools import import_instances_from_zip
from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.ziggy_instance import ZiggyInstance
from onadata.libs.utils.log import audit_log, Actions
from onadata.libs.utils.viewer_tools import enketo_url
from onadata.libs.utils.logger_tools import (
    safe_create_instance,
    OpenRosaResponseBadRequest,
    OpenRosaResponse,
    BaseOpenRosaResponse,
    PublishXForm,
    inject_instanceid,
    remove_xform,
    publish_form)
from onadata.libs.utils.logger_tools import response_with_mimetype_and_name
from onadata.libs.utils.decorators import is_owner
from onadata.libs.utils.user_auth import helper_auth_helper, has_permission,\
    has_edit_permission, HttpResponseNotAuthorized, add_cors_headers

from onadata.libs.utils.viewer_tools import _get_form_url


IO_ERROR_STRINGS = [
    'request data read error',
    'error during read(65536) on wsgi.input'
]


def _bad_request(e):
    strerror = unicode(e)

    return strerror and strerror in IO_ERROR_STRINGS


def _extract_uuid(text):
    text = text[text.find("@key="):-1].replace("@key=", "")
    if text.startswith("uuid:"):
        text = text.replace("uuid:", "")
    return text


def _parse_int(num):
    try:
        return num and int(num)
    except ValueError:
        pass


def _html_submission_response(request, instance):
    data = {}
    data['username'] = instance.xform.user.username
    data['id_string'] = instance.xform.id_string
    data['domain'] = Site.objects.get(id=settings.SITE_ID).domain

    return render(request, "submission.html", data)


def _submission_response(request, instance):
    data = {}
    data['message'] = _("Successful submission.")
    data['formid'] = instance.xform.id_string
    data['encrypted'] = instance.xform.encrypted
    data['instanceID'] = u'uuid:%s' % instance.uuid
    data['submissionDate'] = instance.date_created.isoformat()
    data['markedAsCompleteDate'] = instance.date_modified.isoformat()

    context = RequestContext(request, data)
    t = loader.get_template('submission.xml')

    return BaseOpenRosaResponse(t.render(context))


@require_POST
@csrf_exempt
def bulksubmission(request, username):
    # puts it in a temp directory.
    # runs "import_tools(temp_directory)"
    # deletes
    posting_user = get_object_or_404(User, username__iexact=username)

    # request.FILES is a django.utils.datastructures.MultiValueDict
    # for each key we have a list of values
    try:
        temp_postfile = request.FILES.pop("zip_submission_file", [])
    except IOError:
        return HttpResponseBadRequest(_(u"There was a problem receiving your "
                                        u"ODK submission. [Error: IO Error "
                                        u"reading data]"))
    if len(temp_postfile) != 1:
        return HttpResponseBadRequest(_(u"There was a problem receiving your"
                                        u" ODK submission. [Error: multiple "
                                        u"submission files (?)]"))

    postfile = temp_postfile[0]
    tempdir = tempfile.gettempdir()
    our_tfpath = os.path.join(tempdir, postfile.name)

    with open(our_tfpath, 'wb') as f:
        f.write(postfile.read())

    with open(our_tfpath, 'rb') as f:
        total_count, success_count, errors = import_instances_from_zip(
            f, posting_user)
    # chose the try approach as suggested by the link below
    # http://stackoverflow.com/questions/82831
    try:
        os.remove(our_tfpath)
    except IOError:
        # TODO: log this Exception somewhere
        pass
    json_msg = {
        'message': _(u"Submission complete. Out of %(total)d "
                     u"survey instances, %(success)d were imported, "
                     u"(%(rejected)d were rejected as duplicates, "
                     u"missing forms, etc.)") %
        {'total': total_count, 'success': success_count,
         'rejected': total_count - success_count},
        'errors': u"%d %s" % (len(errors), errors)
    }
    audit = {
        "bulk_submission_log": json_msg
    }
    audit_log(Actions.USER_BULK_SUBMISSION, request.user, posting_user,
              _("Made bulk submissions."), audit, request)
    response = HttpResponse(json.dumps(json_msg))
    response.status_code = 200
    response['Location'] = request.build_absolute_uri(request.path)
    return response


@login_required
def bulksubmission_form(request, username=None):
    username = username if username is None else username.lower()
    if request.user.username == username:
        return render(request, 'bulk_submission_form.html')
    else:
        return HttpResponseRedirect('/%s' % request.user.username)


@require_GET
def formList(request, username):
    """
    This is where ODK Collect gets its download list.
    """
    formlist_user = get_object_or_404(User, username__iexact=username)
    profile, created = UserProfile.objects.get_or_create(user=formlist_user)

    if profile.require_auth:
        authenticator = HttpDigestAuthenticator()
        if not authenticator.authenticate(request):
            return authenticator.build_challenge_response()

        # unauthorized if user in auth request does not match user in path
        # unauthorized if user not active
        if not request.user.is_active:
            return HttpResponseNotAuthorized()

    # filter private forms (where require_auth=False)
    # for users who are non-owner
    if request.user.username == profile.user.username:
        xforms = XForm.objects.filter(downloadable=True,
                                      user__username__iexact=username)
    else:
        xforms = XForm.objects.filter(downloadable=True,
                                      user__username__iexact=username,
                                      require_auth=False)

    audit = {}
    audit_log(Actions.USER_FORMLIST_REQUESTED, request.user, formlist_user,
              _("Requested forms list."), audit, request)

    data = {
        'host': request.build_absolute_uri().replace(
            request.get_full_path(), ''),
        'xforms': xforms
    }
    response = render(request, "xformsList.xml", data,
                      content_type="text/xml; charset=utf-8")
    response['X-OpenRosa-Version'] = '1.0'
    tz = pytz.timezone(settings.TIME_ZONE)
    dt = datetime.now(tz).strftime('%a, %d %b %Y %H:%M:%S %Z')
    response['Date'] = dt

    return response


@require_GET
def xformsManifest(request, username, id_string):
    xform = get_object_or_404(
        XForm, id_string__iexact=id_string, user__username__iexact=username)
    formlist_user = xform.user
    profile, created = \
        UserProfile.objects.get_or_create(user=formlist_user)

    if profile.require_auth:
        authenticator = HttpDigestAuthenticator()
        if not authenticator.authenticate(request):
            return authenticator.build_challenge_response()

    response = render(request, "xformsManifest.xml", {
        'host': request.build_absolute_uri().replace(
            request.get_full_path(), ''),
        'media_files': MetaData.media_upload(xform, download=True)
    }, content_type="text/xml; charset=utf-8")
    response['X-OpenRosa-Version'] = '1.0'
    tz = pytz.timezone(settings.TIME_ZONE)
    dt = datetime.now(tz).strftime('%a, %d %b %Y %H:%M:%S %Z')
    response['Date'] = dt

    return response


@require_http_methods(["HEAD", "POST"])
@csrf_exempt
def submission(request, username=None):
    if username:
        formlist_user = get_object_or_404(User, username__iexact=username)
        profile, created = UserProfile.objects.get_or_create(
            user=formlist_user)

        if profile.require_auth:
            authenticator = HttpDigestAuthenticator()
            if not authenticator.authenticate(request):
                return authenticator.build_challenge_response()

    if request.method == 'HEAD':
        response = OpenRosaResponse(status=204)
        if username:
            response['Location'] = request.build_absolute_uri().replace(
                request.get_full_path(), '/%s/submission' % username)
        else:
            response['Location'] = request.build_absolute_uri().replace(
                request.get_full_path(), '/submission')
        return response

    xml_file_list = []
    media_files = []

    # request.FILES is a django.utils.datastructures.MultiValueDict
    # for each key we have a list of values
    try:
        xml_file_list = request.FILES.pop("xml_submission_file", [])
        if len(xml_file_list) != 1:
            return OpenRosaResponseBadRequest(
                _(u"There should be a single XML submission file.")
            )
        # save this XML file and media files as attachments
        media_files = request.FILES.values()

        # get uuid from post request
        uuid = request.POST.get('uuid')

        error, instance = safe_create_instance(
            username, xml_file_list[0], media_files, uuid, request)

        if error:
            return error
        elif instance is None:
            return OpenRosaResponseBadRequest(
                _(u"Unable to create submission."))

        audit = {
            "xform": instance.xform.id_string
        }
        audit_log(
            Actions.SUBMISSION_CREATED, request.user, instance.xform.user,
            _("Created submission on form %(id_string)s.") %
            {
                "id_string": instance.xform.id_string
            }, audit, request)

        # response as html if posting with a UUID
        if not username and uuid:
            response = _html_submission_response(request, instance)
        else:
            response = _submission_response(request, instance)

        # ODK needs two things for a form to be considered successful
        # 1) the status code needs to be 201 (created)
        # 2) The location header needs to be set to the host it posted to
        response.status_code = 201
        response['Location'] = request.build_absolute_uri(request.path)
        return response
    except IOError as e:
        if _bad_request(e):
            return OpenRosaResponseBadRequest(
                _(u"File transfer interruption."))
        else:
            raise
    finally:
        if len(xml_file_list):
            [_file.close() for _file in xml_file_list]
        if len(media_files):
            [_file.close() for _file in media_files]


def download_xform(request, username, id_string):
    user = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm,
                              user=user, id_string__iexact=id_string)
    profile, created =\
        UserProfile.objects.get_or_create(user=user)

    if profile.require_auth:
        authenticator = HttpDigestAuthenticator()
        if not authenticator.authenticate(request):
            return authenticator.build_challenge_response()
    audit = {
        "xform": xform.id_string
    }
    audit_log(
        Actions.FORM_XML_DOWNLOADED, request.user, xform.user,
        _("Downloaded XML for form '%(id_string)s'.") %
        {
            "id_string": xform.id_string
        }, audit, request)
    response = response_with_mimetype_and_name('xml', id_string,
                                               show_date=False)
    response.content = xform.xml
    return response


def download_xlsform(request, username, id_string):
    xform = get_object_or_404(XForm,
                              user__username__iexact=username,
                              id_string__iexact=id_string)
    owner = User.objects.get(username__iexact=username)
    helper_auth_helper(request)

    if not has_permission(xform, owner, request, xform.shared):
        return HttpResponseForbidden('Not shared.')

    file_path = xform.xls.name
    default_storage = get_storage_class()()

    if file_path != '' and default_storage.exists(file_path):
        audit = {
            "xform": xform.id_string
        }
        audit_log(
            Actions.FORM_XLS_DOWNLOADED, request.user, xform.user,
            _("Downloaded XLS file for form '%(id_string)s'.") %
            {
                "id_string": xform.id_string
            }, audit, request)
        split_path = file_path.split(os.extsep)
        extension = 'xls'

        if len(split_path) > 1:
            extension = split_path[len(split_path) - 1]

        response = response_with_mimetype_and_name(
            'vnd.ms-excel', id_string, show_date=False, extension=extension,
            file_path=file_path)

        return response

    else:
        messages.add_message(request, messages.WARNING,
                             _(u'No XLS file for your form '
                               u'<strong>%(id)s</strong>')
                             % {'id': id_string})

        return HttpResponseRedirect("/%s" % username)


def download_jsonform(request, username, id_string):
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm, user__username__iexact=username,
                              id_string__iexact=id_string)
    if request.method == "OPTIONS":
        response = HttpResponse()
        add_cors_headers(response)
        return response
    helper_auth_helper(request)
    if not has_permission(xform, owner, request, xform.shared):
        response = HttpResponseForbidden(_(u'Not shared.'))
        add_cors_headers(response)
        return response
    response = response_with_mimetype_and_name('json', id_string,
                                               show_date=False)
    if 'callback' in request.GET and request.GET.get('callback') != '':
        callback = request.GET.get('callback')
        response.content = "%s(%s)" % (callback, xform.json)
    else:
        add_cors_headers(response)
        response.content = xform.json
    return response


@is_owner
@require_POST
def delete_xform(request, username, id_string):
    try:
        xform = get_object_or_404(XForm, user__username__iexact=username,
                                  id_string__iexact=id_string)
    except MultipleObjectsReturned:
        return HttpResponse("You account has multiple forms with same formid")

    # delete xform and submissions
    remove_xform(xform)

    audit = {}
    audit_log(
        Actions.FORM_DELETED, request.user, xform.user,
        _("Deleted form '%(id_string)s'.") %
        {
            'id_string': xform.id_string,
        }, audit, request)
    return HttpResponseRedirect('/')


@is_owner
def toggle_downloadable(request, username, id_string):
    xform = XForm.objects.get(user__username__iexact=username,
                              id_string__iexact=id_string)
    xform.downloadable = not xform.downloadable
    xform.save()
    audit = {}
    audit_log(
        Actions.FORM_UPDATED, request.user, xform.user,
        _("Made form '%(id_string)s' %(downloadable)s.") %
        {
            'id_string': xform.id_string,
            'downloadable':
            _("downloadable") if xform.downloadable else _("un-downloadable")
        }, audit, request)
    return HttpResponseRedirect("/%s" % username)


def enter_data(request, username, id_string):
    owner = get_object_or_404(User, username__iexact=username)
    xform = get_object_or_404(XForm, user__username__iexact=username,
                              id_string__iexact=id_string)
    if not has_edit_permission(xform, owner, request, xform.shared):
        return HttpResponseForbidden(_(u'Not shared.'))

    form_url = _get_form_url(request, username, settings.ENKETO_PROTOCOL)

    try:
        url = enketo_url(form_url, xform.id_string)
        if not url:
            return HttpResponseRedirect(reverse(
                'onadata.apps.main.views.show',
                kwargs={'username': username, 'id_string': id_string}))
        return HttpResponseRedirect(url)
    except Exception as e:
        data = {}
        owner = User.objects.get(username__iexact=username)
        data['profile'], created = \
            UserProfile.objects.get_or_create(user=owner)
        data['xform'] = xform
        data['content_user'] = owner
        data['form_view'] = True
        data['message'] = {
            'type': 'alert-error',
            'text': u"Enketo error, reason: %s" % e}
        messages.add_message(
            request, messages.WARNING,
            _("Enketo error: enketo replied %s") % e, fail_silently=True)
        return render(request, "profile.html", data)

    return HttpResponseRedirect(reverse('onadata.apps.main.views.show',
                                        kwargs={'username': username,
                                                'id_string': id_string}))


def edit_data(request, username, id_string, data_id):
    context = RequestContext(request)
    owner = User.objects.get(username__iexact=username)
    xform = get_object_or_404(
        XForm, user__username__iexact=username, id_string__iexact=id_string)
    instance = get_object_or_404(
        Instance, pk=data_id, xform=xform)
    if not has_edit_permission(xform, owner, request, xform.shared):
        return HttpResponseForbidden(_(u'Not shared.'))
    if not hasattr(settings, 'ENKETO_URL'):
        return HttpResponseRedirect(reverse(
            'onadata.apps.main.views.show',
            kwargs={'username': username, 'id_string': id_string}))

    url = '%sdata/edit_url' % settings.ENKETO_URL
    # see commit 220f2dad0e for tmp file creation
    injected_xml = inject_instanceid(instance.xml, instance.uuid)
    return_url = request.build_absolute_uri(
        reverse(
            'onadata.apps.viewer.views.instance',
            kwargs={
                'username': username,
                'id_string': id_string}
        ) + "#/" + str(instance.id))
    form_url = _get_form_url(request, username, settings.ENKETO_PROTOCOL)

    try:
        url = enketo_url(
            form_url, xform.id_string, instance_xml=injected_xml,
            instance_id=instance.uuid, return_url=return_url
        )
    except Exception as e:
        context.message = {
            'type': 'alert-error',
            'text': u"Enketo error, reason: %s" % e}
        messages.add_message(
            request, messages.WARNING,
            _("Enketo error: enketo replied %s") % e, fail_silently=True)
    else:
        if url:
            context.enketo = url
            return HttpResponseRedirect(url)
    return HttpResponseRedirect(
        reverse('onadata.apps.main.views.show',
                kwargs={'username': username,
                        'id_string': id_string}))


def view_submission_list(request, username):
    form_user = get_object_or_404(User, username__iexact=username)
    profile, created = \
        UserProfile.objects.get_or_create(user=form_user)
    authenticator = HttpDigestAuthenticator()
    if not authenticator.authenticate(request):
        return authenticator.build_challenge_response()
    id_string = request.GET.get('formId', None)
    xform = get_object_or_404(
        XForm, id_string__iexact=id_string, user__username__iexact=username)
    if not has_permission(xform, form_user, request, xform.shared_data):
        return HttpResponseForbidden('Not shared.')
    num_entries = request.GET.get('numEntries', None)
    cursor = request.GET.get('cursor', None)
    instances = xform.instances.filter(deleted_at=None).order_by('pk')

    cursor = _parse_int(cursor)
    if cursor:
        instances = instances.filter(pk__gt=cursor)

    num_entries = _parse_int(num_entries)
    if num_entries:
        instances = instances[:num_entries]

    data = {'instances': instances}

    resumptionCursor = 0
    if instances.count():
        last_instance = instances[instances.count() - 1]
        resumptionCursor = last_instance.pk
    elif instances.count() == 0 and cursor:
        resumptionCursor = cursor

    data['resumptionCursor'] = resumptionCursor

    return render(
        request, 'submissionList.xml', data,
        content_type="text/xml; charset=utf-8")


def view_download_submission(request, username):
    form_user = get_object_or_404(User, username__iexact=username)
    profile, created = \
        UserProfile.objects.get_or_create(user=form_user)
    authenticator = HttpDigestAuthenticator()
    if not authenticator.authenticate(request):
        return authenticator.build_challenge_response()
    data = {}
    formId = request.GET.get('formId', None)
    if not isinstance(formId, six.string_types):
        return HttpResponseBadRequest()

    id_string = formId[0:formId.find('[')]
    form_id_parts = formId.split('/')
    if form_id_parts.__len__() < 2:
        return HttpResponseBadRequest()

    uuid = _extract_uuid(form_id_parts[1])
    instance = get_object_or_404(
        Instance, xform__id_string__iexact=id_string, uuid=uuid,
        xform__user__username=username, deleted_at=None)
    xform = instance.xform
    if not has_permission(xform, form_user, request, xform.shared_data):
        return HttpResponseForbidden('Not shared.')
    submission_xml_root_node = instance.get_root_node()
    submission_xml_root_node.setAttribute(
        'instanceID', u'uuid:%s' % instance.uuid)
    submission_xml_root_node.setAttribute(
        'submissionDate', instance.date_created.isoformat()
    )
    data['submission_data'] = submission_xml_root_node.toxml()
    data['media_files'] = Attachment.objects.filter(instance=instance)
    data['host'] = request.build_absolute_uri().replace(
        request.get_full_path(), '')

    return render(
        request, 'downloadSubmission.xml', data,
        content_type="text/xml; charset=utf-8")


@require_http_methods(["HEAD", "POST"])
@csrf_exempt
def form_upload(request, username):
    form_user = get_object_or_404(User, username__iexact=username)
    profile, created = \
        UserProfile.objects.get_or_create(user=form_user)
    authenticator = HttpDigestAuthenticator()
    if not authenticator.authenticate(request):
        return authenticator.build_challenge_response()
    if form_user != request.user:
        return HttpResponseForbidden(
            _(u"Not allowed to upload form[s] to %(user)s account." %
              {'user': form_user}))
    if request.method == 'HEAD':
        response = OpenRosaResponse(status=204)
        response['Location'] = request.build_absolute_uri().replace(
            request.get_full_path(), '/%s/formUpload' % form_user.username)
        return response
    xform_def = request.FILES.get('form_def_file', None)
    content = u""
    if isinstance(xform_def, File):
        do_form_upload = PublishXForm(xform_def, form_user)
        dd = publish_form(do_form_upload.publish_xform)
        status = 201
        if isinstance(dd, XForm):
            content = _(u"%s successfully published." % dd.id_string)
        else:
            content = dd['text']
            if isinstance(content, Exception):
                content = content.message
                status = 500
            else:
                status = 400
    return OpenRosaResponse(content, status=status)


@csrf_exempt
def ziggy_submissions(request, username):
    """
    Accepts ziggy JSON submissions.
        - stored in mongo, ziggy_instances
        - ZiggyInstance Django Model
    Copy form_instance - to create actual Instances for a specific form?
    """
    data = {'message': _(u"Invalid request!")}
    status = 400
    form_user = get_object_or_404(User, username__iexact=username)
    if request.method == 'POST':
        json_post = request.body
        if json_post:
            # save submission
            # i.e pick entity_id, instance_id, server_version, client_version?
            # reporter_id
            records = ZiggyInstance.create_ziggy_instances(
                form_user, json_post)

            data = {'status': 'success',
                    'message': _(u"Successfully processed %(records)s records"
                                 % {'records': records})}
            status = 201
    else:
        # get clientVersion and reportId
        reporter_id = request.GET.get('reporter-id', None)
        client_version = request.GET.get('timestamp', 0)
        if reporter_id is not None and client_version is not None:
            try:
                cursor = ZiggyInstance.get_current_list(
                    reporter_id, client_version)
            except ValueError as e:
                status = 400
                data = {'message': '%s' % e}
            else:
                status = 200
                data = [record for record in cursor]
    return HttpResponse(json.dumps(data), status=status)
