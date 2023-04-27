# -*- coding: utf-8 -*-
"""
CSV export utility functions.
"""
from collections import OrderedDict
from itertools import chain

from django.conf import settings
from django.db.models.query import QuerySet
from django.utils.translation import gettext as _

import unicodecsv as csv
from pyxform.question import Question
from pyxform.section import RepeatingSection, Section
from six import iteritems

from onadata.apps.logger.models import OsmData
from onadata.apps.logger.models.xform import XForm, question_types_to_exclude
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.apps.viewer.models.parsed_instance import ParsedInstance, query_data
from onadata.libs.exceptions import NoRecordsFoundError
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
    MULTIPLE_SELECT_TYPE,
    NA_REP,
    NOTES,
    REVIEW_COMMENT,
    REVIEW_DATE,
    REVIEW_STATUS,
    SELECT_BIND_TYPE,
    STATUS,
    SUBMISSION_TIME,
    SUBMITTED_BY,
    TAGS,
    TOTAL_MEDIA,
    UUID,
    VERSION,
    XFORM_ID_STRING,
)
from onadata.libs.utils.common_tools import (
    get_choice_label,
    get_value_or_attachment_uri,
    str_to_bool,
    track_task_progress,
)
from onadata.libs.utils.model_tools import get_columns_with_hxl

# the bind type of select multiples that we use to compare
MULTIPLE_SELECT_BIND_TYPE = "select"
GEOPOINT_BIND_TYPE = "geopoint"

# column group delimiters
GROUP_DELIMITER_SLASH = "/"
GROUP_DELIMITER_DOT = "."
DEFAULT_GROUP_DELIMITER = GROUP_DELIMITER_SLASH
GROUP_DELIMITERS = [GROUP_DELIMITER_SLASH, GROUP_DELIMITER_DOT]
DEFAULT_NA_REP = getattr(settings, "NA_REP", NA_REP)

# index tags
DEFAULT_OPEN_TAG = "["
DEFAULT_CLOSE_TAG = "]"
DEFAULT_INDEX_TAGS = (DEFAULT_OPEN_TAG, DEFAULT_CLOSE_TAG)

YES = 1
NO = 0


# pylint: disable=invalid-name
def remove_dups_from_list_maintain_order(lst):
    """Removes duplicates from a list and still maintains the order."""
    return list(OrderedDict.fromkeys(lst))


def get_prefix_from_xpath(xpath):
    """Returns xpath prefix."""
    xpath = str(xpath)
    parts = xpath.rsplit("/", 1)
    if len(parts) == 1:
        return None
    if len(parts) == 2:
        return f"{parts[0]}/"
    raise ValueError(f"{xpath} cannot be prefixed, it returns {str(parts)}")


def get_labels_from_columns(columns, data_dictionary, group_delimiter, language=None):
    """Return ``column`` labels"""
    labels = []
    for col in columns:
        elem = data_dictionary.get_survey_element(col)
        label = (
            data_dictionary.get_label(col, elem=elem, language=language)
            if elem
            else col
        )
        if elem is not None and elem.type == "":
            label = group_delimiter.join([elem.parent.name, label])
        if label == "":
            label = elem.name
        labels.append(label)

    return labels


# pylint: disable=unused-argument
def get_column_names_only(columns, data_dictionary, group_delimiter):
    """Return column names as a list."""
    new_columns = []
    for col in columns:
        new_col = None
        elem = data_dictionary.get_survey_element(col)
        if elem is None:
            if any(
                col.endswith(gps_meta)
                for gps_meta in ["_latitude", "_longitude", "_altitude", "_precision"]
            ):
                new_col = col.split(group_delimiter)[-1]
            else:
                new_col = col
        elif elem.type != "":
            new_col = elem.name
        else:
            new_col = DEFAULT_GROUP_DELIMITER.join([elem.parent.name, elem.name])
        new_columns.append(new_col)

    return new_columns


