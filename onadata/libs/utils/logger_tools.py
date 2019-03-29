import os
import re
import sys
import tempfile
from builtins import str as text
from datetime import datetime
from wsgiref.util import FileWrapper
from xml.dom import Node
from xml.parsers.expat import ExpatError

import pytz
from dict2xml import dict2xml
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import (MultipleObjectsReturned, PermissionDenied,
                                    ValidationError)
from django.core.files.storage import get_storage_class
from django.db import IntegrityError, transaction, DataError
from django.db.models import Q
from django.http import (HttpResponse, HttpResponseNotFound,
                         StreamingHttpResponse, UnreadablePostError)
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import DjangoUnicodeDecodeError
from django.utils.translation import ugettext as _
from hashlib import sha256
from modilabs.utils.subprocess_timeout import ProcessTimedOut
from multidb.pinning import use_master

from onadata.apps.logger.models import Attachment, Instance, XForm
from onadata.apps.logger.models.instance import (
    FormInactiveError, InstanceHistory, FormIsMergedDatasetError,
    get_id_string_from_xml_str)
from onadata.apps.logger.models.xform import XLSFormError
from onadata.apps.logger.xform_instance_parser import (
    DuplicateInstance, InstanceEmptyError, InstanceInvalidUserError,
    InstanceMultipleNodeError, NonUniqueFormIdError, clean_and_parse_xml,
    get_deprecated_uuid_from_xml, get_submission_date_from_xml,
    get_uuid_from_xml)
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.apps.viewer.models.parsed_instance import ParsedInstance
from onadata.apps.viewer.signals import process_submission
from onadata.libs.utils.common_tools import report_exception
from onadata.libs.utils.model_tools import set_uuid
from onadata.libs.utils.user_auth import get_user_default_project
from pyxform.errors import PyXFormError
from pyxform.xform2json import create_survey_element_from_xml

OPEN_ROSA_VERSION_HEADER = 'X-OpenRosa-Version'
HTTP_OPEN_ROSA_VERSION_HEADER = 'HTTP_X_OPENROSA_VERSION'
OPEN_ROSA_VERSION = '1.0'
DEFAULT_CONTENT_TYPE = 'text/xml; charset=utf-8'
DEFAULT_CONTENT_LENGTH = settings.DEFAULT_CONTENT_LENGTH

uuid_regex = re.compile(r'<formhub>\s*<uuid>\s*([^<]+)\s*</uuid>\s*</formhub>',
                        re.DOTALL)


def _get_instance(xml, new_uuid, submitted_by, status, xform, checksum):
    history = None
    instance = None
    # check if its an edit submission
    old_uuid = get_deprecated_uuid_from_xml(xml)
    if old_uuid:
        instance = Instance.objects.filter(uuid=old_uuid,
                                           xform_id=xform.pk).first()
        history = InstanceHistory.objects.filter(
            xform_instance__xform_id=xform.pk,
            uuid=new_uuid).only('xform_instance').first()

        if instance:
            # edits
            check_edit_submission_permissions(submitted_by, xform)

            last_edited = timezone.now()
            InstanceHistory.objects.create(
                checksum=instance.checksum,
                xml=instance.xml,
                xform_instance=instance,
                uuid=old_uuid,
                user=submitted_by,
                geom=instance.geom,
                submission_date=instance.last_edited or instance.date_created)
            instance.xml = xml
            instance.last_edited = last_edited
            instance.uuid = new_uuid
            instance.checksum = checksum
            instance.save()

            # call webhooks
            process_submission.send(sender=instance.__class__,
                                    instance=instance)
        elif history:
            instance = history.xform_instance
    if old_uuid is None or (instance is None and history is None):
        # new submission
        instance = Instance.objects.create(
            xml=xml, user=submitted_by, status=status, xform=xform,
            checksum=checksum)
    return instance


def dict2xform(jsform, form_id, root=None):
    if not root:
        root = form_id
    return u"<?xml version='1.0' ?><{0} id='{1}'>{2}</{0}>".format(
        root, form_id, dict2xml(jsform))


def get_first_record(queryset):
    """
    Returns the first item in a queryset sorted by id.
    """
    records = sorted([record for record in queryset], key=lambda k: k.id)
    if records:
        return records[0]

    return None


