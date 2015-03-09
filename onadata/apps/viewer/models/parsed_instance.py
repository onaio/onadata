import base64
import datetime
import json
import re
import six

from dateutil import parser
from django.db import connection
from django.db import models
from django.db.models.signals import post_save
from django.utils.translation import ugettext as _

from onadata.apps.logger.models.note import Note
from onadata.apps.logger.models.instance import _get_attachments_from_instance
from onadata.apps.logger.models.instance import Instance
from onadata.apps.restservice.utils import call_service
from onadata.libs.utils.common_tags import ID, UUID, ATTACHMENTS, GEOLOCATION,\
    SUBMISSION_TIME, MONGO_STRFTIME, BAMBOO_DATASET_ID, DELETEDAT, TAGS,\
    NOTES, SUBMITTED_BY, VERSION, DURATION

from onadata.libs.utils.model_tools import queryset_iterator


# this is Mongo Collection where we will store the parsed submissions
key_whitelist = ['$or', '$and', '$exists', '$in', '$gt', '$gte',
                 '$lt', '$lte', '$regex', '$options', '$all']
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


def _encode_for_mongo(key):
    return reduce(lambda s, c: re.sub(c[0], base64.b64encode(c[1]), s),
                  [(r'^\$', '$'), (r'\.', '.')], key)


def _decode_from_mongo(key):
    re_dollar = re.compile(r"^%s" % base64.b64encode("$"))
    re_dot = re.compile(r"\%s" % base64.b64encode("."))
    return reduce(lambda s, c: c[0].sub(c[1], s),
                  [(re_dollar, '$'), (re_dot, '.')], key)


def _is_invalid_for_mongo(key):
    return key not in\
        key_whitelist and (key.startswith('$') or key.count('.') > 0)


def sort_from_mongo_sort_str(sort_str):
    sort_values = []
    if isinstance(sort_str, six.string_types):
        if sort_str.startswith('{'):
            sort_dict = json.loads(sort_str)
            for k, v in sort_dict.items():
                try:
                    v = int(v)
                except ValueError:
                    pass
                if v < 0:
                    k = u'-{}'.format(k)
                sort_values.append(k)
        else:
            sort_values.append(sort_str)

    return sort_values


def _json_order_by(sort_list):
    _list = []

    for field in sort_list:
        _str = u" json->>%s"
        if field.startswith('-'):
            _str += u" DESC"
        else:
            _str += u" ASC"
        _list.append(_str)

    if len(_list) > 0:
        return u"ORDER BY {}".format(u",".join(_list))

    return u""


def _json_order_by_params(sort_list):
    params = []

    for field in sort_list:
        params.append(field.lstrip('-'))

    return params


def get_name_from_survey_element(element):
    xpath = element.get_xpath()
    model = xpath.split('/')[1]
    return element.get_xpath().replace('/%s/' % model, '')


