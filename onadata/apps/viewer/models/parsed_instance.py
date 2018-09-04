import datetime
import json
import six
import types
from builtins import str as text
from dateutil import parser

from django.conf import settings
from django.db import connection
from django.db import models
from django.utils.translation import ugettext as _
from django.db.models.query import EmptyQuerySet

from onadata.apps.logger.models.note import Note
from onadata.apps.logger.models.instance import _get_attachments_from_instance
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.xform import _encode_for_mongo
from onadata.apps.viewer.parsed_instance_tools import (get_where_clause,
                                                       NONE_JSON_FIELDS)
from onadata.libs.models.sorting import (
    json_order_by, json_order_by_params, sort_from_mongo_sort_str)
from onadata.libs.utils.common_tags import ID, UUID, ATTACHMENTS, GEOLOCATION,\
    SUBMISSION_TIME, MONGO_STRFTIME, BAMBOO_DATASET_ID, DELETEDAT, TAGS,\
    NOTES, SUBMITTED_BY, VERSION, DURATION, EDITED, MEDIA_COUNT, TOTAL_MEDIA,\
    MEDIA_ALL_RECEIVED, XFORM_ID, REVIEW_STATUS, REVIEW_COMMENT
from onadata.libs.utils.model_tools import queryset_iterator
from onadata.libs.utils.mongo import _is_invalid_for_mongo

DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S'


class ParseError(Exception):
    pass


def datetime_from_str(text):
    # Assumes text looks like 2011-01-01T09:50:06.966
    if text is None:
        return None
    dt = None
    try:
        dt = parser.parse(text)
    except Exception:
        return None
    return dt


def dict_for_mongo(d):
    for key, value in d.items():
        if isinstance(value, list):
            value = [dict_for_mongo(e)
                     if isinstance(e, dict) else e for e in value]
        elif isinstance(value, dict):
            value = dict_for_mongo(value)
        elif key == '_id':
            try:
                d[key] = int(value)
            except ValueError:
                # if it is not an int don't convert it
                pass
        if _is_invalid_for_mongo(key):
            del d[key]
            d[_encode_for_mongo(key)] = value
    return d


def get_name_from_survey_element(element):
    return element.get_abbreviated_xpath()


def _parse_sort_fields(fields):
    for field in fields:
        yield NONE_JSON_FIELDS.get(field, field)


def _query_iterator(sql, fields=None, params=[], count=False):
    if not sql:
        raise ValueError(_(u"Bad SQL: %s" % sql))
    cursor = connection.cursor()
    sql_params = fields + params if fields is not None else params

    if count:
        # do sql count of subquery, takes into account all options sql has and
        # is less hacky
        sql = u"SELECT COUNT(*) FROM (" + sql + ") AS CQ"
        fields = [u'count']

    cursor.execute(sql, [text(i) for i in sql_params])

    if fields is None:
        for row in cursor.fetchall():
            yield row[0]
    else:
        for row in cursor.fetchall():
            yield dict(zip(fields, row))


def get_etag_hash_from_query(queryset, sql=None, params=None):
    """Returns md5 hash from the date_modified field or
    """
    if not isinstance(queryset, EmptyQuerySet):
        if sql is None:
            sql, params = queryset.query.sql_with_params()
        sql = (
            "SELECT md5(string_agg(date_modified::text, ''))"
            " FROM (SELECT date_modified " + sql[sql.find('FROM '):] + ") AS A"
        )
        etag_hash = [i for i in _query_iterator(sql, params=params)
                     if i is not None]

        if etag_hash:
            return etag_hash[0]

    return u'%s' % datetime.datetime.utcnow()