def get_uuid_from_submission(xml):
    # parse UUID from uploaded XML
    split_xml = uuid_regex.split(xml.decode('utf-8'))

    # check that xml has UUID
    return len(split_xml) > 1 and split_xml[1] or None


def get_xform_from_submission(xml, username, uuid=None):
    # check alternative form submission ids
    uuid = uuid or get_uuid_from_submission(xml)

    if not username and not uuid:
        raise InstanceInvalidUserError()

    if uuid:
        # try find the form by its uuid which is the ideal condition
        if XForm.objects.filter(
                uuid=uuid, deleted_at__isnull=True).count() > 0:
            xform = XForm.objects.get(uuid=uuid, deleted_at__isnull=True)

            return xform

    id_string = get_id_string_from_xml_str(xml)

    try:
        return get_object_or_404(
            XForm,
            id_string__iexact=id_string,
            user__username=username,
            deleted_at__isnull=True)
    except MultipleObjectsReturned:
        raise NonUniqueFormIdError()


def _has_edit_xform_permission(xform, user):
    if isinstance(xform, XForm) and isinstance(user, User):
        return user.has_perm('logger.change_xform', xform)

    return False


def check_edit_submission_permissions(request_user, xform):
    if xform and request_user and request_user.is_authenticated():
        requires_auth = xform.user.profile.require_auth
        has_edit_perms = _has_edit_xform_permission(xform, request_user)

        if requires_auth and not has_edit_perms:
            raise PermissionDenied(
                _(u"%(request_user)s is not allowed to make edit submissions "
                  u"to %(form_user)s's %(form_title)s form." % {
                      'request_user': request_user,
                      'form_user': xform.user,
                      'form_title': xform.title
                  }))


def check_submission_permissions(request, xform):
    """Check that permission is required and the request user has permission.

    The user does no have permissions iff:
        * the user is authed,
        * either the profile or the form require auth,
        * the xform user is not submitting.

    Since we have a username, the Instance creation logic will
    handle checking for the forms existence by its id_string.

    :returns: None.
    :raises: PermissionDenied based on the above criteria.
    """
    if request and (xform.user.profile.require_auth or xform.require_auth or
                    request.path == '/submission')\
            and xform.user != request.user\
            and not request.user.has_perm('report_xform', xform):
        raise PermissionDenied(
            _(u"%(request_user)s is not allowed to make submissions "
              u"to %(form_user)s's %(form_title)s form." % {
                  'request_user': request.user,
                  'form_user': xform.user,
                  'form_title': xform.title
              }))


def update_attachment_tracking(instance):
    """
    Takes an Instance object and updates attachment tracking fields
    """
    instance.total_media = instance.num_of_media
    instance.media_count = instance.attachments_count
    instance.media_all_received = instance.media_count == instance.total_media
    instance.save(update_fields=['total_media', 'media_count',
                                 'media_all_received', 'json'])


def save_attachments(xform, instance, media_files):
    """
    Saves attachments for the given instance/submission.
    """
    # upload_path = os.path.join(instance.xform.user.username, 'attachments')

    for f in media_files:
        filename, extension = os.path.splitext(f.name)
        extension = extension.replace('.', '')
        content_type = u'text/xml' \
            if extension == Attachment.OSM else f.content_type
        if extension == Attachment.OSM and not xform.instances_with_osm:
            xform.instances_with_osm = True
            xform.save()
        filename = os.path.basename(f.name)
        media_in_submission = (
            filename in instance.get_expected_media() or
            instance.xml.decode('utf-8').find(filename) != -1)
        if media_in_submission:
            Attachment.objects.get_or_create(
                instance=instance,
                media_file=f,
                mimetype=content_type,
                name=filename,
                extension=extension)
    update_attachment_tracking(instance)


