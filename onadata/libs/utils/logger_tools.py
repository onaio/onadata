from datetime import date, datetime
import os
import pytz
import re
import tempfile
import traceback
from xml.dom import Node
from xml.parsers.expat import ExpatError

from dict2xml import dict2xml
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.storage import get_storage_class
from django.core.mail import mail_admins
from django.core.servers.basehttp import FileWrapper
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseNotFound, \
    StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils.encoding import DjangoUnicodeDecodeError
from django.utils.translation import ugettext as _
from django.utils import timezone
from modilabs.utils.subprocess_timeout import ProcessTimedOut
from pyxform.errors import PyXFormError
from pyxform.xform2json import create_survey_element_from_xml
import sys

from onadata.apps.logger.models import Attachment
from onadata.apps.logger.models import Instance
from onadata.apps.logger.models.instance import (
    FormInactiveError,
    InstanceHistory,
    get_id_string_from_xml_str)
from onadata.apps.logger.models import XForm
from onadata.apps.logger.models.xform import XLSFormError
from onadata.apps.logger.xform_instance_parser import (
    InstanceEmptyError,
    InstanceInvalidUserError,
    InstanceMultipleNodeError,
    DuplicateInstance,
    clean_and_parse_xml,
    get_uuid_from_xml,
    get_deprecated_uuid_from_xml,
    get_submission_date_from_xml)
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.apps.viewer.models.parsed_instance import ParsedInstance
from onadata.libs.utils.model_tools import set_uuid
from onadata.libs.utils.user_auth import get_user_default_project


OPEN_ROSA_VERSION_HEADER = 'X-OpenRosa-Version'
HTTP_OPEN_ROSA_VERSION_HEADER = 'HTTP_X_OPENROSA_VERSION'
OPEN_ROSA_VERSION = '1.0'
DEFAULT_CONTENT_TYPE = 'text/xml; charset=utf-8'
DEFAULT_CONTENT_LENGTH = settings.DEFAULT_CONTENT_LENGTH

uuid_regex = re.compile(r'<formhub>\s*<uuid>\s*([^<]+)\s*</uuid>\s*</formhub>',
                        re.DOTALL)


def _get_instance(xml, new_uuid, submitted_by, status, xform):
    # check if its an edit submission
    old_uuid = get_deprecated_uuid_from_xml(xml)
    instances = Instance.objects.filter(uuid=old_uuid)

    if instances:
        # edits
        check_edit_submission_permissions(submitted_by, xform)
        instance = instances[0]
        InstanceHistory.objects.create(
            xml=instance.xml, xform_instance=instance, uuid=old_uuid)
        instance.xml = xml
        instance.uuid = new_uuid
        instance.json = instance.get_dict()
        instance.save()
    else:
        # new submission
        instance = Instance.objects.create(
            xml=xml, user=submitted_by, status=status, xform=xform)

    return instance


def dict2xform(jsform, form_id):
    return u"<?xml version='1.0' ?><{0} id='{0}'>{1}</{0}>".format(
        form_id, dict2xml(jsform))


def get_uuid_from_submission(xml):
    # parse UUID from uploaded XML
    split_xml = uuid_regex.split(xml)

    # check that xml has UUID
    return len(split_xml) > 1 and split_xml[1] or None


def get_xform_from_submission(xml, username, uuid=None):
    # check alternative form submission ids
    uuid = uuid or get_uuid_from_submission(xml)

    if not username and not uuid:
        raise InstanceInvalidUserError()

    if uuid:
        # try find the form by its uuid which is the ideal condition
        if XForm.objects.filter(uuid=uuid).count() > 0:
            xform = XForm.objects.get(uuid=uuid)

            return xform

    id_string = get_id_string_from_xml_str(xml)

    return get_object_or_404(XForm, id_string__iexact=id_string,
                             user__username=username)


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
                      'form_title': xform.title}))


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
                  'form_title': xform.title}))


def save_attachments(xform, instance, media_files):
    for f in media_files:
        filename, extension = os.path.splitext(f.name)
        extension = extension.replace('.', '')
        content_type = u'text/xml' \
            if extension == Attachment.OSM else f.content_type
        if extension == Attachment.OSM and not xform.instances_with_osm:
            xform.instances_with_osm = True
            xform.save()

        Attachment.objects.get_or_create(
            instance=instance, media_file=f, mimetype=content_type,
            extension=extension
        )


def save_submission(xform, xml, media_files, new_uuid, submitted_by, status,
                    date_created_override):
    if not date_created_override:
        date_created_override = get_submission_date_from_xml(xml)

    instance = _get_instance(xml, new_uuid, submitted_by, status, xform)
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
        pi, created = ParsedInstance.objects.get_or_create(
            instance=instance)

    if not created:
        pi.save(async=False)

    return instance


