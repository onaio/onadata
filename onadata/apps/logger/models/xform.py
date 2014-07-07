from hashlib import md5
import json
import os
import re

from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db.models.signals import post_save, post_delete
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import ugettext_lazy, ugettext as _
from guardian.shortcuts import \
    assign_perm, \
    get_perms_for_model,\
    get_users_with_perms, get_perms
from taggit.managers import TaggableManager

from onadata.apps.logger.xform_instance_parser import XLSFormError
from onadata.apps.stats.tasks import stat_log
from onadata.libs.models.base_model import BaseModel


XFORM_TITLE_LENGTH = 255


def upload_to(instance, filename):
    return os.path.join(
        instance.user.username,
        'xls',
        os.path.split(filename)[1])


class DuplicateUUIDError(Exception):
    pass


class XForm(BaseModel):
    CLONED_SUFFIX = '_cloned'
    MAX_ID_LENGTH = 100

    xls = models.FileField(upload_to=upload_to, null=True)
    json = models.TextField(default=u'')
    description = models.TextField(default=u'', null=True)
    xml = models.TextField()

    user = models.ForeignKey(User, related_name='xforms', null=True)
    shared = models.BooleanField(default=False)
    shared_data = models.BooleanField(default=False)
    downloadable = models.BooleanField(default=True)
    allows_sms = models.BooleanField(default=False)
    encrypted = models.BooleanField(default=False)

    # the following fields are filled in automatically
    sms_id_string = models.SlugField(
        editable=False,
        verbose_name=ugettext_lazy("SMS ID"),
        max_length=MAX_ID_LENGTH,
        default=''
    )
    id_string = models.SlugField(
        editable=False,
        verbose_name=ugettext_lazy("ID"),
        max_length=MAX_ID_LENGTH
    )
    title = models.CharField(editable=False, max_length=XFORM_TITLE_LENGTH)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    last_submission_time = models.DateTimeField(blank=True, null=True)
    has_start_time = models.BooleanField(default=False)
    uuid = models.CharField(max_length=32, default=u'')

    uuid_regex = re.compile(r'(<instance>.*?id="[^"]+">)(.*</instance>)(.*)',
                            re.DOTALL)
    instance_id_regex = re.compile(r'<instance>.*?id="([^"]+)".*</instance>',
                                   re.DOTALL)
    uuid_node_location = 2
    uuid_bind_location = 4
    bamboo_dataset = models.CharField(max_length=60, default=u'')
    instances_with_geopoints = models.BooleanField(default=False)
    num_of_submissions = models.IntegerField(default=-1)

    tags = TaggableManager()

    class Meta:
        app_label = 'logger'
        unique_together = (("user", "id_string"), ("user", "sms_id_string"))
        verbose_name = ugettext_lazy("XForm")
        verbose_name_plural = ugettext_lazy("XForms")
        ordering = ("id_string",)
        permissions = (
            ("view_xform", _("Can view associated data")),
            ("report_xform", _("Can make submissions to the form")),
            ("move_xform", _(u"Can move form between projects")),
            ("transfer_xform", _(u"Can transfer form ownership.")),
        )

    def file_name(self):
        return self.id_string + ".xml"

    def url(self):
        return reverse(
            "download_xform",
            kwargs={
                "username": self.user.username,
                "id_string": self.id_string
            }
        )

    def data_dictionary(self):
        from onadata.apps.viewer.models.data_dictionary import\
            DataDictionary
        return DataDictionary.objects.get(pk=self.pk)

    @property
    def has_instances_with_geopoints(self):
        return self.instances_with_geopoints

    def _set_id_string(self):
        matches = self.instance_id_regex.findall(self.xml)
        if len(matches) != 1:
            raise XLSFormError(_("There should be a single id string."))
        self.id_string = matches[0]

    def _set_title(self):
        text = re.sub(r"\s+", " ", self.xml)
        matches = re.findall(r"<h:title>([^<]+)</h:title>", text)
        if len(matches) != 1:
            raise XLSFormError(_("There should be a single title."), matches)
        self.title = u"" if not matches else matches[0][:XFORM_TITLE_LENGTH]

    def _set_description(self):
        self.description = self.description \
            if self.description and self.description != '' else self.title

    def _set_encrypted_field(self):
        if self.json and self.json != '':
            json_dict = json.loads(self.json)
            if 'submission_url' in json_dict and 'public_key' in json_dict:
                self.encrypted = True
            else:
                self.encrypted = False

    def update(self, *args, **kwargs):
        super(XForm, self).save(*args, **kwargs)

    def save(self, *args, **kwargs):
        self._set_title()
        self._set_description()
        old_id_string = self.id_string
        self._set_id_string()
        self._set_encrypted_field()
        # check if we have an existing id_string,
        # if so, the one must match but only if xform is NOT new
        if self.pk and old_id_string and old_id_string != self.id_string:
            raise XLSFormError(
                _(u"Your updated form's id_string '%(new_id)s' must match "
                  "the existing forms' id_string '%(old_id)s'." %
                  {'new_id': self.id_string, 'old_id': old_id_string}))

        if getattr(settings, 'STRICT', True) and \
                not re.search(r"^[\w-]+$", self.id_string):
            raise XLSFormError(_(u'In strict mode, the XForm ID must be a '
                               'valid slug and contain no spaces.'))

        if not self.sms_id_string:
            try:
                # try to guess the form's wanted sms_id_string
                # from it's json rep (from XLSForm)
                # otherwise, use id_string to ensure uniqueness
                self.sms_id_string = json.loads(self.json).get('sms_keyword',
                                                               self.id_string)
            except:
                self.sms_id_string = self.id_string

        super(XForm, self).save(*args, **kwargs)

    def __unicode__(self):
        return getattr(self, "id_string", "")

    def submission_count(self, force_update=False):
        if self.num_of_submissions == -1 or force_update:
            count = self.instances.filter(deleted_at__isnull=True).count()
            self.num_of_submissions = count
            self.save()
        return self.num_of_submissions
    submission_count.short_description = ugettext_lazy("Submission Count")

    def geocoded_submission_count(self):
        """Number of geocoded submissions."""
        return self.instances.filter(deleted_at__isnull=True,
                                     geom__isnull=False).count()

    def time_of_last_submission(self):
        if self.last_submission_time is None and self.num_of_submissions > 0:
            try:
                last_submission = self.instances.\
                    filter(deleted_at__isnull=True).latest("date_created")
            except ObjectDoesNotExist:
                pass
            else:
                self.last_submission_time = last_submission.date_created
                self.save()
        return self.last_submission_time

    def time_of_last_submission_update(self):
        try:
            # we also consider deleted instances in this case
            return self.instances.latest("date_modified").date_modified
        except ObjectDoesNotExist:
            pass

    @property
    def hash(self):
        return u'%s' % md5(self.xml.encode('utf8')).hexdigest()

    @property
    def can_be_replaced(self):
        if hasattr(self.submission_count, '__call__'):
            num_submissions = self.submission_count()
        else:
            num_submissions = self.submission_count
        return num_submissions == 0

    @classmethod
    def public_forms(cls):
        return cls.objects.filter(shared=True)

    def get_xform_permissions(self):
        users_with_perms = []
        for user in get_users_with_perms(self):
            user_permissions = {'user': user,
                                'permissions': get_perms(user, self)}
            users_with_perms.append(user_permissions)
        return users_with_perms


def stats_forms_created(sender, instance, created, **kwargs):
    if created:
        stat_log.delay('formhub-forms-created', 1)

post_save.connect(stats_forms_created, sender=XForm)


def update_profile_num_submissions(sender, instance, **kwargs):
    profile_qs = User.profile.get_query_set()
    try:
        profile = profile_qs.select_for_update()\
            .get(pk=instance.user.profile.pk)
    except ObjectDoesNotExist:
        pass
    else:
        profile.num_of_submissions -= instance.num_of_submissions
        if profile.num_of_submissions < 0:
            profile.num_of_submissions = 0
        profile.save()

post_delete.connect(update_profile_num_submissions, sender=XForm,
                    dispatch_uid='update_profile_num_submissions')


def set_object_permissions(sender, instance=None, created=False, **kwargs):
    if created:
        for perm in get_perms_for_model(XForm):
            assign_perm(perm.codename, instance.user, instance)
post_save.connect(set_object_permissions, sender=XForm,
                  dispatch_uid='xform_object_permissions')