def save_submission(xform, xml, media_files, new_uuid, submitted_by, status,
                    date_created_override, checksum):
    if not date_created_override:
        date_created_override = get_submission_date_from_xml(xml)

    instance = _get_instance(xml, new_uuid, submitted_by, status, xform,
                             checksum)
    save_attachments(xform, instance, media_files)

    # override date created if required
    if date_created_override:
        if not timezone.is_aware(date_created_override):
            # default to utc?
            date_created_override = timezone.make_aware(
                date_created_override, timezone.utc)
        instance.date_created = date_created_override
        instance.save()

    if instance.xform is not None:
        instance.save()
        pi, created = ParsedInstance.objects.get_or_create(instance=instance)
        if not created:
            pi.save(async=False)

    return instance


def get_filtered_instances(*args, **kwargs):
    """Get filtered instances - mainly to allow mocking in tests"""

    return Instance.objects.filter(*args, **kwargs)


def create_instance(username,
                    xml_file,
                    media_files,
                    status=u'submitted_via_web',
                    uuid=None,
                    date_created_override=None,
                    request=None):
    """
    I used to check if this file had been submitted already, I've
    taken this out because it was too slow. Now we're going to create
    a way for an admin to mark duplicate instances. This should
    simplify things a bit.
    Submission cases:
    * If there is a username and no uuid, submitting an old ODK form.
    * If there is a username and a uuid, submitting a new ODK form.
    """
    instance = None
    submitted_by = request.user \
        if request and request.user.is_authenticated() else None

    if username:
        username = username.lower()

    xml = xml_file.read()
    xform = get_xform_from_submission(xml, username, uuid)
    check_submission_permissions(request, xform)
    checksum = sha256(xml).hexdigest()

    new_uuid = get_uuid_from_xml(xml)
    filtered_instances = get_filtered_instances(
        Q(checksum=checksum) | Q(uuid=new_uuid), xform_id=xform.pk)
    existing_instance = get_first_record(filtered_instances.only('id'))
    if existing_instance and \
            (new_uuid or existing_instance.xform.has_start_time):
        # ensure we have saved the extra attachments
        with transaction.atomic():
            save_attachments(xform, existing_instance, media_files)
            existing_instance.save(update_fields=['json', 'date_modified'])

        # Ignore submission as a duplicate IFF
        #  * a submission's XForm collects start time
        #  * the submitted XML is an exact match with one that
        #    has already been submitted for that user.
        return DuplicateInstance()

    # get new and deprecated UUIDs
    history = InstanceHistory.objects.filter(
        xform_instance__xform_id=xform.pk,
        xform_instance__deleted_at__isnull=True,
        uuid=new_uuid).only('xform_instance').first()

    if history:
        duplicate_instance = history.xform_instance
        # ensure we have saved the extra attachments
        with transaction.atomic():
            save_attachments(xform, duplicate_instance, media_files)
            duplicate_instance.save()

        return DuplicateInstance()

    try:
        with transaction.atomic():
            instance = save_submission(xform, xml, media_files, new_uuid,
                                       submitted_by, status,
                                       date_created_override, checksum)
    except IntegrityError:
        instance = get_first_record(Instance.objects.filter(
            Q(checksum=checksum) | Q(uuid=new_uuid),
            xform_id=xform.pk))

        if instance:
            attachment_names = [
                a.media_file.name.split('/')[-1]
                for a in Attachment.objects.filter(instance=instance)
            ]
            media_files = [f for f in media_files
                           if f.name not in attachment_names]
            save_attachments(xform, instance, media_files)
            instance.save()

        instance = DuplicateInstance()
    return instance