# pylint: disable=unused-argument,too-many-arguments,too-many-locals
def write_to_csv(
    path,
    rows,
    columns,
    columns_with_hxl=None,
    remove_group_name=False,
    data_dictionary=None,
    group_delimiter=DEFAULT_GROUP_DELIMITER,
    include_labels=False,
    include_labels_only=False,
    include_hxl=False,
    win_excel_utf8=False,
    total_records=None,
    index_tags=DEFAULT_INDEX_TAGS,
    language=None,
):
    """Writes ``rows`` to a file in CSV format."""
    na_rep = getattr(settings, "NA_REP", NA_REP)
    encoding = "utf-8-sig" if win_excel_utf8 else "utf-8"
    with open(path, "wb") as csvfile:
        writer = csv.writer(csvfile, encoding=encoding, lineterminator="\n")

        # Check if to truncate the group name prefix
        if not include_labels_only:
            if remove_group_name and data_dictionary:
                new_cols = get_column_names_only(
                    columns, data_dictionary, group_delimiter
                )
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
            labels = get_labels_from_columns(
                columns, data_dictionary, group_delimiter, language=language
            )
            writer.writerow(labels)

        if include_hxl and columns_with_hxl:
            hxl_row = [columns_with_hxl.get(col, "") for col in columns]
            if hxl_row:
                writer.writerow(hxl_row)

        for i, row in enumerate(rows, start=1):
            for col in AbstractDataFrameBuilder.IGNORED_COLUMNS:
                row.pop(col, None)
            writer.writerow([row.get(col, na_rep) for col in columns])
            track_task_progress(i, total_records)


