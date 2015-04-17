import csv
import codecs
import cStringIO
from collections import OrderedDict
from itertools import chain

from django.conf import settings
from pyxform.section import Section, RepeatingSection
from pyxform.question import Question

from onadata.apps.logger.models.xform import XForm
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.apps.viewer.models.parsed_instance import ParsedInstance
from onadata.libs.exceptions import NoRecordsFoundError
from onadata.libs.utils.common_tags import ID, XFORM_ID_STRING, STATUS,\
    ATTACHMENTS, GEOLOCATION, UUID, SUBMISSION_TIME, NA_REP,\
    BAMBOO_DATASET_ID, DELETEDAT, TAGS, NOTES, SUBMITTED_BY, VERSION,\
    DURATION
from onadata.libs.utils.export_tools import question_types_to_exclude


# the bind type of select multiples that we use to compare
MULTIPLE_SELECT_BIND_TYPE = u"select"
GEOPOINT_BIND_TYPE = u"geopoint"

# column group delimiters
GROUP_DELIMITER_SLASH = '/'
GROUP_DELIMITER_DOT = '.'
DEFAULT_GROUP_DELIMITER = GROUP_DELIMITER_SLASH
GROUP_DELIMITERS = [GROUP_DELIMITER_SLASH, GROUP_DELIMITER_DOT]


def remove_dups_from_list_maintain_order(l):
    return list(OrderedDict.fromkeys(l))


def get_prefix_from_xpath(xpath):
    xpath = str(xpath)
    parts = xpath.rsplit('/', 1)
    if len(parts) == 1:
        return None
    elif len(parts) == 2:
        return '%s/' % parts[0]
    else:
        raise ValueError(
            '%s cannot be prefixed, it returns %s' % (xpath, str(parts)))


class UnicodeWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([unicode(s).encode("utf-8") for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


def write_to_csv(path, rows, columns, truncate_tite=False):
    na_rep = getattr(settings, 'NA_REP', NA_REP)
    with open(path, 'wb') as csvfile:
        writer = UnicodeWriter(csvfile, lineterminator='\n')

        # Check if to truncate the group name prefix
        if truncate_tite:
            new_colum = [col.split('/')[-1:][0]
                         if '/' in col else col for col in columns]
            writer.writerow(new_colum)
        else:
            writer.writerow(columns)

        for row in rows:
            for col in AbstractDataFrameBuilder.IGNORED_COLUMNS:
                row.pop(col, None)
            writer.writerow([row.get(col, na_rep) for col in columns])


class AbstractDataFrameBuilder(object):
    IGNORED_COLUMNS = [XFORM_ID_STRING, STATUS, ID, ATTACHMENTS, GEOLOCATION,
                       BAMBOO_DATASET_ID, DELETEDAT]
    # fields NOT within the form def that we want to include
    ADDITIONAL_COLUMNS = [
        UUID, SUBMISSION_TIME, TAGS, NOTES, VERSION, DURATION, SUBMITTED_BY]
    BINARY_SELECT_MULTIPLES = False
    """
    Group functionality used by any DataFrameBuilder i.e. XLS, CSV and KML
    """

    def __init__(self, username, id_string, filter_query=None,
                 group_delimiter=DEFAULT_GROUP_DELIMITER,
                 split_select_multiples=True, binary_select_multiples=False,
                 start=None, end=None, truncate_title=False):
        self.username = username
        self.id_string = id_string
        self.filter_query = filter_query
        self.group_delimiter = group_delimiter
        self.split_select_multiples = split_select_multiples
        self.BINARY_SELECT_MULTIPLES = binary_select_multiples
        self.start = start
        self.end = end
        self.truncate_title = truncate_title
        self.xform = XForm.objects.get(id_string=self.id_string,
                                       user__username=self.username)
        self._setup()

    def _setup(self):
        self.dd = DataDictionary.objects.get(user__username=self.username,
                                             id_string=self.id_string)
        self.select_multiples = self._collect_select_multiples(self.dd)
        self.gps_fields = self._collect_gps_fields(self.dd)

    @classmethod
    def _fields_to_select(cls, dd):
        return [c.get_abbreviated_xpath()
                for c in dd.get_survey_elements() if isinstance(c, Question)]

    @classmethod
    def _collect_select_multiples(cls, dd):
        return dict([(e.get_abbreviated_xpath(), [c.get_abbreviated_xpath()
                                                  for c in e.children])
                     for e in dd.get_survey_elements()
                     if e.bind.get("type") == "select"])

    @classmethod
    def _split_select_multiples(cls, record, select_multiples,
                                binary_select_multiples=False):
        """ Prefix contains the xpath and slash if we are within a repeat so
        that we can figure out which select multiples belong to which repeat
        """
        for key, choices in select_multiples.items():
            # the select multiple might be blank or not exist in the record,
            # need to make those False
            selections = []
            if key in record:
                # split selected choices by spaces and join by / to the
                # element's xpath
                selections = ["%s/%s" % (key, r)
                              for r in record[key].split(" ")]
                # remove the column since we are adding separate columns
                # for each choice
                record.pop(key)
                if not binary_select_multiples:
                    # add columns to record for every choice, with default
                    # False and set to True for items in selections
                    record.update(dict([(choice, choice in selections)
                                        for choice in choices]))
                else:
                    YES = 1
                    NO = 0
                    record.update(
                        dict([(choice, YES if choice in selections else NO)
                              for choice in choices]))

            # recurs into repeats
            for record_key, record_item in record.items():
                if type(record_item) == list:
                    for list_item in record_item:
                        if type(list_item) == dict:
                            cls._split_select_multiples(
                                list_item, select_multiples)
        return record

    @classmethod
    def _collect_gps_fields(cls, dd):
        return [e.get_abbreviated_xpath() for e in dd.get_survey_elements()
                if e.bind.get("type") == "geopoint"]

    @classmethod
    def _tag_edit_string(cls, record):
        """
        Turns a list of tags into a string representation.
        """
        if '_tags' in record:
            tags = []
            for tag in record['_tags']:
                if ',' in tag and ' ' in tag:
                    tags.append('"%s"' % tag)
                else:
                    tags.append(tag)
            record.update({'_tags': u', '.join(sorted(tags))})

    @classmethod
    def _split_gps_fields(cls, record, gps_fields):
        updated_gps_fields = {}
        for key, value in record.iteritems():
            if key in gps_fields and isinstance(value, basestring):
                gps_xpaths = DataDictionary.get_additional_geopoint_xpaths(key)
                gps_parts = dict([(xpath, None) for xpath in gps_xpaths])
                # hack, check if its a list and grab the object within that
                parts = value.split(' ')
                # TODO: check whether or not we can have a gps recording
                # from ODKCollect that has less than four components,
                # for now we are assuming that this is not the case.
                if len(parts) == 4:
                    gps_parts = dict(zip(gps_xpaths, parts))
                updated_gps_fields.update(gps_parts)
            # check for repeats within record i.e. in value
            elif type(value) == list:
                for list_item in value:
                    if type(list_item) == dict:
                        cls._split_gps_fields(list_item, gps_fields)
        record.update(updated_gps_fields)

    def _query_data(self, query='{}', start=0,
                    limit=ParsedInstance.DEFAULT_LIMIT,
                    fields='[]', count=False):
        # ParsedInstance.query_mongo takes params as json strings
        # so we dumps the fields dictionary
        count_args = {
            'xform': self.xform,
            'query': query,
            'start': self.start,
            'end': self.end,
            'fields': '[]',
            'sort': '{}',
            'count': True
        }
        count_object = list(ParsedInstance.query_data(**count_args))
        record_count = count_object[0]["count"]
        if record_count < 1:
            raise NoRecordsFoundError("No records found for your query")
        # if count was requested, return the count
        if count:
            return record_count
        else:
            query_args = {
                'xform': self.xform,
                'query': query,
                'fields': fields,
                'start': self.start,
                'end': self.end,
                # TODO: we might want to add this in for the user
                # to sepcify a sort order
                'sort': 'id',
                'start_index': start,
                'limit': limit,
                'count': False
            }
            # use ParsedInstance.query_mongo
            cursor = ParsedInstance.query_data(**query_args)
            return cursor


class CSVDataFrameBuilder(AbstractDataFrameBuilder):

    def __init__(self, username, id_string, filter_query=None,
                 group_delimiter=DEFAULT_GROUP_DELIMITER,
                 split_select_multiples=True, binary_select_multiples=False,
                 start=None, end=None, truncate_title=False):
        super(CSVDataFrameBuilder, self).__init__(
            username, id_string, filter_query, group_delimiter,
            split_select_multiples, binary_select_multiples, start, end,
            truncate_title)
        self.ordered_columns = OrderedDict()

    def _setup(self):
        super(CSVDataFrameBuilder, self)._setup()

    @classmethod
    def _reindex(cls, key, value, ordered_columns, parent_prefix=None):
        """
        Flatten list columns by appending an index, otherwise return as is
        """
        d = {}

        # check for lists
        if type(value) is list and len(value) > 0 \
                and key not in [ATTACHMENTS, NOTES]:
            for index, item in enumerate(value):
                # start at 1
                index += 1
                # for each list check for dict, we want to transform the key of
                # this dict
                if type(item) is dict:
                    for nested_key, nested_val in item.iteritems():
                        # given the key "children/details" and nested_key/
                        # abbreviated xpath
                        # "children/details/immunization/polio_1",
                        # generate ["children", index, "immunization/polio_1"]
                        xpaths = [
                            "%s[%s]" % (
                                nested_key[:nested_key.index(key) + len(key)],
                                index),
                            nested_key[nested_key.index(key) + len(key) + 1:]]
                        # re-create xpath the split on /
                        xpaths = "/".join(xpaths).split("/")
                        new_prefix = xpaths[:-1]
                        if type(nested_val) is list:
                            # if nested_value is a list, rinse and repeat
                            d.update(cls._reindex(
                                nested_key, nested_val,
                                ordered_columns, new_prefix))
                        else:
                            # it can only be a scalar
                            # collapse xpath
                            if parent_prefix:
                                xpaths[0:len(parent_prefix)] = parent_prefix
                            new_xpath = u"/".join(xpaths)
                            # check if this key exists in our ordered columns
                            if key in ordered_columns.keys():
                                if new_xpath not in ordered_columns[key]:
                                    ordered_columns[key].append(new_xpath)
                            d[new_xpath] = nested_val
                else:
                    d[key] = value
        else:
            # anything that's not a list will be in the top level dict so its
            # safe to simply assign
            if key == NOTES:
                d[key] = u"\r\n".join(value)
            elif key == ATTACHMENTS:
                d[key] = []
            else:
                d[key] = value
        return d

    @classmethod
    def _build_ordered_columns(cls, survey_element, ordered_columns,
                               is_repeating_section=False):
        """
        Build a flat ordered dict of column groups

        is_repeating_section ensures that child questions of repeating sections
        are not considered columns
        """
        for child in survey_element.children:
            # child_xpath = child.get_abbreviated_xpath()
            if isinstance(child, Section):
                child_is_repeating = False
                if isinstance(child, RepeatingSection):
                    ordered_columns[child.get_abbreviated_xpath()] = []
                    child_is_repeating = True
                cls._build_ordered_columns(child, ordered_columns,
                                           child_is_repeating)
            elif isinstance(child, Question) and not \
                question_types_to_exclude(child.type) and not\
                    is_repeating_section:  # if is_repeating_section,
                    # its parent already initiliased an empty list
                    # so we dont add it to our list of columns,
                    # the repeating columns list will be
                    # generated when we reindex
                ordered_columns[child.get_abbreviated_xpath()] = None

    def _format_for_dataframe(self, cursor):
        # TODO: check for and handle empty results
        # add ordered columns for select multiples
        if self.split_select_multiples:
            for key, choices in self.select_multiples.items():
                # HACK to ensure choices are NOT duplicated
                self.ordered_columns[key] = \
                    remove_dups_from_list_maintain_order(choices)
        # add ordered columns for gps fields
        for key in self.gps_fields:
            gps_xpaths = self.dd.get_additional_geopoint_xpaths(key)
            self.ordered_columns[key] = [key] + gps_xpaths
        data = []
        for record in cursor:
            # split select multiples
            if self.split_select_multiples:
                record = self._split_select_multiples(
                    record, self.select_multiples,
                    self.BINARY_SELECT_MULTIPLES)
            # check for gps and split into components i.e. latitude, longitude,
            # altitude, precision
            self._split_gps_fields(record, self.gps_fields)
            self._tag_edit_string(record)
            flat_dict = {}
            # re index repeats
            for key, value in record.iteritems():
                reindexed = self._reindex(key, value, self.ordered_columns)
                flat_dict.update(reindexed)

            # if delimetr is diferent, replace within record as well
            if self.group_delimiter != DEFAULT_GROUP_DELIMITER:
                flat_dict = dict((self.group_delimiter.join(k.split('/')), v)
                                 for k, v in flat_dict.iteritems())
            data.append(flat_dict)
        return data

    def export_to(self, path):
        self.ordered_columns = OrderedDict()
        self._build_ordered_columns(self.dd.survey, self.ordered_columns)

        cursor = self._query_data(
            self.filter_query)
        data = self._format_for_dataframe(cursor)

        columns = list(chain.from_iterable(
            [[xpath] if cols is None else cols
             for xpath, cols in self.ordered_columns.iteritems()]))

        # use a different group delimiter if needed
        if self.group_delimiter != DEFAULT_GROUP_DELIMITER:
            columns = [self.group_delimiter.join(col.split("/"))
                       for col in columns]

        # add extra columns
        columns += [col for col in self.ADDITIONAL_COLUMNS]

        write_to_csv(path, data, columns, truncate_tite=self.truncate_title)
