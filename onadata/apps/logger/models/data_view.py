# -*- coding: utf-8 -*-
"""
DataView model class
"""

import datetime
import json

from django.conf import settings
from django.contrib.gis.db import models
from django.db import connection
from django.db.models.signals import post_delete, post_save
from django.db.utils import DataError
from django.utils import timezone
from django.utils.translation import gettext as _

from onadata.apps.viewer.parsed_instance_tools import get_where_clause
from onadata.libs.models.sorting import (  # noqa pylint: disable=unused-import
    json_order_by,
    json_order_by_params,
    sort_from_mongo_sort_str,
)
from onadata.libs.utils.cache_tools import (  # noqa pylint: disable=unused-import
    DATAVIEW_COUNT,
    DATAVIEW_LAST_SUBMISSION_TIME,
    PROJ_OWNER_CACHE,
    XFORM_LINKED_DATAVIEWS,
    safe_delete,
)
from onadata.libs.utils.common_tags import (
    ATTACHMENTS,
    EDITED,
    GEOLOCATION,
    ID,
    LAST_EDITED,
    MONGO_STRFTIME,
    NOTES,
    SUBMISSION_TIME,
)
from onadata.libs.utils.common_tools import get_abbreviated_xpath

SUPPORTED_FILTERS = ["=", ">", "<", ">=", "<=", "<>", "!="]
ATTACHMENT_TYPES = ["photo", "audio", "video"]
DEFAULT_COLUMNS = [ID, SUBMISSION_TIME, EDITED, LAST_EDITED, NOTES]


def _json_sql_str(key, known_integers=None, known_dates=None, known_decimals=None):
    _json_str = "json->>%s"

    if known_integers is not None and key in known_integers:
        _json_str = "CAST(json->>%s AS INT)"
    elif known_dates is not None and key in known_dates:
        _json_str = "CAST(json->>%s AS TIMESTAMP)"
    elif known_decimals is not None and key in known_decimals:
        _json_str = "CAST(JSON->>%s AS DECIMAL)"

    return _json_str


def get_name_from_survey_element(element):
    """Returns the abbreviated xpath of a given ``SurveyElement``."""
    return get_abbreviated_xpath(element.get_xpath())


def append_where_list(comp, t_list, json_str):
    """Concatenates an SQL query based on the ``comp`` comparison value."""
    if comp in ["=", ">", "<", ">=", "<="]:
        t_list.append(f"{json_str} {comp}" + " %s")
    elif comp in ["<>", "!="]:
        t_list.append(f"{json_str} <>" + " %s")

    return t_list


def get_elements_of_type(xform, field_type):
    """
    This function returns a list of column names of a specified type
    """
    return [f.get("name") for f in xform.get_survey_elements_of_type(field_type)]


def has_attachments_fields(data_view):
    """
    This function checks if any column of the dataview is of type
    photo, video or audio (attachments fields). It returns a boolean
    value.
    """
    xform = data_view.xform

    if xform:
        attachments = []
        for element_type in ATTACHMENT_TYPES:
            attachments += get_elements_of_type(xform, element_type)

        if attachments:
            for attachment in data_view.columns:
                if attachment in attachments:
                    return True

    return False


