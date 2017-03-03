import re
from collections import OrderedDict
from itertools import chain

import unicodecsv as csv
from django.conf import settings
from django.db.models.query import QuerySet
from pyxform.question import Question
from pyxform.section import RepeatingSection, Section

from onadata.apps.logger.models import OsmData
from onadata.apps.logger.models.xform import XForm, question_types_to_exclude
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.apps.viewer.models.parsed_instance import (ParsedInstance,
                                                        query_data)
from onadata.libs.exceptions import NoRecordsFoundError
from onadata.libs.utils.common_tags import (ATTACHMENTS, BAMBOO_DATASET_ID,
                                            DELETEDAT, DURATION, EDITED,
                                            GEOLOCATION, ID, NA_REP, NOTES,
                                            STATUS, SUBMISSION_TIME,
                                            SUBMITTED_BY, TAGS, UUID, VERSION,
                                            XFORM_ID_STRING)
from onadata.libs.utils.export_builder import get_value_or_attachment_uri
from onadata.libs.utils.model_tools import get_columns_with_hxl

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


def get_labels_from_columns(columns, dd, group_delimiter):
    labels = []
    for col in columns:
        elem = dd.get_survey_element(col)
        label = dd.get_label(col, elem=elem) if elem else col
        if elem is not None and elem.type == '':
            label = group_delimiter.join([elem.parent.name, label])
        if label == '':
            label = elem.name
        labels.append(label)

    return labels


def get_column_names_only(columns, dd, group_delimiter):
    new_columns = []
    for col in columns:
        new_col = None
        elem = dd.get_survey_element(col)
        if elem is None:
            new_col = col
        elif elem.type != '':
            new_col = elem.name
        else:
            new_col = DEFAULT_GROUP_DELIMITER.join([
                elem.parent.name,
                elem.name
            ])
        new_columns.append(new_col)

    return new_columns


def write_to_csv(path, rows, columns, columns_with_hxl=None,
                 remove_group_name=False, dd=None,
                 group_delimiter=DEFAULT_GROUP_DELIMITER, include_labels=False,
                 include_labels_only=False, include_hxl=False,
                 win_excel_utf8=False):
    na_rep = getattr(settings, 'NA_REP', NA_REP)
    encoding = 'utf-8-sig' if win_excel_utf8 else 'utf-8'
    with open(path, 'wb') as csvfile:
        writer = csv.writer(csvfile, encoding=encoding, lineterminator='\n')

        # Check if to truncate the group name prefix
        if not include_labels_only:
            if remove_group_name and dd:
                new_cols = get_column_names_only(columns, dd, group_delimiter)
            else:
                new_cols = columns

            # use a different group delimiter if needed
            if group_delimiter != DEFAULT_GROUP_DELIMITER:
                new_cols = [
                    group_delimiter.join(col.split(DEFAULT_GROUP_DELIMITER))
                    for col in new_cols
                ]

            writer.writerow(new_cols)

        if include_labels or include_labels_only:
            labels = get_labels_from_columns(columns, dd, group_delimiter)
            writer.writerow(labels)

        if include_hxl and columns_with_hxl:
            hxl_row = [columns_with_hxl.get(col, '') for col in columns]
            hxl_row and writer.writerow(hxl_row)

        for row in rows:
            for col in AbstractDataFrameBuilder.IGNORED_COLUMNS:
                row.pop(col, None)
            writer.writerow([row.get(col, na_rep) for col in columns])


class AbstractDataFrameBuilder(object):
    IGNORED_COLUMNS = [XFORM_ID_STRING, STATUS, ID, ATTACHMENTS, GEOLOCATION,
                       BAMBOO_DATASET_ID, DELETEDAT, EDITED]
    # fields NOT within the form def that we want to include
    ADDITIONAL_COLUMNS = [
        UUID, SUBMISSION_TIME, TAGS, NOTES, VERSION, DURATION,
        SUBMITTED_BY]
    BINARY_SELECT_MULTIPLES = False
    """
    Group functionality used by any DataFrameBuilder i.e. XLS, CSV and KML
    """

    def __init__(self, username, id_string, filter_query=None,
                 group_delimiter=DEFAULT_GROUP_DELIMITER,
                 split_select_multiples=True, binary_select_multiples=False,
                 start=None, end=None, remove_group_name=False, xform=None,
                 include_labels=False, include_labels_only=False,
                 include_images=True, include_hxl=False,
                 win_excel_utf8=False):

        self.username = username
        self.id_string = id_string
        self.filter_query = filter_query
        self.group_delimiter = group_delimiter
        self.split_select_multiples = split_select_multiples
        self.BINARY_SELECT_MULTIPLES = binary_select_multiples
        self.start = start
        self.end = end
        self.remove_group_name = remove_group_name

        if xform:
            self.xform = xform
        else:
            self.xform = XForm.objects.get(id_string=self.id_string,
                                           user__username=self.username)
        self.include_labels = include_labels
        self.include_labels_only = include_labels_only
        self.include_images = include_images
        self.include_hxl = include_hxl
        self.win_excel_utf8 = win_excel_utf8
        self._setup()

    def _setup(self):
        self.dd = self.xform
        self.select_multiples = self._collect_select_multiples(self.dd)
        self.gps_fields = self._collect_gps_fields(self.dd)

    @classmethod
    def _fields_to_select(cls, dd):
        return [c.get_abbreviated_xpath()
                for c in dd.get_survey_elements() if isinstance(c, Question)]

    @classmethod
    def _collect_select_multiples(cls, dd):
        select_multiples = []
        select_multiple_elements = [
            e for e in dd.get_survey_elements_with_choices()
            if e.bind.get('type') == 'select'
        ]
        for e in select_multiple_elements:
            xpath = e.get_abbreviated_xpath()
            choices = [c.get_abbreviated_xpath() for c in e.children]
            if not choices and e.choice_filter and e.itemset:
                itemset = dd.survey.to_json_dict()['choices'].get(e.itemset)
                choices = [u'/'.join([xpath, i.get('name')])
                           for i in itemset] if itemset else choices
            select_multiples.append((xpath, choices))

        return dict(select_multiples)

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
        # query_data takes params as json strings
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
        count_object = list(query_data(**count_args))
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
            cursor = query_data(**query_args)
            return cursor


