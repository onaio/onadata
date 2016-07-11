import base64
import datetime
import json
import re
import six
import types

from dateutil import parser
from django.conf import settings
from django.db import connection
from django.db import models
from django.db.models.signals import post_save
from django.utils.translation import ugettext as _

from onadata.apps.logger.models.note import Note
from onadata.apps.logger.models.instance import _get_attachments_from_instance
from onadata.apps.logger.models.instance import Instance
from onadata.apps.logger.models.xform import _encode_for_mongo

from onadata.libs.models.sorting import (
    json_order_by, json_order_by_params, sort_from_mongo_sort_str)
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.restservice.tasks import call_service_async,\
    sync_update_google_sheets, sync_delete_google_sheets,\
    call_google_sheet_service
from onadata.libs.utils.common_tags import ID, UUID, ATTACHMENTS, GEOLOCATION,\
    SUBMISSION_TIME, MONGO_STRFTIME, BAMBOO_DATASET_ID, DELETEDAT, TAGS,\
    NOTES, SUBMITTED_BY, VERSION, DURATION, EDITED,\
    UPDATE_OR_DELETE_GOOGLE_SHEET_DATA
from onadata.libs.utils.osm import save_osm_data_async
from onadata.libs.utils.common_tools import get_boolean_value
from onadata.libs.utils.model_tools import queryset_iterator

ASYNC_POST_SUBMISSION_PROCESSING_ENABLED = \
    getattr(settings, 'ASYNC_POST_SUBMISSION_PROCESSING_ENABLED', False)


# this is Mongo Collection where we will store the parsed submissions
key_whitelist = ['$or', '$and', '$exists', '$in', '$gt', '$gte',
                 '$lt', '$lte', '$regex', '$options', '$all']
DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S'
KNOWN_DATES = ['_submission_time']
NONE_JSON_FIELDS = {
    '_submission_time': 'date_created',
    '_id': 'id'
}


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
        if type(value) == list:
            value = [dict_for_mongo(e)
                     if type(e) == dict else e for e in value]
        elif type(value) == dict:
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


def _decode_from_mongo(key):
    re_dollar = re.compile(r"^%s" % base64.b64encode("$"))
    re_dot = re.compile(r"\%s" % base64.b64encode("."))
    return reduce(lambda s, c: c[0].sub(c[1], s),
                  [(re_dollar, '$'), (re_dot, '.')], key)


def _is_invalid_for_mongo(key):
    return key not in\
        key_whitelist and (key.startswith('$') or key.count('.') > 0)


def _json_sql_str(key, known_integers=[], known_dates=[]):
    _json_str = u"json->>%s"

    if key in known_integers:
        _json_str = u"CAST(json->>%s AS INT)"
    elif key in known_dates:
        _json_str = u"CAST(json->>%s AS TIMESTAMP)"

    return _json_str


def get_name_from_survey_element(element):
    return element.get_abbreviated_xpath()


def _parse_sort_fields(fields):
    for field in fields:
        yield NONE_JSON_FIELDS.get(field, field)


def _parse_where(query, known_integers, or_where, or_params):
    # using a dictionary here just incase we will need to filter using
    # other table columns
    where, where_params = [], []
    OPERANDS = {
        '$gt': '>',
        '$gte': '>=',
        '$lt': '<',
        '$lte': '<=',
        '$i': '~*'
    }
    for field_key, field_value in query.iteritems():
        if isinstance(field_value, dict):
            if field_key in NONE_JSON_FIELDS:
                json_str = NONE_JSON_FIELDS.get(field_key)
            else:
                json_str = _json_sql_str(
                    field_key, known_integers, KNOWN_DATES)
            for key, value in field_value.iteritems():
                _v = None
                if key in OPERANDS:
                    where.append(
                        u' '.join([json_str, OPERANDS.get(key), u'%s'])
                    )
                _v = value
                if field_key in KNOWN_DATES:
                    _v = datetime.datetime.strptime(
                        _v[:19], MONGO_STRFTIME)
                if field_key in NONE_JSON_FIELDS:
                    where_params.extend([unicode(_v)])
                else:
                    where_params.extend((field_key, unicode(_v)))
        else:
            where.append(u"json->>%s = %s")
            where_params.extend((field_key, unicode(field_value)))

    return where + or_where, where_params + or_params