class DataView(models.Model):
    """
    Model to provide filtered access to the underlying data of an XForm
    """

    name = models.CharField(max_length=255)
    xform = models.ForeignKey("logger.XForm", on_delete=models.CASCADE)
    project = models.ForeignKey("logger.Project", on_delete=models.CASCADE)

    columns = models.JSONField()
    query = models.JSONField(default=dict, blank=True)
    instances_with_geopoints = models.BooleanField(default=False)
    matches_parent = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="dataview_deleted_by",
        null=True,
        on_delete=models.SET_NULL,
        default=None,
        blank=True,
    )

    class Meta:
        app_label = "logger"
        verbose_name = _("Data View")
        verbose_name_plural = _("Data Views")

    def __str__(self):
        return getattr(self, "name", "")

    def has_geo_columnn_n_data(self):
        """
        Check if the data set from the data view has geo location data
        :return: boolean True if present
        """

        # Get the form geo xpaths
        xform = self.xform
        geo_xpaths = xform.geopoint_xpaths()

        set_geom = set(geo_xpaths)
        set_columns = set(self.columns)

        geo_column_selected = set_geom.intersection(set_columns)

        # Check if geolocation column selected
        if geo_column_selected:
            return True
        return False

    def save(self, *args, **kwargs):
        self.instances_with_geopoints = self.has_geo_columnn_n_data()
        return super().save(*args, **kwargs)

    def _get_known_type(self, type_str):
        return [
            get_name_from_survey_element(e)
            for e in self.xform.get_survey_elements_of_type(type_str)
        ]

    def get_known_integers(self):
        """Return elements of type integer"""
        return self._get_known_type("integer")

    def get_known_dates(self):
        """Return elements of type date"""
        return self._get_known_type("date")

    def get_known_decimals(self):
        """Return elements of type decimal"""
        return self._get_known_type("decimal")

    def has_instance(self, instance):
        """Return True if instance in set of dataview data"""
        cursor = connection.cursor()
        sql = "SELECT count(json) FROM logger_instance"

        where, where_params = self._get_where_clause(
            self,
            self.get_known_integers(),
            self.get_known_dates(),
            self.get_known_decimals(),
        )
        sql_where = ""
        if where:
            sql_where = " AND " + " AND ".join(where)

        sql += (
            " WHERE xform_id = %s AND id = %s" + sql_where + " AND deleted_at IS NULL"
        )
        params = [self.xform.pk, instance.id] + where_params

        cursor.execute(sql, [str(i) for i in params])
        records = None
        for row in cursor.fetchall():
            records = row[0]

        return records is not None

    def soft_delete(self, user=None):
        """
        Mark the dataview as soft deleted, appending a timestamped suffix to
        the name to make the initial values available without violating the
        uniqueness constraint.
        """
        soft_deletion_time = timezone.now()
        deletion_suffix = soft_deletion_time.strftime("-deleted-at-%s")
        self.deleted_at = soft_deletion_time
        self.name += deletion_suffix
        update_fields = ["date_modified", "deleted_at", "name", "deleted_by"]
        if user is not None:
            self.deleted_by = user
            update_fields.append("deleted_by")
        self.save(update_fields=update_fields)

    def restore(self):
        """
        Restore the dataview by removing the timestamped suffix from the name
        and setting the deleted_at field to None.
        """
        if self.deleted_at is not None:
            self.name = self.name.split("-deleted-at-")[0]
            self.deleted_at = None
            self.deleted_by = None
            self.save(
                update_fields=["name", "deleted_at", "deleted_by", "date_modified"]
            )

    @classmethod
    def _get_where_clause(  # pylint: disable=too-many-locals
        cls,
        data_view,
        form_integer_fields=None,
        form_date_fields=None,
        form_decimal_fields=None,
    ):
        form_integer_fields = [] if form_integer_fields is None else form_integer_fields
        form_date_fields = [] if form_date_fields is None else form_date_fields
        form_decimal_fields = [] if form_decimal_fields is None else form_decimal_fields
        known_integers = ["_id"] + form_integer_fields
        known_dates = ["_submission_time"] + form_date_fields
        known_decimals = form_decimal_fields
        where = []
        where_params = []

        queries = data_view.query

        or_where = []
        or_params = []

        for query in queries:
            comp = query.get("filter")
            column = query.get("column")
            value = query.get("value")
            condi = query.get("condition")

            json_str = _json_sql_str(
                column, known_integers, known_dates, known_decimals
            )

            if comp in known_dates:
                value = datetime.datetime.strptime(value[:19], MONGO_STRFTIME)

            if condi and condi.lower() == "or":
                or_where = append_where_list(comp, or_where, json_str)
                or_params.extend((column, str(value)))
            else:
                where = append_where_list(comp, where, json_str)
                where_params.extend((column, str(value)))

        if or_where:
            or_where = ["".join(["(", " OR ".join(or_where), ")"])]

        where += or_where
        where_params.extend(or_params)

        return where, where_params

    @classmethod
    def query_iterator(cls, sql, fields=None, params=None, count=False):
        """A database query iterator."""

        def parse_json(data):
            try:
                return json.loads(data)
            except ValueError:
                return data

        params = [] if params is None else params

        cursor = connection.cursor()
        sql_params = tuple(i if isinstance(i, tuple) else str(i) for i in params)

        if count:
            from_pos = sql.upper().find(" FROM")
            if from_pos != -1:
                sql = "SELECT COUNT(*) " + sql[from_pos:]

            order_pos = sql.upper().find("ORDER BY")
            if order_pos != -1:
                sql = sql[:order_pos]

            fields = ["count"]

        cursor.execute(sql, sql_params)

        if fields is None:
            for row in cursor.fetchall():
                yield parse_json(row[0])
        else:
            if count:
                for row in cursor.fetchall():
                    yield dict(zip(fields, row))
            else:
                for row in cursor.fetchall():
                    yield dict(zip(fields, [parse_json(row[0]).get(f) for f in fields]))

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    # pylint: disable=too-many-locals,too-many-branches
    @classmethod
    def generate_query_string(
        cls,
        data_view,
        start_index,
        limit,
        last_submission_time,
        all_data,
        sort,
        filter_query=None,
    ):
        """Returns an SQL string based on the passed in parameters."""
        additional_columns = []
        if data_view.instances_with_geopoints:
            additional_columns = [GEOLOCATION]

        if has_attachments_fields(data_view):
            additional_columns += [ATTACHMENTS]

        sql = "SELECT json FROM logger_instance"
        if all_data or data_view.matches_parent:
            columns = None
        elif last_submission_time:
            columns = [SUBMISSION_TIME]
        else:
            # get the columns needed
            columns = data_view.columns + DEFAULT_COLUMNS + additional_columns

            # field_list = [u"json->%s" for i in columns]

            # sql = u"SELECT %s FROM logger_instance" % u",".join(field_list)

        where, where_params = cls._get_where_clause(
            data_view,
            data_view.get_known_integers(),
            data_view.get_known_dates(),
            data_view.get_known_decimals(),
        )

        if filter_query:
            add_where, add_where_params = get_where_clause(
                filter_query,
                data_view.get_known_integers(),
                data_view.get_known_decimals(),
            )

            if add_where:
                where = where + add_where
                where_params = where_params + add_where_params

        sql_where = ""
        if where:
            sql_where = " AND " + " AND ".join(where)

        if data_view.xform.is_merged_dataset:
            sql += " WHERE xform_id IN %s " + sql_where + " AND deleted_at IS NULL"
            params = [
                tuple(
                    list(
                        data_view.xform.mergedxform.xforms.values_list("pk", flat=True)
                    )
                )
            ] + where_params
        else:
            sql += " WHERE xform_id = %s " + sql_where + " AND deleted_at IS NULL"
            params = [data_view.xform.pk] + where_params

        if sort is not None:
            sort = ["id"] if sort is None else sort_from_mongo_sort_str(sort)
            sql = f"{sql} {json_order_by(sort)}"
            params = params + json_order_by_params(sort)

        elif last_submission_time is False:
            sql += " ORDER BY id"

        if start_index is not None:
            sql += " OFFSET %s"
            params += [start_index]
        if limit is not None:
            sql += " LIMIT %s"
            params += [limit]

        if last_submission_time:
            sql += " ORDER BY date_created DESC"
            sql += " LIMIT 1"

        return (
            sql,
            columns,
            params,
        )

    @classmethod
    def query_data(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        cls,
        data_view,
        start_index=None,
        limit=None,
        count=None,
        last_submission_time=False,
        all_data=False,
        sort=None,
        filter_query=None,
    ):
        """Returns a list of records for the view based on the parameters passed in."""

        (sql, columns, params) = cls.generate_query_string(
            data_view,
            start_index,
            limit,
            last_submission_time,
            all_data,
            sort,
            filter_query,
        )

        try:
            records = list(DataView.query_iterator(sql, columns, params, count))
        except DataError as error:
            return {"error": _(str(error))}

        return records


def clear_cache(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """Post delete handler for clearing the dataview cache."""
    safe_delete(f"{XFORM_LINKED_DATAVIEWS}{instance.xform.pk}")


def clear_dataview_cache(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """Post Save handler for clearing dataview cache on serialized fields."""
    safe_delete(f"{PROJ_OWNER_CACHE}{instance.project.pk}")
    safe_delete(f"{DATAVIEW_COUNT}{instance.xform.pk}")
    safe_delete(f"{DATAVIEW_LAST_SUBMISSION_TIME}{instance.xform.pk}")
    safe_delete(f"{XFORM_LINKED_DATAVIEWS}{instance.xform.pk}")


post_save.connect(clear_dataview_cache, sender=DataView, dispatch_uid="clear_cache")

post_delete.connect(clear_cache, sender=DataView, dispatch_uid="clear_xform_cache")