class CSVDataFrameBuilder(AbstractDataFrameBuilder):

    def __init__(self, username, id_string, filter_query=None,
                 group_delimiter=DEFAULT_GROUP_DELIMITER,
                 split_select_multiples=True, binary_select_multiples=False,
                 start=None, end=None, remove_group_name=False, xform=None,
                 include_labels=False, include_labels_only=False,
                 include_images=False, include_hxl=False,
                 win_excel_utf8=False):
        super(CSVDataFrameBuilder, self).__init__(
            username, id_string, filter_query, group_delimiter,
            split_select_multiples, binary_select_multiples, start, end,
            remove_group_name, xform, include_labels, include_labels_only,
            include_images, include_hxl, win_excel_utf8

        )
        self.ordered_columns = OrderedDict()

    def _setup(self):
        super(CSVDataFrameBuilder, self)._setup()

    @classmethod
    def _reindex(cls, key, value, ordered_columns, row, data_dictionary,
                 parent_prefix=None,
                 include_images=True):
        """
        Flatten list columns by appending an index, otherwise return as is
        """
        def get_ordered_repeat_value(xpath, repeat_value):
            children = data_dictionary.get_child_elements(xpath)
            item = OrderedDict()

            for elem in children:
                xp = elem.get_abbreviated_xpath()
                if xp in repeat_value:
                    item[xp] = repeat_value[xp]

            return item

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
                    # order repeat according to xform order
                    item = get_ordered_repeat_value(key, item)

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
                                ordered_columns, row, data_dictionary,
                                new_prefix,
                                include_images=include_images))
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
                            d[new_xpath] = get_value_or_attachment_uri(
                                nested_key, nested_val, row, data_dictionary,
                                include_images
                            )
                else:
                    d[key] = get_value_or_attachment_uri(
                        key, value, row, data_dictionary, include_images
                    )
        else:
            # anything that's not a list will be in the top level dict so its
            # safe to simply assign
            if key == NOTES:
                # Do not include notes
                d[key] = u""
            else:
                d[key] = get_value_or_attachment_uri(
                    key, value, row, data_dictionary, include_images
                )
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

    def _update_columns_from_data(self, cursor):
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
        image_xpaths = [] if not self.include_images \
            else self.dd.get_media_survey_xpaths()

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
            # re index repeats
            for key, value in record.iteritems():
                self._reindex(key, value, self.ordered_columns,
                              record, self.dd, include_images=image_xpaths)

    def _format_for_dataframe(self, cursor, key_replacement_obj=None):
        pattern = key_replacement_obj.get('pattern')
        replacer = key_replacement_obj.get('replacer')

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
        image_xpaths = [] if not self.include_images \
            else self.dd.get_media_survey_xpaths()

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
                _key = key
                if pattern and replacer:
                    _key = re.sub(pattern, replacer, _key)
                reindexed = self._reindex(_key, value, self.ordered_columns,
                                          record, self.dd,
                                          include_images=image_xpaths)
                flat_dict.update(reindexed)

            yield flat_dict

    def export_to(self, path, dataview=None):
        self.ordered_columns = OrderedDict()
        self._build_ordered_columns(self.dd.survey, self.ordered_columns)

        if dataview:
            cursor = dataview.query_data(dataview, all_data=True)
            if isinstance(cursor, QuerySet):
                cursor = cursor.iterator()
            self._update_columns_from_data(cursor)

            columns = list(chain.from_iterable(
                [[xpath] if cols is None else cols
                 for xpath, cols in self.ordered_columns.iteritems()
                 if [c for c in dataview.columns if xpath.startswith(c)]]
            ))
            cursor = dataview.query_data(dataview, all_data=True)
            if isinstance(cursor, QuerySet):
                cursor = cursor.iterator()
            data = self._format_for_dataframe(cursor)
        else:
            cursor = self._query_data(self.filter_query)
            if isinstance(cursor, QuerySet):
                cursor = cursor.iterator()
            self._update_columns_from_data(cursor)

            columns = list(chain.from_iterable(
                [[xpath] if cols is None else cols
                 for xpath, cols in self.ordered_columns.iteritems()]))

            # add extra columns
            columns += [col for col in self.ADDITIONAL_COLUMNS]
            for field in self.dd.get_survey_elements_of_type('osm'):
                columns += OsmData.get_tag_keys(self.xform,
                                                field.get_abbreviated_xpath(),
                                                include_prefix=True)
            cursor = self._query_data(self.filter_query)
            if isinstance(cursor, QuerySet):
                cursor = cursor.iterator()
            data = self._format_for_dataframe(cursor)

        columns_with_hxl = self.include_hxl and get_columns_with_hxl(
            self.dd.survey_elements)

        write_to_csv(path, data, columns,
                     columns_with_hxl=columns_with_hxl,
                     remove_group_name=self.remove_group_name,
                     dd=self.dd, group_delimiter=self.group_delimiter,
                     include_labels=self.include_labels,
                     include_labels_only=self.include_labels_only,
                     include_hxl=self.include_hxl,
                     win_excel_utf8=self.win_excel_utf8)
