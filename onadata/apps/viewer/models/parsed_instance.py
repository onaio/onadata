# -*- coding: utf-8 -*-
"""
ParsedInstance model
"""

import datetime

from django.conf import settings
from django.db import connection, models
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
from onadata.libs.utils.cache_tools import XFORM_SUBMISSIONS_DELETING, safe_cache_get
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
from onadata.libs.utils.common_tools import get_abbreviated_xpath
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
    return get_abbreviated_xpath(element.get_xpath())


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

    cursor.execute(sql, sql_params)
    if fields is None:
        for row in cursor.fetchall():
            yield parse_json(row[0]) if row[0] else None
    else:
        for row in cursor.fetchall():
            yield dict(
                zip(fields, (json.loads(s) if isinstance(s, str) else s for s in row))
            )


def get_etag_hash_from_query(sql=None, params=None):
    """Returns md5 hash from the date_modified field or"""
    if sql:
        from_index = sql.find("FROM ")
        sql = (
            "SELECT md5(string_agg(date_modified::text, ''))"
            " FROM (SELECT date_modified " + sql[from_index:] + ") AS A"
        )
        etag_hash = [i for i in _query_iterator(sql, params=params) if i is not None]

        if etag_hash:
            return etag_hash[0]

    return f"{datetime.datetime.utcnow()}"


# pylint: disable=too-many-arguments, too-many-positional-arguments
def _start_index_limit(sql, params, start_index, limit):
    if (start_index is not None and start_index < 0) or (
        limit is not None and limit < 0
    ):
        raise ValueError(_("Invalid start/limit params"))

    start_index = 0 if limit is not None and start_index is None else start_index
    if start_index is not None:
        params += [start_index]
        sql += " OFFSET %s"
    if limit is not None:
        sql += " LIMIT %s"
        params += [limit]

    return sql, params


def _get_sort_fields(sort):
    sort = ["id"] if sort is None else sort_from_mongo_sort_str(sort)

    return list(_parse_sort_fields(sort))


def exclude_deleting_submissions_clause(xform_id: int) -> tuple[str, list[int]]:
    """Return SQL clause to exclude submissions whose deletion is in progress

    :param xform_id: XForm ID
    :return: SQL and list of submission IDs under deletion
    """
    instance_ids = safe_cache_get(f"{XFORM_SUBMISSIONS_DELETING}{xform_id}", [])

    if not instance_ids:
        return ("", [])

    placeholders = ", ".join(["%s"] * len(instance_ids))
    return (f"id NOT IN ({placeholders})", instance_ids)


# pylint: disable=too-many-locals
def build_sql_where(xform, query, start=None, end=None):
    """Build SQL WHERE clause"""
    known_integers = [
        get_name_from_survey_element(e)
        for e in xform.get_survey_elements_of_type("integer")
    ]
    where = []
    where_params = []

    if query and isinstance(query, list):
        for qry in query:
            _where, _where_params = get_where_clause(qry, known_integers)
            where += _where
            where_params += _where_params

    else:
        where, where_params = get_where_clause(query, known_integers)

    sql_where = "WHERE xform_id in %s AND deleted_at IS NULL"

    if where_params:
        sql_where += " AND " + " AND ".join(where)

    if isinstance(start, datetime.datetime):
        sql_where += " AND date_created >= %s"
        where_params += [start.isoformat()]
    if isinstance(end, datetime.datetime):
        sql_where += " AND date_created <= %s"
        where_params += [end.isoformat()]

    exclude_sql, exclude_params = exclude_deleting_submissions_clause(xform.pk)

    if exclude_sql:
        # Exclude submissions whose deletion is in progress
        sql_where += f" AND {exclude_sql}"
        where_params += exclude_params

    xform_pks = [xform.pk]

    if xform.is_merged_dataset:
        merged_xform_ids = list(
            xform.mergedxform.xforms.filter(deleted_at__isnull=True).values_list(
                "id", flat=True
            )
        )
        if merged_xform_ids:
            xform_pks = list(merged_xform_ids)

    params = [tuple(xform_pks)] + where_params

    return sql_where, params


# pylint: disable=too-many-locals,too-many-statements,too-many-branches
def get_sql_with_params(
    xform,
    query=None,
    fields=None,
    sort=None,
    start=None,
    end=None,
    start_index=None,
    limit=None,
    json_only: bool = True,
):
    """Returns the SQL and related parameters"""
    sort = _get_sort_fields(sort)
    sql = ""

    if fields and isinstance(fields, six.string_types):
        fields = json.loads(fields)

    if fields:
        field_list = ["json->%s" for _i in fields]
        sql = f"SELECT {','.join(field_list)} FROM logger_instance"

    else:
        if json_only:
            # pylint: disable=protected-access
            if sort and ParsedInstance._has_json_fields(sort):
                sql = "SELECT json FROM logger_instance"

            else:
                sql = "SELECT id,json FROM logger_instance"

        else:
            sql = "SELECT id,json,xml FROM logger_instance"

    sql_where, params = build_sql_where(xform, query, start, end)
    sql += f" {sql_where}"

    # apply sorting
    if sort:
        # pylint: disable=protected-access
        if ParsedInstance._has_json_fields(sort):
            params = list(params) + json_order_by_params(
                sort, none_json_fields=NONE_JSON_FIELDS
            )
            _json_order_by = json_order_by(
                sort, none_json_fields=NONE_JSON_FIELDS, model_name="logger_instance"
            )
            sql = f"{sql} {_json_order_by}"
        else:
            sql += " ORDER BY"

            for index, sort_field in enumerate(sort):
                if sort_field.startswith("-"):
                    sort_field = sort_field.removeprefix("-")
                    # It's safe to use string interpolation since this
                    # is a column and not a value
                    sql += f" {sort_field} DESC"
                else:
                    sql += f" {sort_field} ASC"

                if index != len(sort) - 1:
                    sql += ","

    sql, params = _start_index_limit(sql, params, start_index, limit)

    return sql, params


def query_count(
    xform,
    query=None,
    date_created_gte=None,
    date_created_lte=None,
):
    """Count number of instances matching query"""
    sql_where, params = build_sql_where(
        xform,
        query,
        date_created_gte,
        date_created_lte,
    )
    sql = f"SELECT COUNT(id) FROM logger_instance {sql_where}"  # nosec

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        (count,) = cursor.fetchone()

    return count


def query_fields_data(
    xform,
    fields,
    query=None,
    sort=None,
    start=None,
    end=None,
    start_index=None,
    limit=None,
):
    """Query the submissions table and return json fields data"""
    sql, params = get_sql_with_params(
        xform,
        query=query,
        fields=fields,
        sort=sort,
        start=start,
        end=end,
        start_index=start_index,
        limit=limit,
    )

    if isinstance(fields, six.string_types):
        fields = json.loads(fields)

    return _query_iterator(sql, fields, params)


def query_data(
    xform,
    query=None,
    sort=None,
    start=None,
    end=None,
    start_index=None,
    limit=None,
    json_only: bool = True,
):
    """Query the submissions table and returns the results"""
    sql, params = get_sql_with_params(
        xform,
        query=query,
        sort=sort,
        start=start,
        end=end,
        start_index=start_index,
        limit=limit,
        json_only=json_only,
    )

    instances = Instance.objects.raw(sql, params)

    for instance in instances.iterator():
        if json_only:
            yield instance.json
        else:
            yield instance


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
