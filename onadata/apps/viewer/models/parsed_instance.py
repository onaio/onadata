# -*- coding: utf-8 -*-
"""
ParsedInstance model
"""
import datetime
import types

from django.conf import settings
from django.db import connection, models
from django.db.models.query import EmptyQuerySet
from django.utils.translation import gettext as _

import six
import ujson as json
from dateutil import parser

from onadata.apps.logger.models.instance import Instance, _get_attachments_from_instance
from onadata.apps.logger.models.note import Note
from onadata.apps.logger.models.xform import _encode_for_mongo
from onadata.apps.viewer.parsed_instance_tools import NONE_JSON_FIELDS, get_where_clause
from onadata.libs.models.sorting import (
    json_order_by,
    json_order_by_params,
    sort_from_mongo_sort_str,
)
from onadata.libs.utils.common_tags import (
    ATTACHMENTS,
    BAMBOO_DATASET_ID,
    DATE_MODIFIED,
    DELETEDAT,
    DURATION,
    EDITED,
    GEOLOCATION,
    ID,
    MEDIA_ALL_RECEIVED,
    MEDIA_COUNT,
    MONGO_STRFTIME,
    NOTES,
    REVIEW_COMMENT,
    REVIEW_DATE,
    REVIEW_STATUS,
    SUBMISSION_TIME,
    SUBMITTED_BY,
    TAGS,
    TOTAL_MEDIA,
    UUID,
    VERSION,
    XFORM_ID,
)
from onadata.libs.utils.model_tools import queryset_iterator
from onadata.libs.utils.mongo import _is_invalid_for_mongo

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


class ParseError(Exception):
    """
    Raise when an exception happens when parsing the XForm XML submission.
    """


def datetime_from_str(text):
    """
    Parses a datetime from a string and returns the datetime object.
    """
    # Assumes text looks like 2011-01-01T09:50:06.966
    if text is None:
        return None
    try:
        return parser.parse(text)
    except (TypeError, ValueError):
        return None
    return None


def dict_for_mongo(item):
    """
    Validates the keys of a python object.
    """
    for key, value in item.items():
        if isinstance(value, list):
            value = [dict_for_mongo(e) if isinstance(e, dict) else e for e in value]
        elif isinstance(value, dict):
            value = dict_for_mongo(value)
        elif key == "_id":
            try:
                item[key] = int(value)
            except ValueError:
                # if it is not an int don't convert it
                pass
        if _is_invalid_for_mongo(key):
            del item[key]
            item[_encode_for_mongo(key)] = value
    return item


def get_name_from_survey_element(element):
    """
    Returns the abbreviated xpath of an element.
    """
    return element.get_abbreviated_xpath()


def _parse_sort_fields(fields):
    for field in fields:
        key = field.lstrip("-")
        if field.startswith("-") and key in NONE_JSON_FIELDS:
            field = NONE_JSON_FIELDS.get(key)
            yield f"-{field}"
        else:
            yield NONE_JSON_FIELDS.get(field, field)


def _query_iterator(sql, fields=None, params=None, count=False):
    def parse_json(data):
        try:
            return json.loads(data)
        except ValueError:
            return data

    if not sql:
        raise ValueError(_(f"Bad SQL: {sql}"))
    params = [] if params is None else params
    cursor = connection.cursor()
    sql_params = fields + params if fields is not None else params

    if count:
        # do sql count of subquery, takes into account all options sql has and
        # is less hacky
        sql = "SELECT COUNT(*) FROM (" + sql + ") AS CQ"
        fields = ["count"]

    cursor.execute(sql, [str(i) for i in sql_params])
    if fields is None:
        for row in cursor.fetchall():
            yield parse_json(row[0]) if row[0] else None
    else:
        for row in cursor.fetchall():
            yield dict(zip(fields, (json.loads(s) for s in row)))


def get_etag_hash_from_query(queryset, sql=None, params=None):
    """Returns md5 hash from the date_modified field or"""
    if not isinstance(queryset, EmptyQuerySet):
        if sql is None:
            sql, params = queryset.query.sql_with_params()
        from_index = sql.find("FROM ")
        sql = (
            "SELECT md5(string_agg(date_modified::text, ''))"
            " FROM (SELECT date_modified " + sql[from_index:] + ") AS A"
        )
        etag_hash = [i for i in _query_iterator(sql, params=params) if i is not None]

        if etag_hash:
            return etag_hash[0]

    return f"{datetime.datetime.utcnow()}"


