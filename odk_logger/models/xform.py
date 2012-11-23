import os
import re
import json
from collections import OrderedDict

from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db.models.signals import post_save
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import ugettext_lazy, ugettext as _

from odk_logger.xform_instance_parser import XLSFormError
from common_tags import SUBMISSION_UUID
from utils.stathat_api import stathat_count
from stats.tasks import stat_log

from hashlib import md5


def upload_to(instance, filename):
    return os.path.join(
        instance.user.username,
        'xls',
        os.path.split(filename)[1])


class DuplicateUUIDError(Exception):
    pass


class XForm(models.Model):
    CLONED_SUFFIX = '_cloned'

    xls = models.FileField(upload_to=upload_to, null=True)
    json = models.TextField(default=u'')
    description = models.TextField(default=u'', null=True)
    xml = models.TextField()

    user = models.ForeignKey(User, related_name='xforms', null=True)
    shared = models.BooleanField(default=False)
    shared_data = models.BooleanField(default=False)
    downloadable = models.BooleanField(default=True)
    is_crowd_form = models.BooleanField(default=False)

    # the following fields are filled in automatically
    id_string = models.SlugField(
        editable=False, verbose_name=ugettext_lazy("ID")
    )
    title = models.CharField(editable=False, max_length=64)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    has_start_time = models.BooleanField(default=False)
    uuid = models.CharField(max_length=32, default=u'')

    uuid_regex = re.compile(r'(<instance>.*id="[^"]+">)(.*</instance>)(.*)',
                            re.DOTALL)
    instance_id_regex = re.compile(r'<instance>.*id="([^"]+)".*</instance>',
                                   re.DOTALL)
    uuid_node_location = 2
    uuid_bind_location = 4
    bamboo_dataset = models.CharField(max_length=60, default=u'')
    _bamboo_datasets = models.TextField(default=u'')
    _tmp_bamboo_datasets = None

    class Meta:
        app_label = 'odk_logger'
        unique_together = (("user", "id_string"),)
        verbose_name = ugettext_lazy("XForm")
        verbose_name_plural = ugettext_lazy("XForms")
        ordering = ("id_string",)
        permissions = (
            ("view_xform", _("Can view associated data")),
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
        from odk_viewer.models import DataDictionary
        return DataDictionary.objects.get(pk=self.pk)

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
        self.title = u"" if not matches else matches[0]

    def update(self, *args, **kwargs):
        super(XForm, self).save(*args, **kwargs)

    def save(self, *args, **kwargs):
        # serialize the bamboo datasets holder
        from odk_viewer.models import DataDictionary
        try:
            self.bamboo_datasets = self.bamboo_datasets
        except DataDictionary.DoesNotExist:
            pass

        self._set_title()
        old_id_string = self.id_string
        self._set_id_string()
        # check if we have an existing id_string, if so, the one must match but only if xform is NOT new
        if self.pk and old_id_string and old_id_string != self.id_string:
            raise XLSFormError(_(u"Your updated form's id_string '%s' must match the existing forms' id_string '%s'." %
                                 (self.id_string, old_id_string)))
        if getattr(settings, 'STRICT', True) and \
                not re.search(r"^[\w-]+$", self.id_string):
            raise XLSFormError(_(u'In strict mode, the XForm ID must be a '
                               'valid slug and contain no spaces.'))
        super(XForm, self).save(*args, **kwargs)

    def __unicode__(self):
        return getattr(self, "id_string", "")

    def submission_count(self):
        return self.surveys.filter(deleted_at=None).count()
    submission_count.short_description = ugettext_lazy("Submission Count")

    def time_of_last_submission(self):
        try:
            return self.surveys.\
                filter(deleted_at=None).latest("date_created").date_created
        except ObjectDoesNotExist:
            pass

    @property
    def hash(self):
        return u'%s' % md5(self.xml.encode('utf8')).hexdigest()

    @property
    def can_be_replaced(self):
        return self.submission_count() == 0

    def repeat_sections(self):
        return [col for col, colt in self.columns(with_repeats=True).items()
                if isinstance(colt, list)]

    def columns(self, with_repeats=False, start_at=u''):
        ''' list of columns/fields of that form.

            with_repeats: adds the repeat sections (otherwise striped)
            start_at: only display col containing it (sub fields of repeat) '''

        def _build_ordered_columns(survey_element, ordered_columns,
                                   is_repeating_section=0,
                                   start_at=None):
            """ Build a flat ordered dict of column groups """
            from pyxform.section import Section, RepeatingSection
            from pyxform.question import Question
            from utils.export_tools import question_types_to_exclude
            from utils.logger_tools import xlstype2pythontype

            # guess level (nb or inner loops) of requested columns
            start_at_level = len(start_at.split('/'))

            for child in survey_element.children:
                child_xpath = child.get_abbreviated_xpath()
                child_dict = {child_xpath: xlstype2pythontype(child.type)}

                if isinstance(child, Section):

                    if isinstance(child, RepeatingSection):

                        # repeats are marked as empty lists
                        if with_repeats:
                            ordered_columns.update({child_xpath: []})

                    _build_ordered_columns(child,
                                           ordered_columns,
                                           is_repeating_section + 1,
                                           start_at=start_at)

                elif isinstance(child, Question) and not \
                    question_types_to_exclude(child.type):

                    if not start_at and not is_repeating_section:
                        ordered_columns.update(child_dict)
                    elif start_at:
                        # if using start_at, only add sub fields
                        if (start_at and start_at in child_xpath
                            and is_repeating_section == start_at_level):
                            ordered_columns.update(child_dict)

        survey = self.data_dictionary().survey
        columns = OrderedDict()
        _build_ordered_columns(survey, columns, start_at=start_at)

        # add the submission UUID anyway as it's used on BB to join datasets
        columns = OrderedDict([(SUBMISSION_UUID, unicode)]
                              + columns.items())
        return columns

    def get_bamboo_datasets(self):
        ''' json_dict repres. the form datasets (main, repeats and joined) '''
        def init():
            ds = {"bamboo_id": None, "repeats": {}}
            for repeat in self.repeat_sections():
                ds['repeats'].update({repeat: {'bamboo_id': None,
                                               'joined_id': None}})
            return ds

        if self._tmp_bamboo_datasets is None:
            if not self._bamboo_datasets:
                self._tmp_bamboo_datasets = init()
            else:
                self._tmp_bamboo_datasets = json.loads(self._bamboo_datasets)
        return self._tmp_bamboo_datasets

    def set_bamboo_datasets(self, value):
        self._bamboo_datasets = json.dumps(value)
    bamboo_datasets = property(get_bamboo_datasets, set_bamboo_datasets)

    def sdf_schema(self, repeat=u''):
        ''' Simple Data Format Schema of the form or a given repeat '''
        from utils.logger_tools import pythontype2sdftype
        schema = {}
        for column, column_type in self.columns(start_at=repeat).items():
            stype, olap = pythontype2sdftype(column_type)
            schema[column] = {'label': column,
                              'olap_type': olap,
                              'simpletype': stype}
        return json.dumps(schema)


def stats_forms_created(sender, instance, created, **kwargs):
    if created:
        stathat_count('formhub-forms-created')
        stat_log.delay('formhub-forms-created', 1)


post_save.connect(stats_forms_created, sender=XForm)
