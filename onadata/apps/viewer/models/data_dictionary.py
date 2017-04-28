import csv
import io
import os
import xlrd
from django.utils import timezone

from cStringIO import StringIO
from django.db.models.signals import post_save, pre_save
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils.translation import ugettext as _
from pyxform.builder import create_survey_element_from_dict
from pyxform.utils import has_external_choices
from pyxform.xls2json import parse_file_to_json

from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.xform_instance_parser import XLSFormError
from onadata.libs.utils.model_tools import set_uuid
from onadata.libs.utils.cache_tools import (
    PROJ_FORMS_CACHE, PROJ_BASE_FORMS_CACHE, safe_delete)
from onadata.libs.utils.model_tools import get_columns_with_hxl


# adopted from pyxform.utils.sheet_to_csv
def sheet_to_csv(xls_content, sheet_name):
    """Writes a csv file of a specified sheet from a an excel file

    :param xls_content: Excel file contents
    :param sheet_name: the name of the excel sheet to generate the csv file

    :returns: a (StrionIO) csv file object
    """
    wb = xlrd.open_workbook(file_contents=xls_content)

    try:
        sheet = wb.sheet_by_name(sheet_name)
    except xlrd.biffh.XLRDError:
        return False

    if not sheet or sheet.nrows < 2:
        return False

    csv_file = StringIO()

    writer = csv.writer(csv_file, quoting=csv.QUOTE_ALL)
    mask = [v and len(v.strip()) > 0 for v in sheet.row_values(0)]

    for r in range(sheet.nrows):
        writer.writerow([v for v, m in zip(sheet.row_values(r), mask) if m])

    return csv_file


def upload_to(instance, filename, username=None):
    if instance:
        username = instance.xform.user.username
    return os.path.join(
        username,
        'xls',
        os.path.split(filename)[1]
    )


class DataDictionary(XForm):

    def __init__(self, *args, **kwargs):
        self.instances_for_export = lambda d: d.instances.all()
        super(DataDictionary, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        skip_xls_read = kwargs.get('skip_xls_read')

        if self.xls and not skip_xls_read:
            default_name = None \
                if not self.pk else self.survey.xml_instance().tagName
            try:
                if self.xls.name.endswith('csv'):
                    # csv file gets closed in pyxform, make a copy
                    self.xls.seek(0)
                    file_object = io.BytesIO()
                    file_object.write(self.xls.read())
                    file_object.seek(0)
                    self.xls.seek(0)
                else:
                    file_object = self.xls
                survey_dict = parse_file_to_json(
                    self.xls.name, default_name=default_name,
                    file_object=file_object)
            except csv.Error as e:
                newline_error = u'new-line character seen in unquoted field '\
                    u'- do you need to open the file in universal-newline '\
                    u'mode?'
                if newline_error == unicode(e):
                    self.xls.seek(0)
                    file_obj = StringIO(
                        u'\n'.join(self.xls.read().splitlines()))
                    survey_dict = parse_file_to_json(
                        self.xls.name, default_name=default_name,
                        file_object=file_obj)
                else:
                    raise e
            if has_external_choices(survey_dict):
                self.survey_dict = survey_dict
                self.has_external_choices = True
            survey = create_survey_element_from_dict(survey_dict)
            survey = self._check_version_set(survey)
            if get_columns_with_hxl(survey.get('children')):
                self.has_hxl_support = True
            # if form is being replaced, don't check for id_string uniqueness
            if self.pk is None:
                new_id_string = self.get_unique_id_string(
                    survey.get('id_string'))
                self._id_string_changed = \
                    new_id_string != survey.get('id_string')
                survey['id_string'] = new_id_string
            elif self.id_string != survey.get('id_string'):
                raise XLSFormError(_(
                    (u"Your updated form's id_string '%(new_id)s' must match "
                     "the existing forms' id_string '%(old_id)s', if form has "
                     "submissions." % {'new_id': survey.get('id_string'),
                                       'old_id': self.id_string})))
            else:
                survey['id_string'] = self.id_string
            self.json = survey.to_json()
            self.xml = survey.to_xml()
            self.version = survey.get('version')
            self.last_updated_at = timezone.now()
            self.title = survey.get('title')
            self._mark_start_time_boolean()
            set_uuid(self)
            self._set_uuid_in_xml()

        if 'skip_xls_read' in kwargs:
            del kwargs['skip_xls_read']

        super(DataDictionary, self).save(*args, **kwargs)

    def file_name(self):
        return os.path.split(self.xls.name)[-1]


def set_object_permissions(sender, instance=None, created=False, **kwargs):
    if instance.project:
        # clear cache
        safe_delete('{}{}'.format(PROJ_FORMS_CACHE, instance.project.pk))
        safe_delete('{}{}'.format(PROJ_BASE_FORMS_CACHE, instance.project.pk))

    # seems the super is not called, have to get xform from here
    xform = XForm.objects.get(pk=instance.pk)

    if created:
        from onadata.libs.permissions import OwnerRole

        OwnerRole.add(instance.user, xform)

        if instance.created_by and instance.user != instance.created_by:
            OwnerRole.add(instance.created_by, xform)

        from onadata.libs.utils.project_utils import set_project_perms_to_xform_async  # noqa
        set_project_perms_to_xform_async.delay(xform.pk, instance.project.pk)

    if hasattr(instance, 'has_external_choices') \
            and instance.has_external_choices:
        instance.xls.seek(0)
        f = sheet_to_csv(instance.xls.read(), 'external_choices')
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(0)

        from onadata.apps.main.models.meta_data import MetaData
        data_file = InMemoryUploadedFile(
            file=f,
            field_name='data_file',
            name='itemsets.csv',
            content_type='text/csv',
            size=size,
            charset=None
        )

        MetaData.media_upload(xform, data_file)


post_save.connect(set_object_permissions, sender=DataDictionary,
                  dispatch_uid='xform_object_permissions')


def save_project(sender, instance=None, created=False, **kwargs):
    instance.project.save()


pre_save.connect(save_project, sender=DataDictionary,
                 dispatch_uid='save_project_datadictionary')
