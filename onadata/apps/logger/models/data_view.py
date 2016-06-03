import datetime

from django.utils.translation import ugettext as _
from django.contrib.gis.db import models
from django.contrib.postgres.fields import JSONField
from django.db import connection
from django.db.models.signals import post_delete, post_save

from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.project import Project
from onadata.libs.models.sorting import (
    json_order_by, json_order_by_params, sort_from_mongo_sort_str)
from onadata.libs.utils.common_tags import (
    ATTACHMENTS,
    EDITED,
    LAST_EDITED,
    MONGO_STRFTIME,
    NOTES,
    ID,
    GEOLOCATION,
    SUBMISSION_TIME)
from onadata.libs.utils.cache_tools import (
    safe_delete,
    DATAVIEW_COUNT,
    DATAVIEW_LAST_SUBMISSION_TIME,
    XFORM_LINKED_DATAVIEWS)

SUPPORTED_FILTERS = ['=', '>', '<', '>=', '<=', '<>', '!=']
ATTACHMENT_TYPES = ['photo', 'audio', 'video']
DEFAULT_COLUMNS = [ID, SUBMISSION_TIME, EDITED, LAST_EDITED, NOTES]


def _json_sql_str(key, known_integers=[], known_dates=[]):
    _json_str = u"json->>%s"

    if key in known_integers:
        _json_str = u"CAST(json->>%s AS INT)"
    elif key in known_dates:
        _json_str = u"CAST(json->>%s AS TIMESTAMP)"

    return _json_str


def get_name_from_survey_element(element):
    return element.get_abbreviated_xpath()


def append_where_list(comp, t_list, json_str):
    if comp in ['=', '>', '<', '>=', '<=']:
        t_list.append(u"{} {} %s".format(json_str, comp))
    elif comp in ['<>', '!=']:
        t_list.append(u"{} <> %s".format(json_str))

    return t_list


def get_elements_of_type(xform, field_type):
    """
    This function returns a list of column names of a specified type
    """
    return [f.get('name')
            for f in xform.get_survey_elements_of_type(field_type)]


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
            for a in data_view.columns:
                if a in attachments:
                    return True

    return False