# pylint: disable=too-many-arguments
def _start_index_limit(records, sql, fields, params, sort, start_index, limit):
    if (start_index is not None and start_index < 0) or (
        limit is not None and limit < 0
    ):
        raise ValueError(_("Invalid start/limit params"))
    if (start_index is not None or limit is not None) and not sql:
        sql, params = records.query.sql_with_params()
        params = list(params)

    start_index = 0 if limit is not None and start_index is None else start_index
    # pylint: disable=protected-access
    has_json_fields = ParsedInstance._has_json_fields(sort)
    if start_index is not None and (has_json_fields or fields):
        params += [start_index]
        sql = f"{sql} OFFSET %s"
    if limit is not None and (has_json_fields or fields):
        sql = f"{sql} LIMIT %s"
        params += [limit]
    if (
        start_index is not None
        and limit is not None
        and not fields
        and not has_json_fields
    ):
        end_index = start_index + limit
        records = records[start_index:end_index]
    if start_index is not None and limit is None and not fields and not has_json_fields:
        records = records[start_index:]

    return records, sql, params


def _get_instances(xform, start, end):
    kwargs = {"deleted_at": None}

    if isinstance(start, datetime.datetime):
        kwargs.update({"date_created__gte": start})
    if isinstance(end, datetime.datetime):
        kwargs.update({"date_created__lte": end})

    if xform.is_merged_dataset:
        xforms = xform.mergedxform.xforms.filter(deleted_at__isnull=True).values_list(
            "id", flat=True
        )
        xform_ids = list(xforms) or [xform.pk]
        instances = Instance.objects.filter(xform_id__in=xform_ids)
    else:
        instances = xform.instances

    return instances.filter(**kwargs)


def _get_sort_fields(sort):
    sort = ["id"] if sort is None else sort_from_mongo_sort_str(sort)

    return list(_parse_sort_fields(sort))


# pylint: disable=too-many-locals
def get_sql_with_params(
    xform,
    query=None,
    fields=None,
    sort=None,
    start=None,
    end=None,
    start_index=None,
    limit=None,
    count=None,
    json_only: bool = True,
):
    """
    Returns the SQL and related parameters.
    """
    records = _get_instances(xform, start, end)
    params = []
    sort = _get_sort_fields(sort)
    sql = ""

    known_integers = [
        get_name_from_survey_element(e)
        for e in xform.get_survey_elements_of_type("integer")
    ]
    where, where_params = get_where_clause(query, known_integers)

    if fields and isinstance(fields, six.string_types):
        fields = json.loads(fields)

    if fields:
        field_list = ["json->%s" for _i in fields]
        sql = f"SELECT {','.join(field_list)} FROM logger_instance"

        sql_where = ""
        if where_params:
            sql_where = " AND " + " AND ".join(where)

        sql += " WHERE xform_id = %s " + sql_where + " AND deleted_at IS NULL"
        params = [xform.pk] + where_params
    else:
        if json_only:
            records = records.values_list("json", flat=True)

        if query and isinstance(query, list):
            for qry in query:
                _where, _where_params = get_where_clause(qry, known_integers)
                records = records.extra(where=_where, params=_where_params)

        else:
            if where_params:
                records = records.extra(where=where, params=where_params)

    # apply sorting
    if not count and sort:
        # pylint: disable=protected-access
        if ParsedInstance._has_json_fields(sort):
            if not fields:
                # we have to do a sql query for json field order
                sql, params = records.query.sql_with_params()
            params = list(params) + json_order_by_params(
                sort, none_json_fields=NONE_JSON_FIELDS
            )
            _json_order_by = json_order_by(
                sort, none_json_fields=NONE_JSON_FIELDS, model_name="logger_instance"
            )
            sql = f"{sql} {_json_order_by}"
        else:
            if not fields:
                records = records.order_by(*sort)

    records, sql, params = _start_index_limit(
        records, sql, fields, params, sort, start_index, limit
    )

    return sql, params, records


def query_data(
    xform,
    query=None,
    fields=None,
    sort=None,
    start=None,
    end=None,
    start_index=None,
    limit=None,
    count=None,
    json_only: bool = True,
):
    """Query the submissions table and returns the results."""

    sql, params, records = get_sql_with_params(
        xform,
        query,
        fields,
        sort,
        start,
        end,
        start_index,
        limit,
        count,
        json_only=json_only,
    )
    if fields and isinstance(fields, six.string_types):
        fields = json.loads(fields)
    sort = _get_sort_fields(sort)
    # pylint: disable=protected-access
    if (ParsedInstance._has_json_fields(sort) or fields) and sql:
        records = _query_iterator(sql, fields, params, count)

    if count and isinstance(records, types.GeneratorType):
        return list(records)
    if count:
        return [{"count": records.count()}]

    return records