@use_master
def safe_create_instance(username, xml_file, media_files, uuid, request):
    """Create an instance and catch exceptions.

    :returns: A list [error, instance] where error is None if there was no
        error.
    """
    error = instance = None

    try:
        instance = create_instance(
            username, xml_file, media_files, uuid=uuid, request=request)
    except InstanceInvalidUserError:
        error = OpenRosaResponseBadRequest(_(u"Username or ID required."))
    except InstanceEmptyError:
        error = OpenRosaResponseBadRequest(
            _(u"Received empty submission. No instance was created"))
    except (FormInactiveError, FormIsMergedDatasetError) as e:
        error = OpenRosaResponseNotAllowed(text(e))
    except XForm.DoesNotExist:
        error = OpenRosaResponseNotFound(
            _(u"Form does not exist on this account"))
    except ExpatError:
        error = OpenRosaResponseBadRequest(_(u"Improperly formatted XML."))
    except DuplicateInstance:
        response = OpenRosaResponse(_(u"Duplicate submission"))
        response.status_code = 202
        if request:
            response['Location'] = request.build_absolute_uri(request.path)
        error = response
    except PermissionDenied as e:
        error = OpenRosaResponseForbidden(e)
    except UnreadablePostError as e:
        error = OpenRosaResponseBadRequest(
            _(u"Unable to read submitted file: %(error)s"
              % {'error': text(e)}))
    except InstanceMultipleNodeError as e:
        error = OpenRosaResponseBadRequest(e)
    except DjangoUnicodeDecodeError:
        error = OpenRosaResponseBadRequest(
            _(u"File likely corrupted during "
              u"transmission, please try later."))
    except NonUniqueFormIdError as e:
        error = OpenRosaResponseBadRequest(
            _(u"Unable to submit because there are multiple forms with"
              u" this formID."))
    except DataError as e:
        error = OpenRosaResponseBadRequest((str(e)))
    if isinstance(instance, DuplicateInstance):
        response = OpenRosaResponse(_(u"Duplicate submission"))
        response.status_code = 202
        if request:
            response['Location'] = request.build_absolute_uri(request.path)
        error = response
        instance = None
    return [error, instance]


def response_with_mimetype_and_name(mimetype,
                                    name,
                                    extension=None,
                                    show_date=True,
                                    file_path=None,
                                    use_local_filesystem=False,
                                    full_mime=False):
    if extension is None:
        extension = mimetype
    if not full_mime:
        mimetype = "application/%s" % mimetype
    if file_path:
        try:
            if not use_local_filesystem:
                default_storage = get_storage_class()()
                wrapper = FileWrapper(default_storage.open(file_path))
                response = StreamingHttpResponse(
                    wrapper, content_type=mimetype)
                response['Content-Length'] = default_storage.size(file_path)
            else:
                wrapper = FileWrapper(open(file_path))
                response = StreamingHttpResponse(
                    wrapper, content_type=mimetype)
                response['Content-Length'] = os.path.getsize(file_path)
        except IOError:
            response = HttpResponseNotFound(
                _(u"The requested file could not be found."))
    else:
        response = HttpResponse(content_type=mimetype)
    response['Content-Disposition'] = generate_content_disposition_header(
        name, extension, show_date)
    return response


def generate_content_disposition_header(name, extension, show_date=True):
    if name is None:
        return 'attachment;'
    if show_date:
        name = "%s-%s" % (name, datetime.now().strftime("%Y-%m-%d-%H-%M-%S"))
    return 'attachment; filename=%s.%s' % (name, extension)


def store_temp_file(data):
    tmp = tempfile.TemporaryFile()
    ret = None
    try:
        tmp.write(data)
        tmp.seek(0)
        ret = tmp
    finally:
        tmp.close()
    return ret


def publish_form(callback):
    """
    Calls the callback function to publish a XLSForm and returns appropriate
    message depending on exception throw during publishing of a XLSForm.
    """
    try:
        return callback()
    except (PyXFormError, XLSFormError) as e:
        return {'type': 'alert-error', 'text': text(e)}
    except IntegrityError as e:
        return {
            'type': 'alert-error',
            'text': _(u'Form with this id or SMS-keyword already exists.'),
        }
    except ProcessTimedOut as e:
        # catch timeout errors
        return {
            'type': 'alert-error',
            'text': _(u'Form validation timeout, please try again.'),
        }
    except (MemoryError, OSError) as e:
        return {
            'type': 'alert-error',
            'text': _((u'An error occurred while publishing the form. '
                       'Please try again.')),
        }
    except (AttributeError, Exception, ValidationError) as e:
        report_exception("Form publishing exception: {}".format(e), text(e),
                         sys.exc_info())
        return {'type': 'alert-error', 'text': text(e)}


@transaction.atomic()
def publish_xls_form(xls_file, user, project, id_string=None, created_by=None):
    """Create or update DataDictionary with xls_file, user
    id_string is optional when updating
    """
    # get or create DataDictionary based on user and id string
    if id_string:
        dd = DataDictionary.objects.get(
            user=user, id_string=id_string, project=project)
        dd.xls = xls_file
        dd.save()

        return dd
    else:
        return DataDictionary.objects.create(
            created_by=created_by or user,
            user=user,
            xls=xls_file,
            project=project)


