from datetime import datetime

from django.contrib.gis.db import models
from django.db.models.signals import post_save, pre_save, post_delete
from django.contrib.auth.models import User
from django.contrib.gis.geos import GeometryCollection, Point
from django.core.urlresolvers import reverse
from django.utils import timezone
from django.utils.translation import ugettext as _
from jsonfield import JSONField
from taggit.managers import TaggableManager

from onadata.apps.logger.models.survey_type import SurveyType
from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.xform import XFORM_TITLE_LENGTH
from onadata.apps.logger.xform_instance_parser import XFormInstanceParser,\
    clean_and_parse_xml, get_uuid_from_xml
from onadata.libs.utils.common_tags import ATTACHMENTS, BAMBOO_DATASET_ID,\
    DELETEDAT, GEOLOCATION, ID, MONGO_STRFTIME, NOTES, SUBMISSION_TIME, TAGS,\
    UUID, XFORM_ID_STRING, SUBMITTED_BY, VERSION, STATUS, DURATION, START, END
from onadata.libs.utils.model_tools import set_uuid
from onadata.libs.data.query import get_numeric_fields
from onadata.libs.utils.cache_tools import safe_delete
from onadata.libs.utils.cache_tools import IS_ORG
from onadata.libs.utils.cache_tools import PROJ_SUB_DATE_CACHE
from onadata.libs.utils.cache_tools import PROJ_NUM_DATASET_CACHE,\
    XFORM_DATA_VERSIONS, DATAVIEW_COUNT, XFORM_DATA
from onadata.libs.utils.timing import calculate_duration


def get_attachment_url(attachment, suffix=None):
    kwargs = {'pk': attachment.pk}
    url = u'{}?filename={}'.format(
        reverse('files-detail', kwargs=kwargs),
        attachment.media_file.name
    )
    if suffix:
        url += u'&suffix={}'.format(suffix)

    return url


def _get_attachments_from_instance(instance):
    attachments = []
    for a in instance.attachments.all():
        attachment = dict()
        attachment['download_url'] = get_attachment_url(a)
        attachment['small_download_url'] = get_attachment_url(a, 'small')
        attachment['medium_download_url'] = get_attachment_url(a, 'medium')
        attachment['mimetype'] = a.mimetype
        attachment['filename'] = a.media_file.name
        attachment['instance'] = a.instance.pk
        attachment['xform'] = instance.xform.id
        attachment['id'] = a.id
        attachments.append(attachment)

    return attachments


def _get_tag_or_element_type_xpath(dd, tag):
    elems = dd.get_survey_elements_of_type(tag)
    return elems[0].get_abbreviated_xpath() if elems else tag


class FormInactiveError(Exception):

    def __unicode__(self):
        return _("Form is inactive")

    def __str__(self):
        return unicode(self).encode('utf-8')


def numeric_checker(string_value):
    if string_value.isdigit():
        return int(string_value)
    else:
        try:
            return float(string_value)
        except ValueError:
            pass


# need to establish id_string of the xform before we run get_dict since
# we now rely on data dictionary to parse the xml


def get_id_string_from_xml_str(xml_str):
    xml_obj = clean_and_parse_xml(xml_str)
    root_node = xml_obj.documentElement
    id_string = root_node.getAttribute(u"id")

    if len(id_string) == 0:
        # may be hidden in submission/data/id_string
        elems = root_node.getElementsByTagName('data')

        for data in elems:
            for child in data.childNodes:
                id_string = data.childNodes[0].getAttribute('id')

                if len(id_string) > 0:
                    break

            if len(id_string) > 0:
                break

    return id_string


def submission_time():
    return timezone.now()


def update_xform_submission_count(sender, instance, created, **kwargs):
    if created:
        xform = XForm.objects.select_related().select_for_update()\
            .get(pk=instance.xform.pk)
        xform.num_of_submissions += 1
        xform.last_submission_time = instance.date_created
        xform.save()
        profile_qs = User.profile.get_query_set()
        try:
            profile = profile_qs.select_for_update()\
                .get(pk=xform.user.profile.pk)
        except profile_qs.model.DoesNotExist:
            pass
        else:
            profile.num_of_submissions += 1
            profile.save()

        safe_delete('{}{}'.format(XFORM_DATA_VERSIONS, xform.pk))
        safe_delete('{}{}'.format(DATAVIEW_COUNT, xform.pk))

    # Delete this for update, delete and create actions
    safe_delete(('{}{}'.format(XFORM_DATA, instance.xform.pk)))