class ParsedInstance(models.Model):
    """
    ParsedInstance - parsed XML submission, represents the XML submissions as a python
                     object.
    """

    USERFORM_ID = "_userform_id"
    STATUS = "_status"
    DEFAULT_LIMIT = settings.PARSED_INSTANCE_DEFAULT_LIMIT
    DEFAULT_BATCHSIZE = settings.PARSED_INSTANCE_DEFAULT_BATCHSIZE

    instance = models.OneToOneField(
        Instance, related_name="parsed_instance", on_delete=models.CASCADE
    )
    start_time = models.DateTimeField(null=True)
    end_time = models.DateTimeField(null=True)
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

        return any(i for i in sort_list if i.lstrip("-") not in fields)

    def to_dict_for_mongo(self):
        """
        Return the XForm XML submission as a python object.
        """
        data_dict = self.to_dict()
        data = {
            UUID: self.instance.uuid,
            ID: self.instance.id,
            BAMBOO_DATASET_ID: self.instance.xform.bamboo_dataset,
            self.USERFORM_ID: (
                f"{self.instance.xform.user.username}_"
                f"{self.instance.xform.id_string}"
            ),
            ATTACHMENTS: _get_attachments_from_instance(self.instance),
            self.STATUS: self.instance.status,
            GEOLOCATION: [self.lat, self.lng],
            SUBMISSION_TIME: self.instance.date_created.strftime(MONGO_STRFTIME),
            DATE_MODIFIED: self.instance.date_modified.strftime(MONGO_STRFTIME),
            TAGS: list(self.instance.tags.names()),
            NOTES: self.get_notes(),
            SUBMITTED_BY: self.instance.user.username if self.instance.user else None,
            VERSION: self.instance.version,
            DURATION: self.instance.get_duration(),
            XFORM_ID: self.instance.xform.pk,
            TOTAL_MEDIA: self.instance.total_media,
            MEDIA_COUNT: self.instance.media_count,
            MEDIA_ALL_RECEIVED: self.instance.media_all_received,
        }

        if isinstance(self.instance.deleted_at, datetime.datetime):
            data[DELETEDAT] = self.instance.deleted_at.strftime(MONGO_STRFTIME)

        if self.instance.has_a_review:
            review = self.instance.get_latest_review()
            if review:
                data[REVIEW_STATUS] = review.status
                data[REVIEW_DATE] = review.date_created.strftime(MONGO_STRFTIME)
                if review.get_note_text():
                    data[REVIEW_COMMENT] = review.get_note_text()

        data[EDITED] = self.instance.submission_history.count() > 0

        data_dict.update(data)

        return dict_for_mongo(data_dict)

    def to_dict(self):
        """
        Returns a python dictionary object of a submission.
        """
        if not hasattr(self, "_dict_cache"):
            # pylint: disable=attribute-defined-outside-init
            self._dict_cache = self.instance.get_dict()
        return self._dict_cache

    @classmethod
    def dicts(cls, xform):
        """
        Iterates over a forms submissions.
        """
        queryset = cls.objects.filter(instance__xform=xform)
        for parsed_instance in queryset_iterator(queryset):
            yield parsed_instance.to_dict()

    def _get_name_for_type(self, type_value):
        """
        We cannot assume that start time and end times always use the same
        XPath. This is causing problems for other peoples' forms.

        This is a quick fix to determine from the original XLSForm's JSON
        representation what the 'name' was for a given
        type_value ('start' or 'end')
        """
        datadict = self.instance.xform.json_dict()
        for item in datadict["children"]:
            if isinstance(item, dict) and item.get("type") == type_value:
                return item["name"]
        return None

    def _set_geopoint(self):
        if self.instance.point:
            self.lat = self.instance.point.y
            self.lng = self.instance.point.x

    def save(self, *args, **kwargs):  # noqa
        # start/end_time obsolete: originally used to approximate for
        # instanceID, before instanceIDs were implemented
        self.start_time = None
        self.end_time = None
        self._set_geopoint()
        super().save(*args, **kwargs)  # noqa

    def add_note(self, note):
        """
        Add a note for the instance.
        """
        note = Note(instance=self.instance, note=note)
        note.save()

    def remove_note(self, note_id):
        """
        Deletes the note with the `pk` as ``note_id``
        """
        note = self.instance.notes.get(pk=note_id)
        note.delete()

    def get_notes(self):
        """Returns a list of notes data objects."""
        notes = []
        note_qs = self.instance.notes.values(
            "id", "note", "date_created", "date_modified"
        )
        for note in note_qs:
            note["date_created"] = note["date_created"].strftime(MONGO_STRFTIME)
            note["date_modified"] = note["date_modified"].strftime(MONGO_STRFTIME)
            notes.append(note)
        return notes