def create_instance(username, xml_file, media_files,
                    status=u'submitted_via_web', uuid=None,
                    date_created_override=None, request=None):
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

    existing_instance_count = Instance.objects.filter(
        xml=xml, xform__user=xform.user).count()

    if existing_instance_count > 0:
        existing_instance = Instance.objects.filter(
            xml=xml, xform__user=xform.user)[0]
        if not existing_instance.xform or\
                existing_instance.xform.has_start_time:
            # ensure we have saved the extra attachments
            save_attachments(xform, existing_instance, media_files)
            existing_instance.save()
            transaction.commit()

            # Ignore submission as a duplicate IFF
            #  * a submission's XForm collects start time
            #  * the submitted XML is an exact match with one that
            #    has already been submitted for that user.
            return DuplicateInstance()

    # get new and depracated uuid's
    new_uuid = get_uuid_from_xml(xml)
    duplicate_instances = Instance.objects.filter(uuid=new_uuid)

    if duplicate_instances:
        # ensure we have saved the extra attachments
        with transaction.atomic():
            save_attachments(xform, duplicate_instances[0], media_files)
            duplicate_instances[0].save()

        return DuplicateInstance()

    instance = save_submission(xform, xml, media_files, new_uuid,
                               submitted_by, status, date_created_override)
    return instance


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
            _(u"Received empty submission. No instance was created")
        )
    except FormInactiveError:
        error = OpenRosaResponseNotAllowed(_(u"Form is not active"))
    except XForm.DoesNotExist:
        error = OpenRosaResponseNotFound(
            _(u"Form does not exist on this account")
        )
    except ExpatError:
        error = OpenRosaResponseBadRequest(_(u"Improperly formatted XML."))
    except DuplicateInstance:
        response = OpenRosaResponse(_(u"Duplicate submission"))
        response.status_code = 202
        response['Location'] = request.build_absolute_uri(request.path)
        error = response
    except PermissionDenied as e:
        error = OpenRosaResponseForbidden(e)
    except InstanceMultipleNodeError as e:
        error = OpenRosaResponseBadRequest(e)
    except DjangoUnicodeDecodeError:
        error = OpenRosaResponseBadRequest(_(u"File likely corrupted during "
                                             u"transmission, please try later."
                                             ))
    if isinstance(instance, DuplicateInstance):
        response = OpenRosaResponse(_(u"Duplicate submission"))
        response.status_code = 202
        response['Location'] = request.build_absolute_uri(request.path)
        error = response
        instance = None

    return [error, instance]


def report_exception(subject, info, exc_info=None):
    # Add hostname to subject mail

    subject = "{0} - {1}".format(subject, settings.HOSTNAME)
    if exc_info:
        cls, err = exc_info[:2]
        message = _(u"Exception in request:"
                    u" %(class)s: %(error)s")\
            % {'class': cls.__name__, 'error': err}
        message += u"".join(traceback.format_exception(*exc_info))
    else:
        message = u"%s" % info

    if settings.DEBUG or settings.TESTING_MODE:
        sys.stdout.write("Subject: %s\n" % subject)
        sys.stdout.write("Message: %s\n" % message)
    else:
        mail_admins(subject=subject, message=message)


def response_with_mimetype_and_name(
        mimetype, name, extension=None, show_date=True, file_path=None,
        use_local_filesystem=False, full_mime=False):
    if extension is None:
        extension = mimetype
    if not full_mime:
        mimetype = "application/%s" % mimetype
    if file_path:
        try:
            if not use_local_filesystem:
                default_storage = get_storage_class()()
                wrapper = FileWrapper(default_storage.open(file_path))
                response = StreamingHttpResponse(wrapper,
                                                 content_type=mimetype)
                response['Content-Length'] = default_storage.size(file_path)
            else:
                wrapper = FileWrapper(open(file_path))
                response = StreamingHttpResponse(wrapper,
                                                 content_type=mimetype)
                response['Content-Length'] = os.path.getsize(file_path)
        except IOError:
            response = HttpResponseNotFound(
                _(u"The requested file could not be found."))
    else:
        response = HttpResponse(content_type=mimetype)
    response['Content-Disposition'] = disposition_ext_and_date(
        name, extension, show_date)
    return response


def disposition_ext_and_date(name, extension, show_date=True):
    if name is None:
        return 'attachment;'
    if show_date:
        name = "%s_%s" % (name, date.today().strftime("%Y_%m_%d"))
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
    try:
        return callback()
    except (PyXFormError, XLSFormError) as e:
        msg = unicode(e)

        if 'invalid xml tag' in msg:
            msg = _(u"Invalid file name; Names must begin with a letter, "
                    u"colon, or underscore, subsequent characters can include"
                    u" numbers, dashes,periods and with no spacing.")
        return {
            'type': 'alert-error',
            'text': msg
        }
    except IntegrityError as e:
        transaction.rollback()
        return {
            'type': 'alert-error',
            'text': _(u'Form with this id or SMS-keyword already exists.'),
        }
    except ValidationError as e:
        # on clone invalid URL
        return {
            'type': 'alert-error',
            'text': _(u'Invalid URL format.'),
        }
    except AttributeError as e:
        # form.publish returned None, not sure why...

        return {
            'type': 'alert-error',
            'text': unicode(e)
        }
    except ProcessTimedOut as e:
        # catch timeout errors
        return {
            'type': 'alert-error',
            'text': _(u'Form validation timeout, please try again.'),
        }
    except Exception as e:
        transaction.rollback()
        # error in the XLS file; show an error to the user

        return {
            'type': 'alert-error',
            'text': unicode(e)
        }


def publish_xls_form(xls_file, user, project, id_string=None, created_by=None):
    """ Creates or updates a DataDictionary with supplied xls_file,
        user and optional id_string - if updating
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
            project=project
        )


def publish_xml_form(xml_file, user, project, id_string=None, created_by=None):
    xml = xml_file.read()
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
        dd.save()

        return dd
    else:
        created_by = created_by or user
        dd = DataDictionary(created_by=created_by, user=user, xml=xml,
                            json=form_json, project=project)
        dd._mark_start_time_boolean()
        set_uuid(dd)
        dd._set_uuid_in_xml(file_name=xml_file.name)
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
            if n.nodeType == Node.ELEMENT_NODE and
            n.tagName.lower() == "meta"]
        if len(meta_tags) == 0:
            meta_tag = xml.createElement("meta")
            xml.documentElement.appendChild(meta_tag)
        else:
            meta_tag = meta_tags[0]

        # check if we have an instanceID tag
        uuid_tags = [
            n for n in meta_tag.childNodes
            if n.nodeType == Node.ELEMENT_NODE and n.tagName == "instanceID"]
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