def _start_index_limit(records, sql, fields, params, sort, start_index, limit):
    if start_index is not None and \
            (start_index < 0 or (limit is not None and limit < 0)):
        raise ValueError(_("Invalid start/limit params"))
    if (start_index is not None or limit is not None) and not sql:
        sql, params = records.query.sql_with_params()
        params = list(params)

    start_index = 0 \
        if limit is not None and start_index is None else start_index

    if start_index is not None and \
            (ParsedInstance._has_json_fields(sort) or fields):
        params += [start_index]
        sql = u"%s OFFSET %%s" % sql
    if limit is not None and \
            (ParsedInstance._has_json_fields(sort) or fields):
        sql = u"%s LIMIT %%s" % sql
        params += [limit]
    if start_index is not None and limit is not None and not fields and  \
            not ParsedInstance._has_json_fields(sort):
        records = records[start_index: start_index + limit]
    if start_index is not None and limit is None and not fields and \
            not ParsedInstance._has_json_fields(sort):
        records = records[start_index:]

    return records, sql, params


def _get_instances(xform, start, end):
    kwargs = {'deleted_at': None}

    if isinstance(start, datetime.datetime):
        kwargs.update({'date_created__gte': start})
    if isinstance(end, datetime.datetime):
        kwargs.update({'date_created__lte': end})

    if xform.is_merged_dataset:
        xforms = xform.mergedxform.xforms.filter(deleted_at__isnull=True)\
            .values_list('id', flat=True)
        xform_ids = [i for i in xforms] or [xform.pk]
        instances = Instance.objects.filter(xform_id__in=xform_ids)
    else:
        instances = xform.instances

    return instances.filter(**kwargs)


def _get_sort_fields(sort):
    sort = ['id'] if sort is None else sort_from_mongo_sort_str(sort)

    return [i for i in _parse_sort_fields(sort)]


def get_sql_with_params(xform, query=None, fields=None, sort=None, start=None,
                        end=None, start_index=None, limit=None, count=None):
    records = _get_instances(xform, start, end)
    params = []
    sort = _get_sort_fields(sort)
    sql = ""

    known_integers = [
        get_name_from_survey_element(e)
        for e in xform.get_survey_elements_of_type('integer')]
    where, where_params = get_where_clause(query, known_integers)

    if fields and isinstance(fields, six.string_types):
        fields = json.loads(fields)

    if fields:
        field_list = [u"json->%s" for _i in fields]
        sql = u"SELECT %s FROM logger_instance" % u",".join(field_list)

        sql_where = u""
        if where_params:
            sql_where = u" AND " + u" AND ".join(where)

        sql += u" WHERE xform_id = %s " + sql_where \
            + u" AND deleted_at IS NULL"
        params = [xform.pk] + where_params
    else:

        records = records.values_list('json', flat=True)
        if where_params:
            records = records.extra(where=where, params=where_params)

    # apply sorting
    if not count and sort:
        if ParsedInstance._has_json_fields(sort):
            if not fields:
                # we have to do a sql query for json field order
                sql, params = records.query.sql_with_params()
            params = list(params) + json_order_by_params(sort)
            sql = u"%s %s" % (sql, json_order_by(sort))
        elif not fields:
            records = records.order_by(*sort)

    records, sql, params = _start_index_limit(
        records, sql, fields, params, sort, start_index, limit
    )

    return sql, params, records


def query_data(xform, query=None, fields=None, sort=None, start=None,
               end=None, start_index=None, limit=None, count=None):

    sql, params, records = get_sql_with_params(
        xform, query, fields, sort, start, end, start_index, limit, count
    )
    if fields and isinstance(fields, six.string_types):
        fields = json.loads(fields)
    sort = _get_sort_fields(sort)
    if (ParsedInstance._has_json_fields(sort) or fields) and sql:
        records = _query_iterator(sql, fields, params, count)

    if count and isinstance(records, types.GeneratorType):
        return [i for i in records]
    elif count:
        return [{"count": records.count()}]

    return records


