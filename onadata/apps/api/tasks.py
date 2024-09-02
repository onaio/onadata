# -*- coding: utf-8 -*-
"""
Celery api.tasks module.
"""
import os
import sys
import logging
from datetime import timedelta

from celery.result import AsyncResult
from django.conf import settings
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from onadata.apps.api import tools
from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.logger.models import Instance, ProjectInvitation, XForm, Project
from onadata.apps.api.tools import invalidate_organization_cache
from onadata.celeryapp import app
from onadata.libs.utils.email import send_generic_email
from onadata.libs.utils.model_tools import queryset_iterator
from onadata.libs.utils.cache_tools import (
    safe_delete,
    XFORM_REGENERATE_INSTANCE_JSON_TASK,
)
from onadata.libs.models.share_project import ShareProject
from onadata.libs.utils.email import ProjectInvitationEmail

logger = logging.getLogger(__name__)


User = get_user_model()


def recreate_tmp_file(name, path, mime_type):
    """Creates a TemporaryUploadedFile from a file path with given name"""
    tmp_file = TemporaryUploadedFile(name, mime_type, 0, None)
    # pylint: disable=consider-using-with,unspecified-encoding
    tmp_file.file = open(path)
    tmp_file.size = os.fstat(tmp_file.fileno()).st_size
    return tmp_file


@app.task(bind=True)
def publish_xlsform_async(self, user_id, post_data, owner_id, file_data):
    """Publishes an XLSForm"""
    try:
        files = MultiValueDict()
        files["xls_file"] = default_storage.open(file_data.get("path"))

        owner = User.objects.get(id=owner_id)
        if owner_id == user_id:
            user = owner
        else:
            user = User.objects.get(id=user_id)
        survey = tools.do_publish_xlsform(user, post_data, files, owner)
        default_storage.delete(file_data.get("path"))

        if isinstance(survey, XForm):
            return {"pk": survey.pk}

        return survey
    except Exception as exc:  # pylint: disable=broad-except
        if isinstance(exc, MemoryError):
            if self.request.retries < 3:
                self.retry(exc=exc, countdown=1)
            else:
                error_message = (
                    "Service temporarily unavailable, please try to "
                    "publish the form again"
                )
        else:
            error_message = str(sys.exc_info()[1])

        return {"error": error_message}


@app.task()
def delete_xform_async(xform_id, user_id):
    """Soft delete an XForm asynchrounous task"""
    xform = XForm.objects.get(pk=xform_id)
    user = User.objects.get(pk=user_id)
    xform.soft_delete(user)


@app.task()
def delete_user_async():
    """Delete inactive user accounts"""
    users = User.objects.filter(
        active=False, username__contains="deleted-at", email__contains="deleted-at"
    )
    for user in users:
        user.delete()


def get_async_status(job_uuid):
    """Gets progress status or result"""

    if not job_uuid:
        return {"error": "Empty job uuid"}

    job = AsyncResult(job_uuid)
    result = job.result or job.state
    if isinstance(result, str):
        return {"JOB_STATUS": result}

    return result


@app.task()
def send_verification_email(email, message_txt, subject):
    """
    Sends a verification email
    """
    send_generic_email(email, message_txt, subject)


@app.task()
def send_account_lockout_email(email, message_txt, subject):
    """Sends account locked email."""
    send_generic_email(email, message_txt, subject)


@app.task()
def delete_inactive_submissions():
    """
    Task to periodically delete soft deleted submissions from db
    """
    submissions_lifespan = getattr(settings, "INACTIVE_SUBMISSIONS_LIFESPAN", None)
    if submissions_lifespan:
        time_threshold = timezone.now() - timedelta(days=submissions_lifespan)
        # delete instance attachments
        instances = Instance.objects.filter(
            deleted_at__isnull=False, deleted_at__lte=time_threshold
        )
        for instance in queryset_iterator(instances):
            # delete submission
            instance.delete()


@app.task()
def send_project_invitation_email_async(
    invitation_id: str, url: str
):  # pylint: disable=invalid-name
    """Sends project invitation email asynchronously"""
    try:
        invitation = ProjectInvitation.objects.get(id=invitation_id)

    except ProjectInvitation.DoesNotExist as err:
        logger.exception(err)

    else:
        email = ProjectInvitationEmail(invitation, url)
        email.send()


@app.task(track_started=True)
def regenerate_form_instance_json(xform_id: int):
    """Regenerate a form's instances json

    Json data recreated afresh and any existing json data is overriden
    """
    try:
        xform: XForm = XForm.objects.get(pk=xform_id)
    except XForm.DoesNotExist as err:
        logger.exception(err)

    else:
        if not xform.is_instance_json_regenerated:
            instances = xform.instances.filter(deleted_at__isnull=True)

            for instance in queryset_iterator(instances):
                # We do not want to trigger Model.save or any signal
                # Queryset.update is a workaround to achieve this.
                # Instance.save and the post/pre signals may contain
                # some side-effects which we are not interested in e.g
                # updating date_modified which we do not want
                Instance.objects.filter(pk=instance.pk).update(
                    json=instance.get_full_dict()
                )

            xform.is_instance_json_regenerated = True
            xform.save()
            # Clear cache used to store the task id from the AsyncResult
            cache_key = f"{XFORM_REGENERATE_INSTANCE_JSON_TASK}{xform_id}"
            safe_delete(cache_key)


class ShareProjectBaseTask(app.Task):  # pylint: disable=too-few-public-methods
    """A Task base class for sharing a project."""

    autoretry_for = (
        DatabaseError,
        ConnectionError,
    )
    retry_backoff = 3


@app.task(base=ShareProjectBaseTask)
def add_org_user_and_share_projects_async(
    org_id: int,
    user_id: int,
    role: str = None,
    email_subject: str = None,
    email_msg: str = None,
):  # pylint: disable=invalid-name
    """Add user to organization and share projects asynchronously"""
    try:
        organization = OrganizationProfile.objects.get(pk=org_id)
        user = User.objects.get(pk=user_id)

    except OrganizationProfile.DoesNotExist as err:
        logger.exception(err)

    except User.DoesNotExist as err:
        logger.exception(err)

    else:
        tools.add_org_user_and_share_projects(organization, user, role)

        invalidate_organization_cache(organization.user.username)

        if email_msg and email_subject and user.email:
            send_mail(
                email_subject,
                email_msg,
                settings.DEFAULT_FROM_EMAIL,
                (user.email,),
            )


@app.task(base=ShareProjectBaseTask)
def remove_org_user_async(org_id, user_id):
    """Remove user from organization asynchronously"""
    try:
        organization = OrganizationProfile.objects.get(pk=org_id)
        user = User.objects.get(pk=user_id)

    except OrganizationProfile.DoesNotExist as err:
        logger.exception(err)

    except User.DoesNotExist as err:
        logger.exception(err)

    else:
        tools.remove_user_from_organization(organization, user)

        invalidate_organization_cache(organization.user.username)


@app.task(base=ShareProjectBaseTask)
def share_project_async(project_id, username, role, remove=False):
    """Share project asynchronously"""
    try:
        project = Project.objects.get(pk=project_id)

    except Project.DoesNotExist as err:
        logger.exception(err)

    else:
        share = ShareProject(project, username, role, remove)
        share.save()