# pylint: disable=too-few-public-methods,too-many-instance-attributes
class AbstractDataFrameBuilder:
    """
    Abstract Data Frame Builder class
    """

    IGNORED_COLUMNS = [
        XFORM_ID_STRING,
        STATUS,
        ATTACHMENTS,
        GEOLOCATION,
        BAMBOO_DATASET_ID,
        DELETEDAT,
        EDITED,
    ]
    # fields NOT within the form def that we want to include
    ADDITIONAL_COLUMNS = [
        ID,
        UUID,
        SUBMISSION_TIME,
        DATE_MODIFIED,
        TAGS,
        NOTES,
        VERSION,
        DURATION,
        SUBMITTED_BY,
        TOTAL_MEDIA,
        MEDIA_COUNT,
        MEDIA_ALL_RECEIVED,
    ]
    BINARY_SELECT_MULTIPLES = False
    VALUE_SELECT_MULTIPLES = False
    """
    Group functionality used by any DataFrameBuilder i.e. XLS, CSV and KML
    """

    # pylint: disable=too-many-arguments,too-many-locals
    def __init__(
        self,
        username,
        id_string,
        filter_query=None,
        group_delimiter=DEFAULT_GROUP_DELIMITER,
        split_select_multiples=True,
        binary_select_multiples=False,
        start=None,
        end=None,
        remove_group_name=False,
        xform=None,
        include_labels=False,
        include_labels_only=False,
        include_images=True,
        include_hxl=False,
        win_excel_utf8=False,
        total_records=None,
        index_tags=DEFAULT_INDEX_TAGS,
        value_select_multiples=False,
        show_choice_labels=True,
        include_reviews=False,
        language=None,
    ):

        self.username = username
        self.id_string = id_string
        self.filter_query = filter_query
        self.group_delimiter = group_delimiter
        self.split_select_multiples = split_select_multiples
        # pylint: disable=invalid-name
        self.BINARY_SELECT_MULTIPLES = binary_select_multiples
        self.VALUE_SELECT_MULTIPLES = value_select_multiples
        self.start = start
        self.end = end
        self.remove_group_name = remove_group_name
        self.extra_columns = self.ADDITIONAL_COLUMNS + getattr(
            settings, "EXTRA_COLUMNS", []
        )

        if include_reviews:
            self.extra_columns = self.extra_columns + [
                REVIEW_STATUS,
                REVIEW_COMMENT,
                REVIEW_DATE,
            ]

        if xform:
            self.xform = xform
        else:
            self.xform = XForm.objects.get(
                id_string=self.id_string, user__username=self.username
            )
        self.include_labels = include_labels
        self.include_labels_only = include_labels_only
        self.include_images = include_images
        self.include_hxl = include_hxl
        self.win_excel_utf8 = win_excel_utf8
        self.total_records = total_records
        if index_tags != DEFAULT_INDEX_TAGS and not isinstance(
            index_tags, (tuple, list)
        ):
            raise ValueError(
                _(
                    f"Invalid option for repeat_index_tags: {index_tags} "
                    "expecting a tuple with opening and closing tags "
                    "e.g repeat_index_tags=('[', ']')"
                )
            )
        self.index_tags = index_tags
        self.show_choice_labels = show_choice_labels
        self.language = language

        self._setup()

    def _setup(self):
        self.data_dictionary = self.xform
        self.select_multiples = self._collect_select_multiples(
            self.data_dictionary, self.language
        )
        self.gps_fields = self._collect_gps_fields(self.data_dictionary)

    @classmethod
    def _fields_to_select(cls, data_dictionary):
        return [
            c.get_abbreviated_xpath()
            for c in data_dictionary.get_survey_elements()
            if isinstance(c, Question)
        ]

    @classmethod
    def _collect_select_multiples(cls, data_dictionary, language=None):
        select_multiples = []
        select_multiple_elements = [
            e
            for e in data_dictionary.get_survey_elements_with_choices()
            if e.bind.get("type") == SELECT_BIND_TYPE and e.type == MULTIPLE_SELECT_TYPE
        ]
        for e in select_multiple_elements:
            xpath = e.get_abbreviated_xpath()
            choices = [
                (
                    c.get_abbreviated_xpath(),
                    c.name,
                    get_choice_label(c.label, data_dictionary, language),
                )
                for c in e.children
            ]
            is_choice_randomized = str_to_bool(
                e.parameters and e.parameters.get("randomize")
            )
            if (
                (not choices and e.choice_filter) or is_choice_randomized
            ) and e.itemset:
                itemset = data_dictionary.survey.to_json_dict()["choices"].get(
                    e.itemset
                )
                choices = (
                    [
                        (
                            "/".join([xpath, i.get("name")]),
                            i.get("name"),
                            get_choice_label(i.get("label"), data_dictionary, language),
                        )
                        for i in itemset
                    ]
                    if itemset
                    else choices
                )
            select_multiples.append((xpath, choices))

        return dict(select_multiples)

    # pylint: disable=too-many-arguments
    @classmethod
    def _split_select_multiples(
        cls,
        record,
        select_multiples,
        binary_select_multiples=False,
        value_select_multiples=False,
        show_choice_labels=False,
    ):
        """Prefix contains the xpath and slash if we are within a repeat so
        that we can figure out which select multiples belong to which repeat
        """
        for key, choices in select_multiples.items():
            # the select multiple might be blank or not exist in the record,
            # need to make those False
            selections = []
            if key in record:
                # split selected choices by spaces and join by / to the
                # element's xpath
                selections = [f"{key}/{r}" for r in record[key].split(" ")]
                if value_select_multiples:
                    record.update(
                        {
                            choice.replace("/" + name, "/" + label)
                            if show_choice_labels
                            else choice: (
                                label
                                if show_choice_labels
                                else record[key].split()[selections.index(choice)]
                            )
                            if choice in selections
                            else None
                            for choice, name, label in choices
                        }
                    )
                elif not binary_select_multiples:
                    # add columns to record for every choice, with default
                    # False and set to True for items in selections
                    record.update(
                        {
                            choice.replace("/" + name, "/" + label)
                            if show_choice_labels
                            else choice: choice in selections
                            for choice, name, label in choices
                        }
                    )
                else:
                    record.update(
                        {
                            choice.replace("/" + name, "/" + label)
                            if show_choice_labels
                            else choice: YES
                            if choice in selections
                            else NO
                            for choice, name, label in choices
                        }
                    )
                # remove the column since we are adding separate columns
                # for each choice
                record.pop(key)

            # recurs into repeats
            for _record_key, record_item in record.items():
                if isinstance(record_item, list):
                    for list_item in record_item:
                        if isinstance(list_item, dict):
                            cls._split_select_multiples(
                                list_item,
                                select_multiples,
                                binary_select_multiples=binary_select_multiples,  # noqa
                                value_select_multiples=value_select_multiples,
                                show_choice_labels=show_choice_labels,
                            )
        return record

    @classmethod
    def _collect_gps_fields(cls, data_dictionary):
        return [
            e.get_abbreviated_xpath()
            for e in data_dictionary.get_survey_elements()
            if e.bind.get("type") == "geopoint"
        ]

    @classmethod
    def _tag_edit_string(cls, record):
        """
        Turns a list of tags into a string representation.
        """
        if "_tags" in record:
            tags = []
            for tag in record["_tags"]:
                if "," in tag and " " in tag:
                    tags.append(f'"{tag}"')
                else:
                    tags.append(tag)
            record.update({"_tags": ", ".join(sorted(tags))})

    @classmethod
    def _split_gps_fields(cls, record, gps_fields):
        updated_gps_fields = {}
        for (key, value) in iteritems(record):
            if key in gps_fields and isinstance(value, str):
                gps_xpaths = DataDictionary.get_additional_geopoint_xpaths(key)
                gps_parts = {xpath: None for xpath in gps_xpaths}
                # hack, check if its a list and grab the object within that
                parts = value.split(" ")
                if len(parts) == 4:
                    gps_parts = dict(zip(gps_xpaths, parts))
                updated_gps_fields.update(gps_parts)
            # check for repeats within record i.e. in value
            elif isinstance(value, list):
                for list_item in value:
                    if isinstance(list_item, dict):
                        cls._split_gps_fields(list_item, gps_fields)
        record.update(updated_gps_fields)

    # pylint: disable=too-many-arguments
    def _query_data(
        self,
        query="{}",
        start=0,
        limit=ParsedInstance.DEFAULT_LIMIT,
        fields="[]",
        count=False,
    ):
        # query_data takes params as json strings
        # so we dumps the fields dictionary
        count_args = {
            "xform": self.xform,
            "query": query,
            "start": self.start,
            "end": self.end,
            "fields": "[]",
            "sort": "{}",
            "count": True,
        }
        count_object = list(query_data(**count_args))
        record_count = count_object[0]["count"]
        if record_count < 1:
            raise NoRecordsFoundError("No records found for your query")
        # if count was requested, return the count
        if count:
            return record_count

        query_args = {
            "xform": self.xform,
            "query": query,
            "fields": fields,
            "start": self.start,
            "end": self.end,
            "sort": "id",
            "start_index": start,
            "limit": limit,
            "count": False,
        }
        cursor = query_data(**query_args)

        return cursor