class DataView(models.Model):
    """
    Model to provide filtered access to the underlying data of an XForm
    """

    name = models.CharField(max_length=255)
    xform = models.ForeignKey(XForm)
    project = models.ForeignKey(Project)

    columns = JSONField()
    query = JSONField(default=dict, blank=True)
    instances_with_geopoints = models.BooleanField(default=False)
    matches_parent = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'logger'
        verbose_name = _('Data View')
        verbose_name_plural = _('Data Views')

    def __unicode__(self):
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
        return super(DataView, self).save(*args, **kwargs)

    def _get_known_type(self, type_str):
        return [
            get_name_from_survey_element(e)
            for e in self.xform.get_survey_elements_of_type(type_str)]

    def get_known_integers(self):
        """Return elements of type integer"""
        return self._get_known_type('integer')

    def get_known_dates(self):
        """Return elements of type date"""
        return self._get_known_type('date')

    def has_instance(self, instance):
        cursor = connection.cursor()
        sql = u"SELECT count(json) FROM logger_instance"

        where, where_params = self._get_where_clause(self,
                                                     self.get_known_integers(),
                                                     self.get_known_dates())
        sql_where = u""
        if where:
            sql_where = u" AND " + u" AND ".join(where)

        sql += u" WHERE xform_id = %s AND id = %s" + sql_where \
               + u" AND deleted_at IS NULL"
        params = [self.xform.pk, instance.id] + where_params

        cursor.execute(sql, [unicode(i) for i in params])

        for row in cursor.fetchall():
            records = row[0]

        return True if records else False

    @classmethod
    def _get_where_clause(cls, data_view, form_integer_fields=[],
                          form_date_fields=[]):
        known_integers = ['_id'] + form_integer_fields
        known_dates = ['_submission_time'] + form_date_fields
        where = []
        where_params = []

        query = data_view.query

        or_where = []
        or_params = []

        for qu in query:
            comp = qu.get('filter')
            column = qu.get('column')
            value = qu.get('value')
            condi = qu.get('condition')

            json_str = _json_sql_str(column, known_integers, known_dates)

            if comp in known_dates:
                value = datetime.datetime.strptime(
                    value[:19], MONGO_STRFTIME)

            if condi and condi.lower() == 'or':
                or_where = append_where_list(comp, or_where, json_str)
                or_params.extend((column, unicode(value)))
            else:
                where = append_where_list(comp, where, json_str)
                where_params.extend((column, unicode(value)))

        if or_where:
            or_where = [u"".join([u"(", u" OR ".join(or_where), u")"])]

        where += or_where
        where_params.extend(or_params)

        return where, where_params

    @classmethod
    def query_iterator(cls, sql, fields=None, params=[], count=False):
        cursor = connection.cursor()
        sql_params = fields + params if fields is not None else params

        if count:
            from_pos = sql.upper().find(' FROM')
            if from_pos != -1:
                sql = u"SELECT COUNT(*) " + sql[from_pos:]

            order_pos = sql.upper().find('ORDER BY')
            if order_pos != -1:
                sql = sql[:order_pos]

            sql_params = params
            fields = [u'count']

        cursor.execute(sql, [unicode(i) for i in sql_params])

        if fields is None:
            for row in cursor.fetchall():
                yield row[0]
        else:
            for row in cursor.fetchall():
                yield dict(zip(fields, row))

    @classmethod
    def generate_query_string(cls, data_view, start_index, limit,
                              last_submission_time, all_data, sort):
        additional_columns = [GEOLOCATION] \
            if data_view.instances_with_geopoints else []

        if has_attachments_fields(data_view):
            additional_columns += [ATTACHMENTS]

        if all_data:
            sql = u"SELECT json FROM logger_instance"
            columns = None
        elif last_submission_time:
            sql = u"SELECT json->%s FROM logger_instance"
            columns = [SUBMISSION_TIME]
        else:
            # get the columns needed
            columns = data_view.columns + DEFAULT_COLUMNS + additional_columns

            field_list = [u"json->%s" for i in columns]

            sql = u"SELECT %s FROM logger_instance" % u",".join(field_list)

        where, where_params = cls._get_where_clause(
            data_view,
            data_view.get_known_integers(),
            data_view.get_known_dates())

        sql_where = ""
        if where:
            sql_where = u" AND " + u" AND ".join(where)

        sql += u" WHERE xform_id = %s " + sql_where \
               + u" AND deleted_at IS NULL"
        params = [data_view.xform.pk] + where_params

        if sort is not None:
            sort = ['id'] if sort is None\
                else sort_from_mongo_sort_str(sort)
            sql = u"{} {}".format(sql, json_order_by(sort))
            params = params + json_order_by_params(sort)

        elif last_submission_time is False:
            sql += ' ORDER BY id'

        if start_index is not None:
            sql += u" OFFSET %s"
            params += [start_index]
        if limit is not None:
            sql += u" LIMIT %s"
            params += [limit]

        if last_submission_time:
            sql += u" ORDER BY date_created DESC"
            sql += u" LIMIT 1"

        return (sql, columns, params, )

    @classmethod
    def query_data(cls, data_view, start_index=None, limit=None, count=None,
                   last_submission_time=False, all_data=False, sort=None):

        (sql, columns, params) = cls.generate_query_string(
            data_view, start_index, limit, last_submission_time,
            all_data, sort)

        try:
            records = [record for record in DataView.query_iterator(sql,
                                                                    columns,
                                                                    params,
                                                                    count)]
        except Exception as e:
            return {"error": _(e.message)}

        return records


# Post delete handler for clearing the dataview cache
def clear_cache(sender, instance, **kwargs):
    # clear cache
    safe_delete('{}{}'.format(XFORM_LINKED_DATAVIEWS, instance.xform.pk))


# Post Save handler for clearing dataview cache on serialized fields
def clear_dataview_cache(sender, instance, **kwargs):
    safe_delete('{}{}'.format(DATAVIEW_COUNT, instance.xform.pk))
    safe_delete(
        '{}{}'.format(DATAVIEW_LAST_SUBMISSION_TIME, instance.xform.pk))


post_save.connect(clear_dataview_cache, sender=DataView,
                  dispatch_uid='clear_cache')

post_delete.connect(clear_cache, sender=DataView,
                    dispatch_uid='clear_xform_cache')