class ParsedInstance(models.Model):
    USERFORM_ID = u'_userform_id'
    STATUS = u'_status'
    DEFAULT_LIMIT = 30000
    DEFAULT_BATCHSIZE = 1000

    instance = models.OneToOneField(Instance, related_name="parsed_instance")
    start_time = models.DateTimeField(null=True)
    end_time = models.DateTimeField(null=True)
    # TODO: decide if decimal field is better than float field.
    lat = models.FloatField(null=True)
    lng = models.FloatField(null=True)

    class Meta:
        app_label = "viewer"

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
    def _get_where_clause(cls, query, form_integer_fields=[]):
        known_integers = ['_id'] + form_integer_fields
        where = []
        where_params = []
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

            # where = [u"json->>%s = %s" for i in query.items()] + or_where
            for k, v in query.items():
                if isinstance(v, dict):
                    json_str = u"CAST(json->>%s AS INT)" \
                        if k in known_integers else u"json->%s"
                    _v = None
                    if '$gt' in v:
                        where.append(u"{} > %s".format(json_str))
                        _v = v.get('$gt')
                    if '$gte' in v:
                        where.append(u"{} >= %s".format(json_str))
                        _v = v.get('$gte')
                    if '$lt' in v:
                        where.append(u"{} < %s".format(json_str))
                        _v = v.get('$lt')
                    if '$lte' in v:
                        where.append(u"{} <= %s".format(json_str))
                        _v = v.get('$lte')
                    if _v is None:
                        _v = v
                    where_params.extend((k, unicode(_v)))
                else:
                    where.append(u"json->>%s = %s")
                    where_params.extend((k, unicode(v)))
            where += or_where
            # [where_params.extend((k, unicode(v))) for k, v in query.items()]
            where_params.extend(or_params)

        return where, where_params

    @classmethod
    def query_data(cls, xform, query=None, fields=None, sort=None, start=None,
                   end=None, start_index=None, limit=None, count=None):
        if start_index is not None and \
                (start_index is not None and start_index < 0 or
                 (limit is not None and limit < 0)):
            raise ValueError(_("Invalid start/limit params"))
        if limit is not None and start_index is None:
            start_index = 0

        instances = xform.instances.filter(deleted_at=None)
        if isinstance(start, datetime.datetime):
            instances = instances.filter(date_created__gte=start)
        if isinstance(end, datetime.datetime):
            instances = instances.filter(date_created__lte=end)
        sort = ['id'] if sort is None else sort_from_mongo_sort_str(sort)

        sql_where = u""
        data_dictionary = xform.data_dictionary()
        known_integers = [
            get_name_from_survey_element(e)
            for e in data_dictionary.get_survey_elements_of_type('integer')]
        where, where_params = cls._get_where_clause(query, known_integers)

        if fields and isinstance(fields, six.string_types):
            fields = json.loads(fields)

        if fields:
            field_list = [u"json->%s" for i in fields]
            sql = u"SELECT %s FROM logger_instance" % u",".join(field_list)

            if where_params:
                sql_where = u" AND " + u" AND ".join(where)

            sql += u" WHERE xform_id = %s " + sql_where \
                + u" AND deleted_at IS NULL"
            params = [xform.pk] + where_params

            # apply sorting
            if ParsedInstance._has_json_fields(sort):
                sql = u"{} {}".format(sql, _json_order_by(sort))
                params = params + _json_order_by_params(sort)

            if start_index is not None:
                sql += u" OFFSET %s"
                params += [start_index]
            if limit is not None:
                sql += u" LIMIT %s"
                params += [limit]
            records = ParsedInstance.query_iterator(sql, fields, params, count)
        else:
            if count:
                return [{"count": instances.count()}]

            if where_params:
                instances = instances.extra(where=where, params=where_params)

            if ParsedInstance._has_json_fields(sort):
                # we have to do an sql query for json field order
                records = instances.values_list('json', flat=True)
                _sql, _params = records.query.sql_with_params()
                sql = u"{} {}".format(_sql, _json_order_by(sort))
                params = list(_params) + _json_order_by_params(sort)
                records = ParsedInstance.query_iterator(sql, None, params)
            else:
                records = instances.order_by(*sort)\
                    .values_list('json', flat=True)

            if start_index is not None:
                if ParsedInstance._has_json_fields(sort):
                    _sql, _params = sql, params
                    params = _params + [start_index]
                else:
                    _sql, _params = records.query.sql_with_params()
                    params = list(_params + (start_index,))
                # some inconsistent/weird behavior I noticed with django's
                # queryset made me have to do a raw query
                # records = records[start_index: limit]
                sql = u"{} OFFSET %s".format(_sql)
                if limit is not None:
                    sql = u"{} LIMIT %s".format(sql)
                    params += [limit]
                records = ParsedInstance.query_iterator(sql, None, params)

        return records

    @classmethod
    def _has_json_fields(cls, sort_list):
        """
        Checks if any field in sort_list is not a field in the Instance model
        """
        fields = Instance._meta.get_all_field_names()

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

    def get_data_dictionary(self):
        # TODO: fix hack to get around a circular import
        from onadata.apps.viewer.models.data_dictionary import\
            DataDictionary
        return DataDictionary.objects.get(
            user=self.instance.xform.user,
            id_string=self.instance.xform.id_string
        )

    data_dictionary = property(get_data_dictionary)

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
            note['date_created'] = \
                note['date_created'].strftime(MONGO_STRFTIME)
            note['date_modified'] = \
                note['date_modified'].strftime(MONGO_STRFTIME)
            notes.append(note)
        return notes


def rest_service_form_submission(sender, **kwargs):
    parsed_instance = kwargs.get('instance')
    created = kwargs.get('created')
    if created:
        call_service(parsed_instance)


post_save.connect(rest_service_form_submission, sender=ParsedInstance)