def update_xform_submission_count_delete(sender, instance, **kwargs):
    try:
        xform = XForm.objects.select_for_update().get(pk=instance.xform.pk)
    except XForm.DoesNotExist:
        pass
    else:
        xform.num_of_submissions -= 1
        if xform.num_of_submissions < 0:
            xform.num_of_submissions = 0
        xform.save()
        profile_qs = User.profile.get_query_set()
        try:
            profile = profile_qs.select_for_update()\
                .get(pk=xform.user.profile.pk)
        except profile_qs.model.DoesNotExist:
            pass
        else:
            profile.num_of_submissions -= 1
            if profile.num_of_submissions < 0:
                profile.num_of_submissions = 0
            profile.save()

        for a in [PROJ_NUM_DATASET_CACHE, PROJ_SUB_DATE_CACHE]:
            safe_delete('{}{}'.format(a, xform.project.pk))

        safe_delete('{}{}'.format(IS_ORG, xform.pk))
        safe_delete('{}{}'.format(XFORM_DATA_VERSIONS, xform.pk))
        safe_delete('{}{}'.format(DATAVIEW_COUNT, xform.pk))
        safe_delete(('{}{}'.format(XFORM_DATA, xform.pk)))

        if xform.instances.exclude(geom=None).count() < 1:
            xform.instances_with_geopoints = False
            xform.save()


