from datetime import datetime

from django.contrib.gis.db import models
from django.db.models.signals import post_save
from django.db.models.signals import post_delete
from django.contrib.auth.models import User
from django.contrib.gis.geos import GeometryCollection, Point
from django.utils import timezone
from django.utils.translation import ugettext as _
from jsonfield import JSONField
from taggit.managers import TaggableManager

from onadata.apps.logger.models.survey_type import SurveyType
from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.xform_instance_parser import XFormInstanceParser,\
    clean_and_parse_xml, get_uuid_from_xml
from onadata.libs.utils.common_tags import ATTACHMENTS, BAMBOO_DATASET_ID,\
    DELETEDAT, GEOLOCATION, ID, MONGO_STRFTIME, NOTES, SUBMISSION_TIME, TAGS,\
    UUID, XFORM_ID_STRING
from onadata.libs.utils.model_tools import set_uuid


class FormInactiveError(Exception):
    def __unicode__(self):
        return _("Form is inactive")

    def __str__(self):
        return unicode(self).encode('utf-8')


# need to establish id_string of the xform before we run get_dict since
# we now rely on data dictionary to parse the xml
def get_id_string_from_xml_str(xml_str):
    xml_obj = clean_and_parse_xml(xml_str)
    root_node = xml_obj.documentElement

    return root_node.getAttribute(u"id")


def submission_time():
    return timezone.now()


def update_xform_submission_count(sender, instance, created, **kwargs):
    if created:
        xform = XForm.objects.select_related().select_for_update()\
            .get(pk=instance.xform.pk)
        if xform.num_of_submissions == -1:
            xform.num_of_submissions = 0
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
        doc = self.get_dict()

        if not self.date_created:
            now = submission_time()
            self.date_created = now

        point = self.point
        if point:
            doc[GEOLOCATION] = [point.y, point.x]

        doc[SUBMISSION_TIME] = self.date_created.strftime(MONGO_STRFTIME)
        doc[XFORM_ID_STRING] = self._parser.get_xform_id_string()
        self.json = doc

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

    def _set_xform(self, id_string):
        self.xform = XForm.objects.get(id_string=id_string, user=self.user)

    def get(self, abbreviated_xpath):
        self._set_parser()
        return self._parser.get(abbreviated_xpath)

    def get_dict(self, force_new=False, flat=True):
        """Return a python object representation of this instance's XML."""
        self._set_parser()

        return self._parser.get_flat_dict_with_attributes() if flat else\
            self._parser.to_dict()

    def get_full_dict(self):
        # TODO should we store all of these in the JSON no matter what?
        d = self.json
        data = {
            UUID: self.uuid,
            ID: self.id,
            BAMBOO_DATASET_ID: self.xform.bamboo_dataset,
            self.USERFORM_ID: u'%s_%s' % (
                self.user.username,
                self.xform.id_string),
            ATTACHMENTS: [a.media_file.name for a in
                          self.attachments.all()],
            self.STATUS: self.status,
            TAGS: list(self.tags.names()),
            NOTES: self.get_notes()
        }

        if isinstance(self.instance.deleted_at, datetime):
            data[DELETEDAT] = self.deleted_at.strftime(MONGO_STRFTIME)

        d.update(data)

        return d

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

        try:
            self._set_xform(get_id_string_from_xml_str(self.xml))
        except XForm.DoesNotExist:
            if not force:
                raise XForm.DoesNotExist

        self._set_geom()
        self._set_json()
        self._set_survey_type()
        self._set_uuid()
        super(Instance, self).save(*args, **kwargs)

    def set_deleted(self, deleted_at=timezone.now()):
        self.deleted_at = deleted_at
        self.save()
        # force submission count re-calculation
        self.xform.submission_count(force_update=True)
        self.parsed_instance.save()


post_save.connect(update_xform_submission_count, sender=Instance,
                  dispatch_uid='update_xform_submission_count')

post_delete.connect(update_xform_submission_count_delete, sender=Instance,
                    dispatch_uid='update_xform_submission_count_delete')


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