# pylint: disable=too-few-public-methods
class CSVDataFrameBuilder(AbstractDataFrameBuilder):
    """CSV data frame builder"""

    # pylint: disable=too-many-arguments,too-many-locals
    def __init__(
        self,
        username,
        id_string,
        filter_query=None,
        group_delimiter=DEFAULT_GROUP_DELIMITER,
        split_select_multiples=True,
        binary_select_multiples=False,
        start=None,
        end=None,
        remove_group_name=False,
        xform=None,
        include_labels=False,
        include_labels_only=False,
        include_images=False,
        include_hxl=False,
        win_excel_utf8=False,
        total_records=None,
        index_tags=DEFAULT_INDEX_TAGS,
        value_select_multiples=False,
        show_choice_labels=False,
        include_reviews=False,
        language=None,
    ):

        super().__init__(
            username,
            id_string,
            filter_query,
            group_delimiter,
            split_select_multiples,
            binary_select_multiples,
            start,
            end,
            remove_group_name,
            xform,
            include_labels,
            include_labels_only,
            include_images,
            include_hxl,
            win_excel_utf8,
            total_records,
            index_tags,
            value_select_multiples,
            show_choice_labels,
            include_reviews,
            language,
        )

        self.ordered_columns = OrderedDict()
        self.image_xpaths = (
            []
            if not self.include_images
            else self.data_dictionary.get_media_survey_xpaths()
        )

    # pylint: disable=too-many-arguments,too-many-branches,too-many-locals
    @classmethod
    def _reindex(
        cls,
        key,
        value,
        ordered_columns,
        row,
        data_dictionary,
        parent_prefix=None,
        include_images=True,
        split_select_multiples=True,
        index_tags=DEFAULT_INDEX_TAGS,
        show_choice_labels=False,
        language=None,
    ):
        """
        Flatten list columns by appending an index, otherwise return as is
        """

        def get_ordered_repeat_value(xpath, repeat_value):
            """
            Return OrderedDict of repeats in the order in which they appear in
            the XForm.
            """
            children = data_dictionary.get_child_elements(xpath, split_select_multiples)
            item = OrderedDict()

            for elem in children:
                if not question_types_to_exclude(elem.type):
                    abbreviated_xpath = elem.get_abbreviated_xpath()
                    item[abbreviated_xpath] = repeat_value.get(
                        abbreviated_xpath, DEFAULT_NA_REP
                    )

            return item

        record = {}

        # check for lists
        # pylint: disable=too-many-nested-blocks
        if isinstance(value, list) and value and key not in [ATTACHMENTS, NOTES]:
            for index, item in enumerate(value):
                # start at 1
                index += 1
                # for each list check for dict, we want to transform the key of
                # this dict
                if isinstance(item, dict):
                    # order repeat according to xform order
                    _item = get_ordered_repeat_value(key, item)
                    if key in _item and _item[key] == "n/a":
                        # See https://github.com/onaio/zebra/issues/6830
                        # handles the case of a repeat construct in the data but the
                        # form has no repeat construct defined using begin repeat for
                        # example when you have a hidden value that has a repeat_count
                        # set within a group.
                        _item = item

                    for (nested_key, nested_val) in iteritems(_item):
                        # given the key "children/details" and nested_key/
                        # abbreviated xpath
                        # "children/details/immunization/polio_1",
                        # generate ["children", index, "immunization/polio_1"]
                        if parent_prefix is not None:
                            _key = "/".join(
                                parent_prefix + key.split("/")[len(parent_prefix) :]
                            )
                            xpaths = [
                                f"{_key}{index_tags[0]}{index}{index_tags[1]}"
                            ] + nested_key.split("/")[len(_key.split("/")) :]
                        else:
                            xpaths = [
                                f"{key}{index_tags[0]}{index}{index_tags[1]}"
                            ] + nested_key.split("/")[len(key.split("/")) :]
                        # re-create xpath the split on /
                        xpaths = "/".join(xpaths).split("/")
                        new_prefix = xpaths[:-1]
                        if isinstance(nested_val, list):
                            # if nested_value is a list, rinse and repeat
                            record.update(
                                cls._reindex(
                                    nested_key,
                                    nested_val,
                                    ordered_columns,
                                    row,
                                    data_dictionary,
                                    new_prefix,
                                    include_images=include_images,
                                    split_select_multiples=split_select_multiples,
                                    index_tags=index_tags,
                                    show_choice_labels=show_choice_labels,
                                    language=language,
                                )
                            )
                        else:
                            # it can only be a scalar
                            # collapse xpath
                            new_xpath = "/".join(xpaths)
                            # check if this key exists in our ordered columns
                            if key in list(ordered_columns):
                                try:
                                    if new_xpath not in ordered_columns[key]:
                                        ordered_columns[key].append(new_xpath)
                                except TypeError:
                                    ordered_columns[key] = [new_xpath]
                            record[new_xpath] = get_value_or_attachment_uri(
                                nested_key,
                                nested_val,
                                row,
                                data_dictionary,
                                include_images,
                                show_choice_labels=show_choice_labels,
                                language=language,
                            )
                else:
                    record[key] = get_value_or_attachment_uri(
                        key,
                        value,
                        row,
                        data_dictionary,
                        include_images,
                        show_choice_labels=show_choice_labels,
                        language=language,
                    )
        else:
            # anything that's not a list will be in the top level dict so its
            # safe to simply assign
            if key == NOTES:
                # Do not include notes
                record[key] = ""
            else:
                record[key] = get_value_or_attachment_uri(
                    key,
                    value,
                    row,
                    data_dictionary,
                    include_images,
                    show_choice_labels=show_choice_labels,
                    language=language,
                )
        return record

    @classmethod
    def _build_ordered_columns(
        cls, survey_element, ordered_columns, is_repeating_section=False
    ):
        """
        Build a flat ordered dict of column groups

        is_repeating_section ensures that child questions of repeating sections
        are not considered columns
        """
        for child in survey_element.children:
            if isinstance(child, Section):
                child_is_repeating = False
                if isinstance(child, RepeatingSection):
                    ordered_columns[child.get_abbreviated_xpath()] = []
                    child_is_repeating = True
                cls._build_ordered_columns(child, ordered_columns, child_is_repeating)
            elif (
                isinstance(child, Question)
                and not question_types_to_exclude(child.type)
                and not is_repeating_section
            ):  # if is_repeating_section,
                # its parent already initiliased an empty list
                # so we dont add it to our list of columns,
                # the repeating columns list will be
                # generated when we reindex
                ordered_columns[child.get_abbreviated_xpath()] = None

    def _update_ordered_columns_from_data(self, cursor):
        """
        Populates `self.ordered_columns` object that is
        used to generate export column headers for
        forms that split select multiple and gps data.
        """
        # add ordered columns for select multiples
        if self.split_select_multiples:
            for (key, choices) in iteritems(self.select_multiples):
                # HACK to ensure choices are NOT duplicated
                if key in self.ordered_columns.keys():
                    self.ordered_columns[key] = remove_dups_from_list_maintain_order(
                        [
                            choice.replace("/" + name, "/" + label)
                            if self.show_choice_labels
                            else choice
                            for choice, name, label in choices
                        ]
                    )

        # add ordered columns for gps fields
        for key in self.gps_fields:
            gps_xpaths = self.data_dictionary.get_additional_geopoint_xpaths(key)
            self.ordered_columns[key] = [key] + gps_xpaths

        # add ordered columns for nested repeat data
        for record in cursor:
            # re index column repeats
            for (key, value) in iteritems(record):
                self._reindex(
                    key,
                    value,
                    self.ordered_columns,
                    record,
                    self.data_dictionary,
                    include_images=self.image_xpaths,
                    split_select_multiples=self.split_select_multiples,
                    index_tags=self.index_tags,
                    show_choice_labels=self.show_choice_labels,
                    language=self.language,
                )

    def _format_for_dataframe(self, cursor):
        """
        Unpacks nested repeat data for export.
        """
        for record in cursor:
            # split select multiples
            if self.split_select_multiples:
                record = self._split_select_multiples(
                    record,
                    self.select_multiples,
                    self.BINARY_SELECT_MULTIPLES,
                    self.VALUE_SELECT_MULTIPLES,
                    show_choice_labels=self.show_choice_labels,
                )
            # check for gps and split into
            # components i.e. latitude, longitude,
            # altitude, precision
            self._split_gps_fields(record, self.gps_fields)
            self._tag_edit_string(record)
            flat_dict = {}
            # re index repeats
            for (key, value) in iteritems(record):
                reindexed = self._reindex(
                    key,
                    value,
                    self.ordered_columns,
                    record,
                    self.data_dictionary,
                    include_images=self.image_xpaths,
                    split_select_multiples=self.split_select_multiples,
                    index_tags=self.index_tags,
                    show_choice_labels=self.show_choice_labels,
                    language=self.language,
                )
                flat_dict.update(reindexed)
            yield flat_dict

    def export_to(self, path, dataview=None):
        """Export a CSV formated to the given ``path``."""
        self.ordered_columns = OrderedDict()
        self._build_ordered_columns(self.data_dictionary.survey, self.ordered_columns)

        if dataview:
            cursor = dataview.query_data(
                dataview, all_data=True, filter_query=self.filter_query
            )
            if isinstance(cursor, QuerySet):
                cursor = cursor.iterator()

            self._update_ordered_columns_from_data(cursor)

            data = self._format_for_dataframe(cursor)

            columns = list(
                chain.from_iterable(
                    [
                        [xpath] if cols is None else cols
                        for (xpath, cols) in iteritems(self.ordered_columns)
                        if [c for c in dataview.columns if xpath.startswith(c)]
                    ]
                )
            )
        else:
            try:
                cursor = self._query_data(self.filter_query)
            except NoRecordsFoundError:
                # Set cursor object to an an empty queryset
                cursor = self.xform.instances.none()

            self._update_ordered_columns_from_data(cursor)

            if isinstance(cursor, QuerySet):
                cursor = cursor.iterator()

            # Unpack xform columns and data
            data = self._format_for_dataframe(cursor)

            columns = list(
                chain.from_iterable(
                    [
                        [xpath] if cols is None else cols
                        for (xpath, cols) in iteritems(self.ordered_columns)
                    ]
                )
            )

            # add extra columns
            columns += list(self.extra_columns)

            for field in self.data_dictionary.get_survey_elements_of_type("osm"):
                columns += OsmData.get_tag_keys(
                    self.xform, field.get_abbreviated_xpath(), include_prefix=True
                )

        columns_with_hxl = self.include_hxl and get_columns_with_hxl(
            self.data_dictionary.survey_elements
        )

        write_to_csv(
            path,
            data,
            columns,
            columns_with_hxl=columns_with_hxl,
            remove_group_name=self.remove_group_name,
            data_dictionary=self.data_dictionary,
            group_delimiter=self.group_delimiter,
            include_labels=self.include_labels,
            include_labels_only=self.include_labels_only,
            include_hxl=self.include_hxl,
            win_excel_utf8=self.win_excel_utf8,
            total_records=self.total_records,
            index_tags=self.index_tags,
            language=self.language,
        )