class Instance(models.Model):
    json = JSONField(default={}, null=False)
    xml = models.TextField()
    user = models.ForeignKey(User, related_name='instances', null=True)
    xform = models.ForeignKey(XForm, null=True, related_name='instances')
    survey_type = models.ForeignKey(SurveyType)

    # shows when we first received this instance
    date_created = models.DateTimeField(auto_now_add=True)

    # this will end up representing "date last parsed"
    date_modified = models.DateTimeField(auto_now=True)

    # this will end up representing "date instance was deleted"
    deleted_at = models.DateTimeField(null=True, default=None)

    # ODK keeps track of three statuses for an instance:
    # incomplete, submitted, complete
    # we add a fourth status: submitted_via_web
    status = models.CharField(max_length=20,
                              default=u'submitted_via_web')
    uuid = models.CharField(max_length=249, default=u'')
    version = models.CharField(max_length=XFORM_TITLE_LENGTH, null=True)

    # store an geographic objects associated with this instance
    geom = models.GeometryCollectionField(null=True)
    objects = models.GeoManager()

    tags = TaggableManager()

    class Meta:
        app_label = 'logger'

    @classmethod
    def set_deleted_at(cls, instance_id, deleted_at=timezone.now()):
        try:
            instance = cls.objects.get(id=instance_id)
        except cls.DoesNotExist:
            pass
        else:
            instance.set_deleted(deleted_at)

    def numeric_converter(self, json_dict, numeric_fields=None):
        if numeric_fields is None:
            numeric_fields = get_numeric_fields(self.xform)
        for key, value in json_dict.items():
            if isinstance(value, basestring) and key in numeric_fields:
                converted_value = numeric_checker(value)
                if converted_value:
                    json_dict[key] = converted_value
            elif isinstance(value, dict):
                json_dict[key] = self.numeric_converter(
                    value, numeric_fields)
            elif isinstance(value, list):
                for k, v in enumerate(value):
                    if isinstance(v, basestring) and key in numeric_fields:
                        converted_value = numeric_checker(v)
                        if converted_value:
                            json_dict[key] = converted_value
                    elif isinstance(v, dict):
                        value[k] = self.numeric_converter(
                            v, numeric_fields)
        return json_dict

    def _check_active(self, force):
        """Check that form is active and raise exception if not.

        :param force: Ignore restrictions on saving.
        """
        if not force and self.xform and not self.xform.downloadable:
            raise FormInactiveError()

    def _set_geom(self):
        xform = self.xform
        data_dictionary = xform.data_dictionary()
        geo_xpaths = data_dictionary.geopoint_xpaths()
        doc = self.get_dict()
        points = []

        if len(geo_xpaths):
            for xpath in geo_xpaths:
                geometry = [float(s) for s in doc.get(xpath, u'').split()]

                if len(geometry):
                    lat, lng = geometry[0:2]
                    points.append(Point(lng, lat))

            if not xform.instances_with_geopoints and len(points):
                xform.instances_with_geopoints = True
                xform.save()

            self.geom = GeometryCollection(points)

    def _set_json(self):
        self.json = self.get_full_dict()

    def get_full_dict(self):
        doc = self.json or {}
        doc.update(self.get_dict())

        if self.id:
            doc.update({
                UUID: self.uuid,
                ID: self.id,
                BAMBOO_DATASET_ID: self.xform.bamboo_dataset,
                ATTACHMENTS: _get_attachments_from_instance(self),
                STATUS: self.status,
                TAGS: list(self.tags.names()),
                NOTES: self.get_notes(),
                VERSION: self.version,
                DURATION: self.get_duration(),
                XFORM_ID_STRING: self._parser.get_xform_id_string(),
                GEOLOCATION: [self.point.y, self.point.x] if self.point
                else [None, None],
                SUBMITTED_BY: self.user.username if self.user else None
            })

            if isinstance(self.deleted_at, datetime):
                doc[DELETEDAT] = self.deleted_at.strftime(MONGO_STRFTIME)

            if not self.date_created:
                self.date_created = submission_time()

            doc[SUBMISSION_TIME] = self.date_created.strftime(MONGO_STRFTIME)

        return doc

    def _set_parser(self):
        if not hasattr(self, "_parser"):
            self._parser = XFormInstanceParser(
                self.xml, self.xform.data_dictionary())

    def _set_survey_type(self):
        self.survey_type, created = \
            SurveyType.objects.get_or_create(slug=self.get_root_node_name())

    def _set_uuid(self):
        if self.xml and not self.uuid:
            uuid = get_uuid_from_xml(self.xml)
            if uuid is not None:
                self.uuid = uuid
        set_uuid(self)

    def get(self, abbreviated_xpath):
        self._set_parser()
        return self._parser.get(abbreviated_xpath)

    def get_dict(self, force_new=False, flat=True):
        """Return a python object representation of this instance's XML."""
        self._set_parser()

        instance_dict = self._parser.get_flat_dict_with_attributes() if flat \
            else self._parser.to_dict()
        return self.numeric_converter(instance_dict)

    def get_notes(self):
        return [note['note'] for note in self.notes.values('note')]

    def get_root_node(self):
        self._set_parser()
        return self._parser.get_root_node()

    def get_root_node_name(self):
        self._set_parser()
        return self._parser.get_root_node_name()

    @property
    def point(self):
        gc = self.geom

        if gc and len(gc):
            return gc[0]

    def save(self, *args, **kwargs):
        force = kwargs.get('force')

        if force:
            del kwargs['force']

        self._check_active(force)

        self._set_geom()
        self._set_json()
        self._set_survey_type()
        self._set_uuid()
        self.version = self.xform.version
        super(Instance, self).save(*args, **kwargs)

    def set_deleted(self, deleted_at=timezone.now()):
        self.deleted_at = deleted_at
        self.save()
        # force submission count re-calculation
        self.xform.submission_count(force_update=True)
        self.parsed_instance.save()

    def get_duration(self):
        data = self.get_dict()
        dd = self.xform.data_dictionary()
        start_name = _get_tag_or_element_type_xpath(dd, START)
        end_name = _get_tag_or_element_type_xpath(dd, END)
        start_time, end_time = data.get(start_name), data.get(end_name)

        return calculate_duration(start_time, end_time)


post_save.connect(update_xform_submission_count, sender=Instance,
                  dispatch_uid='update_xform_submission_count')

post_delete.connect(update_xform_submission_count_delete, sender=Instance,
                    dispatch_uid='update_xform_submission_count_delete')


def save_project(sender, instance=None, created=False, **kwargs):
    instance.xform.project.save()

pre_save.connect(save_project, sender=Instance,
                 dispatch_uid='save_project_instance')


def save_full_json(sender, instance=None, created=False, **kwargs):
    if created:
        instance.json = instance.get_full_dict()
        instance.save()

post_save.connect(save_full_json, Instance, dispatch_uid='save_full_json')


class InstanceHistory(models.Model):

    class Meta:
        app_label = 'logger'

    xform_instance = models.ForeignKey(
        Instance, related_name='submission_history')
    xml = models.TextField()
    # old instance id
    uuid = models.CharField(max_length=249, default=u'')

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