def _query_iterator(sql, fields=None, params=[], count=False):
    cursor = connection.cursor()
    sql_params = fields + params if fields is not None else params

    if count:
        # do sql count of subquery, takes into account all options sql has and
        # is less hacky
        sql = u"SELECT COUNT(*) FROM (" + sql + ") AS CQ"
        fields = [u'count']

    cursor.execute(sql, [unicode(i) for i in sql_params])

    if fields is None:
        for row in cursor.fetchall():
            yield row[0]
    else:
        for row in cursor.fetchall():
            yield dict(zip(fields, row))


def get_where_clause(query, form_integer_fields=[]):
    known_integers = ['_id'] + form_integer_fields
    where = []
    where_params = []

    try:
        if query and isinstance(query, six.string_types):
            query = json.loads(query)
            or_where = []
            or_params = []
            if isinstance(query, list):
                query = query[0]

            if '$or' in query.keys():
                or_dict = query.pop('$or')
                for l in or_dict:
                    or_where.extend([u"json->>%s = %s" for i in l.items()])
                    [or_params.extend(i) for i in l.items()]

                or_where = [u"".join([u"(", u" OR ".join(or_where), u")"])]

            where, where_params = _parse_where(query, known_integers,
                                               or_where, or_params)

    except (ValueError, AttributeError) as e:
        if query and isinstance(query, six.string_types) and \
                query.startswith('{'):
            raise e
        # cast query param to text
        where = [u"json::text ~* cast(%s as text)"]
        where_params = [query]

    return where, where_params


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
    instances = xform.instances.filter(deleted_at=None)
    if isinstance(start, datetime.datetime):
        instances = instances.filter(date_created__gte=start)
    if isinstance(end, datetime.datetime):
        instances = instances.filter(date_created__lte=end)

    return instances


def _get_sort_fields(sort):
    sort = ['id'] if sort is None else sort_from_mongo_sort_str(sort)

    return [i for i in _parse_sort_fields(sort)]


def query_data(xform, query=None, fields=None, sort=None, start=None,
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
        field_list = [u"json->%s" for i in fields]
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

    if ParsedInstance._has_json_fields(sort) or fields:
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
            DURATION: self.instance.get_duration()
        }

        if isinstance(self.instance.deleted_at, datetime.datetime):
            data[DELETEDAT] = self.instance.deleted_at.strftime(MONGO_STRFTIME)

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
            if type(item) == dict and item.get(u'type') == type_value:
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


def google_sync_post_save_signal(parsed_instance, created):
    xform = parsed_instance.instance.xform
    google_sheets_details = MetaData.get_google_sheet_details(xform.pk)
    retry_policy = {
        'max_retries': getattr(settings, 'DEFAULT_CELERY_MAX_RETIRES', 3),
        'interval_start':
            getattr(settings, 'DEFAULT_CELERY_INTERVAL_START', 1),
        'interval_step':  getattr(settings, 'DEFAULT_CELERY_INTERVAL_STEP',
                                  0.5),
        'interval_max':  getattr(settings, 'DEFAULT_CELERY_INTERVAL_MAX', 0.5)
    }

    # Check whethe google sheet is configured for this form
    if google_sheets_details:
        if created:
            # Always run in async mode
            call_google_sheet_service.apply_async(
                args=[parsed_instance.instance_id],
                countdown=1,
                retry_policy=retry_policy
            )
        else:
            should_sync_updates = \
                google_sheets_details.get(UPDATE_OR_DELETE_GOOGLE_SHEET_DATA)
            # update signal. Check for google_sheet metadata
            if get_boolean_value(should_sync_updates):

                # soft delete detected, sync google sheet
                if parsed_instance.instance.deleted_at:
                    sync_delete_google_sheets.apply_async(
                        args=[parsed_instance.instance_id, xform.pk],
                        countdown=1,
                        retry_policy=retry_policy
                    )
                else:
                    # normal update
                    sync_update_google_sheets.apply_async(
                        args=[parsed_instance.instance_id, xform.pk],
                        countdown=1,
                        retry_policy=retry_policy
                    )


def post_save_submission(sender, **kwargs):
    parsed_instance = kwargs.get('instance')
    created = kwargs.get('created')

    if created:
        if ASYNC_POST_SUBMISSION_PROCESSING_ENABLED:
            call_service_async.apply_async(
                args=[parsed_instance.instance_id],
                countdown=1
            )

            save_osm_data_async.apply_async(
                args=[parsed_instance.instance_id],
                countdown=1
            )
        else:
            call_service_async(parsed_instance.instance_id)
            save_osm_data_async(parsed_instance.instance_id)

    google_sync_post_save_signal(parsed_instance, created)


post_save.connect(post_save_submission, sender=ParsedInstance)