def publish_xml_form(xml_file, user, project, id_string=None, created_by=None):
    xml = xml_file.read()
    if isinstance(xml, bytes):
        xml = xml.decode('utf-8')
    survey = create_survey_element_from_xml(xml)
    form_json = survey.to_json()
    if id_string:
        dd = DataDictionary.objects.get(
            user=user, id_string=id_string, project=project)
        dd.xml = xml
        dd.json = form_json
        dd._mark_start_time_boolean()
        set_uuid(dd)
        dd._set_uuid_in_xml()
        dd._set_hash()
        dd.save()

        return dd
    else:
        created_by = created_by or user
        dd = DataDictionary(
            created_by=created_by,
            user=user,
            xml=xml,
            json=form_json,
            project=project)
        dd._mark_start_time_boolean()
        set_uuid(dd)
        dd._set_uuid_in_xml(file_name=xml_file.name)
        dd._set_hash()
        dd.save()

        return dd


class BaseOpenRosaResponse(HttpResponse):
    status_code = 201

    def __init__(self, *args, **kwargs):
        super(BaseOpenRosaResponse, self).__init__(*args, **kwargs)

        self[OPEN_ROSA_VERSION_HEADER] = OPEN_ROSA_VERSION
        tz = pytz.timezone(settings.TIME_ZONE)
        dt = datetime.now(tz).strftime('%a, %d %b %Y %H:%M:%S %Z')
        self['Date'] = dt
        self['X-OpenRosa-Accept-Content-Length'] = DEFAULT_CONTENT_LENGTH
        self['Content-Type'] = DEFAULT_CONTENT_TYPE


class OpenRosaResponse(BaseOpenRosaResponse):
    status_code = 201

    def __init__(self, *args, **kwargs):
        super(OpenRosaResponse, self).__init__(*args, **kwargs)
        self.message = self.content
        # wrap content around xml
        self.content = '''<?xml version='1.0' encoding='UTF-8' ?>
<OpenRosaResponse xmlns="http://openrosa.org/http/response">
        <message nature="">%s</message>
</OpenRosaResponse>''' % self.content


class OpenRosaResponseNotFound(OpenRosaResponse):
    status_code = 404


class OpenRosaResponseBadRequest(OpenRosaResponse):
    status_code = 400


class OpenRosaResponseNotAllowed(OpenRosaResponse):
    status_code = 405


class OpenRosaResponseForbidden(OpenRosaResponse):
    status_code = 403


def inject_instanceid(xml_str, uuid):
    if get_uuid_from_xml(xml_str) is None:
        xml = clean_and_parse_xml(xml_str)
        children = xml.childNodes
        if children.length == 0:
            raise ValueError(_("XML string must have a survey element."))

        # check if we have a meta tag
        survey_node = children.item(0)
        meta_tags = [
            n for n in survey_node.childNodes
            if n.nodeType == Node.ELEMENT_NODE and n.tagName.lower() == "meta"
        ]
        if len(meta_tags) == 0:
            meta_tag = xml.createElement("meta")
            xml.documentElement.appendChild(meta_tag)
        else:
            meta_tag = meta_tags[0]

        # check if we have an instanceID tag
        uuid_tags = [
            n for n in meta_tag.childNodes
            if n.nodeType == Node.ELEMENT_NODE and n.tagName == "instanceID"
        ]
        if len(uuid_tags) == 0:
            uuid_tag = xml.createElement("instanceID")
            meta_tag.appendChild(uuid_tag)
        else:
            uuid_tag = uuid_tags[0]
        # insert meta and instanceID
        text_node = xml.createTextNode(u"uuid:%s" % uuid)
        uuid_tag.appendChild(text_node)
        return xml.toxml()
    return xml_str


def remove_xform(xform):
    # delete xform, and all related models
    xform.delete()


class PublishXForm(object):
    def __init__(self, xml_file, user):
        self.xml_file = xml_file
        self.user = user
        self.project = get_user_default_project(user)

    def publish_xform(self):
        return publish_xml_form(self.xml_file, self.user, self.project)