class ParsedInstance(models.Model):
    USERFORM_ID = u'_userform_id'
    STATUS = u'_status'
    DEFAULT_LIMIT = settings.PARSED_INSTANCE_DEFAULT_LIMIT
    DEFAULT_BATCHSIZE = settings.PARSED_INSTANCE_DEFAULT_BATCHSIZE

    instance = models.OneToOneField(Instance, related_name="parsed_instance")
    start_time = models.DateTimeField(null=True)
    end_time = models.DateTimeField(null=True)
    # TODO: decide if decimal field is better than float field.
    lat = models.FloatField(null=True)
    lng = models.FloatField(null=True)

    class Meta:
        app_label = "viewer"

    @classmethod
    def _has_json_fields(cls, sort_list):
        """
        Checks if any field in sort_list is not a field in the Instance model
        """
        fields = [f.name for f in Instance._meta.get_fields()]

        return any([i for i in sort_list if i.lstrip('-') not in fields])

    def to_dict_for_mongo(self):
        d = self.to_dict()
        data = {
            UUID: self.instance.uuid,
            ID: self.instance.id,
            BAMBOO_DATASET_ID: self.instance.xform.bamboo_dataset,
            self.USERFORM_ID: u'%s_%s' % (
                self.instance.xform.user.username,
                self.instance.xform.id_string),
            ATTACHMENTS: _get_attachments_from_instance(self.instance),
            self.STATUS: self.instance.status,
            GEOLOCATION: [self.lat, self.lng],
            SUBMISSION_TIME: self.instance.date_created.strftime(
                MONGO_STRFTIME),
            TAGS: list(self.instance.tags.names()),
            NOTES: self.get_notes(),
            SUBMITTED_BY: self.instance.user.username
            if self.instance.user else None,
            VERSION: self.instance.version,
            DURATION: self.instance.get_duration(),
            XFORM_ID: self.instance.xform.pk,
            TOTAL_MEDIA: self.instance.total_media,
            MEDIA_COUNT: self.instance.media_count,
            MEDIA_ALL_RECEIVED: self.instance.media_all_received
        }

        if isinstance(self.instance.deleted_at, datetime.datetime):
            data[DELETEDAT] = self.instance.deleted_at.strftime(MONGO_STRFTIME)

        if self.instance.has_a_review:
            status, comment = self.instance.get_review_status_and_comment()
            data[REVIEW_STATUS] = status
            if comment:
                data[REVIEW_COMMENT] = comment

        data[EDITED] = (True if self.instance.submission_history.count() > 0
                        else False)

        d.update(data)

        return dict_for_mongo(d)

    def to_dict(self):
        if not hasattr(self, "_dict_cache"):
            self._dict_cache = self.instance.get_dict()
        return self._dict_cache

    @classmethod
    def dicts(cls, xform):
        qs = cls.objects.filter(instance__xform=xform)
        for parsed_instance in queryset_iterator(qs):
            yield parsed_instance.to_dict()

    def _get_name_for_type(self, type_value):
        """
        We cannot assume that start time and end times always use the same
        XPath. This is causing problems for other peoples' forms.

        This is a quick fix to determine from the original XLSForm's JSON
        representation what the 'name' was for a given
        type_value ('start' or 'end')
        """
        datadict = json.loads(self.instance.xform.json)
        for item in datadict['children']:
            if isinstance(item, dict) and item.get(u'type') == type_value:
                return item['name']

    # TODO: figure out how much of this code should be here versus
    # data_dictionary.py.
    def _set_geopoint(self):
        if self.instance.point:
            self.lat = self.instance.point.y
            self.lng = self.instance.point.x

    def save(self, async=False, *args, **kwargs):
        # start/end_time obsolete: originally used to approximate for
        # instanceID, before instanceIDs were implemented
        self.start_time = None
        self.end_time = None
        self._set_geopoint()
        super(ParsedInstance, self).save(*args, **kwargs)

    def add_note(self, note):
        note = Note(instance=self.instance, note=note)
        note.save()

    def remove_note(self, pk):
        note = self.instance.notes.get(pk=pk)
        note.delete()

    def get_notes(self):
        notes = []
        note_qs = self.instance.notes.values(
            'id', 'note', 'date_created', 'date_modified')
        for note in note_qs:
            note['date_created'] = note['date_created'].strftime(
                MONGO_STRFTIME)
            note['date_modified'] = note['date_modified'].strftime(
                MONGO_STRFTIME)
            notes.append(note)
        return notes
