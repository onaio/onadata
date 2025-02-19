# pylint: disable=too-many-lines
# -*- coding: utf-8 -*-
"""
ExportBuilder
"""

from __future__ import unicode_literals

import csv
import re
import uuid
from datetime import date, datetime
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.core.files.temp import NamedTemporaryFile

from openpyxl.utils.datetime import to_excel
from openpyxl.workbook import Workbook
from pyxform.question import Option, Question
from pyxform.section import RepeatingSection, Section
from savReaderWriter import SavWriter  # pylint: disable=no-name-in-module
from six import iteritems

from onadata.apps.logger.models.osmdata import OsmData
from onadata.apps.logger.models.xform import (
    QUESTION_TYPES_TO_EXCLUDE,
    _encode_for_mongo,
)
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.libs.utils.common_tags import (
    ATTACHMENTS,
    BAMBOO_DATASET_ID,
    DELETEDAT,
    DURATION,
    GEOLOCATION,
    ID,
    INDEX,
    MULTIPLE_SELECT_TYPE,
    NOTES,
    PARENT_INDEX,
    PARENT_TABLE_NAME,
    REPEAT_INDEX_TAGS,
    REVIEW_COMMENT,
    REVIEW_DATE,
    REVIEW_STATUS,
    SAV_255_BYTES_TYPE,
    SAV_NUMERIC_TYPE,
    SELECT_BIND_TYPE,
    SELECT_ONE,
    STATUS,
    SUBMISSION_TIME,
    SUBMITTED_BY,
    TAGS,
    UUID,
    VERSION,
    XFORM_ID_STRING,
)
from onadata.libs.utils.common_tools import (
    get_abbreviated_xpath,
    get_choice_label,
    get_choice_label_value,
    get_value_or_attachment_uri,
    str_to_bool,
    track_task_progress,
)
from onadata.libs.utils.mongo import _decode_from_mongo, _is_invalid_for_mongo

# the bind type of select multiples that we use to compare
GEOPOINT_BIND_TYPE = "geopoint"
OSM_BIND_TYPE = "osm"

YES = 1
NO = 0


def get_data_dictionary_from_survey(survey):
    """Creates a DataDictionary instance from an XML survey instance."""
    data_dicionary = DataDictionary()
    # pylint: disable=protected-access
    data_dicionary._survey = survey

    return data_dicionary


def encode_if_str(row, key, encode_dates=False, sav_writer=None):
    """Encode a string value in ``row[key]``."""
    val = row.get(key)
    if isinstance(val, (datetime, date)):
        if sav_writer:
            if isinstance(val, datetime):
                if val.isoformat():
                    strptime_fmt = "%Y-%m-%dT%H:%M:%S"
                else:
                    strptime_fmt = "%Y-%m-%dT%H:%M:%S.%f%z"
            else:
                strptime_fmt = "%Y-%m-%d"
            return sav_writer.spssDateTime(
                val.isoformat().encode("utf-8"), strptime_fmt
            )
        if encode_dates:
            return val.isoformat()

    if sav_writer:
        val = "" if val is None else val
        return str(val) if not isinstance(val, bool) else val
    return val


# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
# pylint: disable=too-many-nested-blocks,too-many-branches
def dict_to_joined_export(
    data, index, indices, name, survey, row, host, media_xpaths=None
):
    """
    Converts a dict into one or more tabular datasets
    :param data: current record which can be changed or updated
    :param index: keeps count of record number
    :param indices: a dictionary storing list values if data is a dict
    :param name: the name of the survey
    :param survey: the survey
    :param row: current record that remains unchanged on this function's recall
    """
    output = {}
    media_xpaths = [] if media_xpaths is None else media_xpaths
    if isinstance(data, dict):
        for key, val in iteritems(data):
            if isinstance(val, list) and key not in [NOTES, ATTACHMENTS, TAGS]:
                output[key] = []
                for child in val:
                    if key not in indices:
                        indices[key] = 0
                    indices[key] += 1
                    child_index = indices[key]
                    new_output = dict_to_joined_export(
                        child,
                        child_index,
                        indices,
                        key,
                        survey,
                        row,
                        host,
                        media_xpaths,
                    )
                    item = {
                        INDEX: child_index,
                        PARENT_INDEX: index,
                        PARENT_TABLE_NAME: name,
                    }
                    # iterate over keys within new_output and append to
                    # main output
                    for out_key, out_val in iteritems(new_output):
                        if isinstance(out_val, list):
                            if out_key not in output:
                                output[out_key] = []
                            output[out_key].extend(out_val)
                        else:
                            item.update(out_val)
                    output[key].append(item)
            else:
                if name not in output:
                    output[name] = {}
                if key in [TAGS]:
                    output[name][key] = ",".join(val)
                elif key in [NOTES]:
                    note_list = [v if isinstance(v, str) else v["note"] for v in val]
                    output[name][key] = "\r\n".join(note_list)
                else:
                    data_dictionary = get_data_dictionary_from_survey(survey)
                    output[name][key] = get_value_or_attachment_uri(
                        key,
                        val,
                        data,
                        data_dictionary,
                        media_xpaths,
                        row and row.get(ATTACHMENTS),
                        host=host,
                    )

    return output


def is_all_numeric(items):
    """Check if all items on the list are numeric, zero padded numbers will not
    be considered as numeric.

    :param items: list of values to be checked

    :return boolean:
    """
    try:
        for i in items:
            float(i)
            # if there is a zero padded number, it is not all numeric
            if isinstance(i, str) and len(i) > 1 and i[0] == "0" and i[1] != ".":
                return False
        return True
    except ValueError:
        return False

    # check for zero padded numbers to be treated as non numeric
    return not (
        any(
            i.startswith("0") and len(i) > 1 and i.find(".") == -1
            for i in items
            if isinstance(i, str)
        )
    )


# pylint: disable=invalid-name
def string_to_date_with_xls_validation(date_str):
    """Try to convert a string to a date object.

    :param date_str: string to convert
    :returns: object if converted, otherwise date string
    """
    if not isinstance(date_str, str):
        return date_str

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        to_excel(date_obj)
    except ValueError:
        return date_str
    return date_obj


# pylint: disable=invalid-name
def decode_mongo_encoded_section_names(data):
    """Recursively decode mongo keys.

    :param data: A dictionary to decode.
    """
    results = {}
    for k, v in iteritems(data):
        new_v = v
        if isinstance(v, dict):
            new_v = decode_mongo_encoded_section_names(v)
        elif isinstance(v, list):
            new_v = [
                decode_mongo_encoded_section_names(x) if isinstance(x, dict) else x
                for x in v
            ]
        results[_decode_from_mongo(k)] = new_v
    return results


def _check_sav_column(column, columns):
    """
    Check for duplicates and append @ 4 chars uuid.
    Also checks for column length more than 64 chars
    :param column:
    :return: truncated column
    """

    if len(column) > 64:
        col_len_diff = len(column) - 64
        column = column[:-col_len_diff]

    if column.lower() in (t.lower() for t in columns):
        if len(column) > 59:
            column = column[:-5]
        column = column + "@" + str(uuid.uuid4()).split("-")[1]

    return column


def _get_var_name(title, var_names):
    """
    GET valid SPSS varName.
    @param title - survey element title/name
    @param var_names - list of existing var_names
    @return valid varName and list of var_names with new var name appended
    """
    var_name = (
        title.replace("/", ".")
        .replace("-", "_")
        .replace(":", "_")
        .replace("{", "")
        .replace("}", "")
    )
    var_name = _check_sav_column(var_name, var_names)
    var_name = "@" + var_name if var_name.startswith("_") else var_name
    var_names.append(var_name)
    return var_name, var_names


# pylint: disable=too-many-instance-attributes
class ExportBuilder:
    """Utility class for generating multiple formats of data export to file."""

    IGNORED_COLUMNS = [
        XFORM_ID_STRING,
        STATUS,
        ATTACHMENTS,
        GEOLOCATION,
        BAMBOO_DATASET_ID,
        DELETEDAT,
    ]
    # fields we export but are not within the form's structure
    EXTRA_FIELDS = [
        ID,
        UUID,
        SUBMISSION_TIME,
        INDEX,
        PARENT_TABLE_NAME,
        PARENT_INDEX,
        TAGS,
        NOTES,
        VERSION,
        DURATION,
        SUBMITTED_BY,
    ]
    SPLIT_SELECT_MULTIPLES = True
    BINARY_SELECT_MULTIPLES = False
    VALUE_SELECT_MULTIPLES = False

    # column group delimiters get_value_or_attachment_uri
    GROUP_DELIMITER_SLASH = "/"
    GROUP_DELIMITER_DOT = "."
    GROUP_DELIMITER = GROUP_DELIMITER_SLASH
    GROUP_DELIMITERS = [GROUP_DELIMITER_SLASH, GROUP_DELIMITER_DOT]

    # index tags
    REPEAT_INDEX_TAGS = ("[", "]")

    INCLUDE_LABELS = False
    INCLUDE_LABELS_ONLY = False
    INCLUDE_HXL = False
    INCLUDE_IMAGES = settings.EXPORT_WITH_IMAGE_DEFAULT

    SHOW_CHOICE_LABELS = False
    INCLUDE_REVIEWS = False

    TYPES_TO_CONVERT = ["int", "decimal", "date"]  # , 'dateTime']
    CONVERT_FUNCS = {
        "int": int,
        "decimal": float,
        "date": string_to_date_with_xls_validation,
        "dateTime": lambda x: datetime.strptime(x[:19], "%Y-%m-%dT%H:%M:%S"),
    }

    TRUNCATE_GROUP_TITLE = False

    XLS_SHEET_NAME_MAX_CHARS = 31
    url = None
    language = None

    def __init__(self):
        self.extra_columns = self.EXTRA_FIELDS + getattr(settings, "EXTRA_COLUMNS", [])
        self.osm_columns = []

    @classmethod
    def format_field_title(
        cls,
        abbreviated_xpath,
        field_delimiter,
        data_dictionary,
        remove_group_name=False,
        gps_extra_field=False,
    ):
        """Format the field title."""
        title = abbreviated_xpath
        # Check if to truncate the group name prefix
        if remove_group_name:
            if gps_extra_field:
                title = title.split(field_delimiter)[-1]
            else:
                elem = data_dictionary.get_survey_element(abbreviated_xpath)
                # incase abbreviated_xpath is a choices xpath
                if elem is None:
                    pass
                elif isinstance(elem, Option):
                    parent = data_dictionary.get_survey_element(
                        field_delimiter.join(
                            abbreviated_xpath.split(field_delimiter)[:-1]
                        )
                    )
                    title = field_delimiter.join([parent.name, elem.name])
                else:
                    title = elem.name

        if field_delimiter != "/" and "/" in title:
            title = field_delimiter.join(title.split("/"))
        return title

    def get_choice_label_from_dict(self, label):
        """Returns the choice label for the default language

        If a label for the target language is blank then the default
        language is used
        """
        if isinstance(label, dict):
            default_language = self.get_default_language(list(label))
            default_label = label.get(default_language)

            if self.language:
                return label.get(self.language, default_label)

            return default_label

        return label

    def _get_select_mulitples_choices(
        self, child, data_dicionary, field_delimiter, remove_group_name
    ):
        def get_choice_dict(xpath, label):
            title = ExportBuilder.format_field_title(
                xpath, field_delimiter, data_dicionary, remove_group_name
            )

            return {
                "label": field_delimiter.join([child.name, label or title]),
                "_label": label or title,
                "_label_xpath": field_delimiter.join([child.name, label or title]),
                "title": title,
                "xpath": xpath,
                "type": "string",
            }

        choices = []
        is_choice_randomized = str_to_bool(
            child.parameters and child.parameters.get("randomize")
        )
        if (
            (
                (hasattr(child, "children") and not child.children)
                and child.choice_filter
            )
            or is_choice_randomized
        ) and child.itemset:
            itemset = data_dicionary.survey.to_json_dict()["choices"].get(child.itemset)
            choices = (
                [
                    get_choice_dict(
                        "/".join([get_abbreviated_xpath(child.get_xpath()), i["name"]]),
                        self.get_choice_label_from_dict(i["label"]),
                    )
                    for i in itemset
                ]
                if itemset
                else choices
            )
        else:
            choices = [
                get_choice_dict(
                    get_abbreviated_xpath("/".join([child.get_xpath(), c.name])),
                    get_choice_label(c.label, data_dicionary, language=self.language),
                )
                for c in child.choices.options
            ]

        return choices

    # pylint: disable=too-many-statements
    def set_survey(self, survey, xform=None, include_reviews=False):
        """Set's the XForm XML ``survey`` instance."""
        if self.INCLUDE_REVIEWS or include_reviews:
            # pylint: disable=invalid-name
            self.EXTRA_FIELDS = self.EXTRA_FIELDS + [
                REVIEW_STATUS,
                REVIEW_COMMENT,
                REVIEW_DATE,
            ]
            self.__init__()  # pylint: disable=unnecessary-dunder-call
        data_dicionary = get_data_dictionary_from_survey(survey)

        # pylint: disable=too-many-arguments,too-many-positional-arguments
        def build_sections(
            current_section,
            survey_element,
            sections,
            select_multiples,
            gps_fields,
            osm_fields,
            encoded_fields,
            select_ones,
            field_delimiter="/",
            remove_group_name=False,
            language=None,
        ):
            # pylint: disable=too-many-nested-blocks,too-many-branches
            # pylint: disable=too-many-locals
            for child in survey_element.children:
                current_section_name = current_section["name"]
                # if a section, recurs
                if isinstance(child, Section):
                    # if its repeating, build a new section
                    if isinstance(child, RepeatingSection):
                        # section_name in recursive call changes
                        section = {
                            "name": get_abbreviated_xpath(child.get_xpath()),
                            "elements": [],
                        }
                        self.sections.append(section)
                        build_sections(
                            section,
                            child,
                            sections,
                            select_multiples,
                            gps_fields,
                            osm_fields,
                            encoded_fields,
                            select_ones,
                            field_delimiter,
                            remove_group_name,
                            language=language,
                        )
                    else:
                        # its a group, recurs using the same section
                        build_sections(
                            current_section,
                            child,
                            sections,
                            select_multiples,
                            gps_fields,
                            osm_fields,
                            encoded_fields,
                            select_ones,
                            field_delimiter,
                            remove_group_name,
                            language=language,
                        )
                elif isinstance(child, Question) and (
                    child.bind.get("type") not in QUESTION_TYPES_TO_EXCLUDE
                    and child.type not in QUESTION_TYPES_TO_EXCLUDE  # noqa W503
                ):
                    # add to survey_sections
                    if isinstance(child, Question):
                        child_xpath = get_abbreviated_xpath(child.get_xpath())
                        _title = ExportBuilder.format_field_title(
                            get_abbreviated_xpath(child.get_xpath()),
                            field_delimiter,
                            data_dicionary,
                            remove_group_name,
                        )
                        _label = (
                            data_dicionary.get_label(
                                child_xpath, elem=child, language=language
                            )
                            or _title  # noqa W503
                        )
                        current_section["elements"].append(
                            {
                                "label": _label,
                                "title": _title,
                                "xpath": child_xpath,
                                "type": child.bind.get("type"),
                            }
                        )

                        if _is_invalid_for_mongo(child_xpath):
                            if current_section_name not in encoded_fields:
                                encoded_fields[current_section_name] = {}
                            encoded_fields[current_section_name].update(
                                {child_xpath: _encode_for_mongo(child_xpath)}
                            )

                    # if its a select multiple, make columns out of its choices
                    if (
                        child.bind.get("type") == SELECT_BIND_TYPE
                        and child.type == MULTIPLE_SELECT_TYPE  # noqa W503
                    ):
                        choices = []
                        if self.SPLIT_SELECT_MULTIPLES:
                            choices = self._get_select_mulitples_choices(
                                child,
                                data_dicionary,
                                field_delimiter,
                                remove_group_name,
                            )
                            for choice in choices:
                                if choice not in current_section["elements"]:
                                    current_section["elements"].append(choice)

                        # choices_xpaths = [c['xpath'] for c in choices]
                        _append_xpaths_to_section(
                            current_section_name,
                            select_multiples,
                            get_abbreviated_xpath(child.get_xpath()),
                            choices,
                        )

                    # split gps fields within this section
                    if child.bind.get("type") == GEOPOINT_BIND_TYPE:
                        # add columns for geopoint components
                        parent_xpath = get_abbreviated_xpath(child.get_xpath())
                        xpaths = DataDictionary.get_additional_geopoint_xpaths(
                            get_abbreviated_xpath(child.get_xpath())
                        )
                        for xpath in xpaths:
                            _title = ExportBuilder.format_field_title(
                                xpath,
                                field_delimiter,
                                data_dicionary,
                                remove_group_name,
                                gps_extra_field=True,
                            )
                            current_section["elements"].append(
                                {
                                    "label": _title,
                                    "title": _title,
                                    "xpath": xpath,
                                    "parent": parent_xpath,
                                    "type": "decimal",
                                }
                            )
                        _append_xpaths_to_section(
                            current_section_name,
                            gps_fields,
                            get_abbreviated_xpath(child.get_xpath()),
                            xpaths,
                        )

                    # get other osm fields
                    if child.get("type") == OSM_BIND_TYPE:
                        xpaths = _get_osm_paths(child, xform)
                        for xpath in xpaths:
                            _title = ExportBuilder.format_field_title(
                                xpath,
                                field_delimiter,
                                data_dicionary,
                                remove_group_name,
                            )
                            current_section["elements"].append(
                                {
                                    "label": _title,
                                    "title": _title,
                                    "xpath": xpath,
                                    "type": "osm",
                                }
                            )
                        _append_xpaths_to_section(
                            current_section_name,
                            osm_fields,
                            get_abbreviated_xpath(child.get_xpath()),
                            xpaths,
                        )
                    if (
                        child.bind.get("type") == SELECT_BIND_TYPE
                        and child.type == SELECT_ONE  # noqa W503
                    ):
                        _append_xpaths_to_section(
                            current_section_name,
                            select_ones,
                            get_abbreviated_xpath(child.get_xpath()),
                            [],
                        )

        def _append_xpaths_to_section(current_section_name, field_list, xpath, xpaths):
            if current_section_name not in field_list:
                field_list[current_section_name] = {}
            field_list[current_section_name][xpath] = xpaths

        def _get_osm_paths(osm_field, xform):
            """
            Get osm tag keys from OsmData and make them available for the
            export builder. They are used as columns.
            """
            osm_columns = []
            if osm_field and xform:
                osm_columns = OsmData.get_tag_keys(
                    xform,
                    get_abbreviated_xpath(osm_field.get_xpath()),
                    include_prefix=True,
                )
            return osm_columns

        # pylint: disable=attribute-defined-outside-init
        self.data_dicionary = data_dicionary
        self.survey = survey
        self.select_multiples = {}
        self.select_ones = {}
        self.gps_fields = {}
        self.osm_fields = {}
        self.encoded_fields = {}
        main_section = {"name": survey.name, "elements": []}
        self.sections = [main_section]
        build_sections(
            main_section,
            self.survey,
            self.sections,
            self.select_multiples,
            self.gps_fields,
            self.osm_fields,
            self.encoded_fields,
            self.select_ones,
            self.GROUP_DELIMITER,
            self.TRUNCATE_GROUP_TITLE,
            language=self.language,
        )

    def section_by_name(self, name):
        """Return section by the given ``name``."""
        matches = [s for s in self.sections if s["name"] == name]
        assert len(matches) == 1

        return matches[0]

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    @classmethod
    def split_select_multiples(
        cls,
        row,
        select_multiples,
        select_values=False,
        binary_select_multiples=False,
        show_choice_labels=False,
        data_dictionary=None,
        language=None,
    ):
        """
        Split select multiple choices in a submission to individual columns.

        :param row: single submission dict
        :param select_multiples: list of XPATHs and choices of select multiple
                                 questions.
        :param binary_select_multiples: if True the value of the split columns
                                        will be 1 when the choice has been
                                        selected otherwise it will be 0.
        :param select_values: the value of the split columns will be the
                              name/value of the choice when selected otherwise
                              blank/None.
        :param show_choice_labels: Show a choice label instead of the
                                   value/True/False/1/0.
        :param data_dictionary: A DataDictionary/XForm object
        :param language: specific language as defined in the XLSForm.

        :return: the row dict with select multiples choice as fields in the row
        """
        # for each select_multiple, get the associated data and split it
        for xpath, choices in iteritems(select_multiples):
            # get the data matching this xpath
            data = row.get(xpath) and str(row.get(xpath))
            selections = []
            if data:
                selections = [f"{xpath}/{selection}" for selection in data.split()]
                if show_choice_labels and data_dictionary:
                    row[xpath] = get_choice_label_value(
                        xpath, data, data_dictionary, language
                    )
            if select_values:
                if show_choice_labels:
                    row.update(
                        {
                            choice["label"]: (
                                choice["_label"]
                                if selections and choice["xpath"] in selections
                                else None
                            )
                            for choice in choices
                        }
                    )
                else:
                    row.update(
                        {
                            choice["xpath"]: (
                                data.split()[selections.index(choice["xpath"])]
                                if selections and choice["xpath"] in selections
                                else None
                            )
                            for choice in choices
                        }
                    )
            elif binary_select_multiples:
                row.update(
                    {
                        choice["label"] if show_choice_labels else choice["xpath"]: (
                            YES if choice["xpath"] in selections else NO
                        )
                        for choice in choices
                    }
                )
            else:
                row.update(
                    {
                        choice["label"] if show_choice_labels else choice["xpath"]: (
                            choice["xpath"] in selections if selections else None
                        )
                        for choice in choices
                    }
                )
        return row

    @classmethod
    def split_gps_components(cls, row, gps_fields):
        """Splits GPS components into their own fields."""
        # for each gps_field, get associated data and split it
        for xpath, gps_components in iteritems(gps_fields):
            data = row.get(xpath)
            if data:
                gps_parts = data.split()
                if len(gps_parts) > 0:
                    row.update(zip(gps_components, gps_parts))
        return row

    @classmethod
    def decode_mongo_encoded_fields(cls, row, encoded_fields):
        """Update encoded fields with their corresponding xpath"""
        for xpath, encoded_xpath in iteritems(encoded_fields):
            if row.get(encoded_xpath):
                val = row.pop(encoded_xpath)
                row.update({xpath: val})
        return row

    @classmethod
    def convert_type(cls, value, data_type):
        """
        Convert data to its native type e.g. string '1' to int 1
        @param value: the string value to convert
        @param data_type: the native data type to convert to
        @return: the converted value
        """
        func = ExportBuilder.CONVERT_FUNCS.get(data_type, lambda x: x)
        try:
            return func(value)
        except ValueError:
            return value

    # pylint: disable=too-many-branches
    def pre_process_row(self, row, section):
        """
        Split select multiples, gps and decode . and $
        """
        section_name = section["name"]
        # first decode fields so that subsequent lookups
        # have decoded field names
        if section_name in self.encoded_fields:
            row = ExportBuilder.decode_mongo_encoded_fields(
                row, self.encoded_fields[section_name]
            )
        if section_name in self.select_multiples:
            select_multiples = self.select_multiples[section_name]
            if self.SPLIT_SELECT_MULTIPLES:
                row = ExportBuilder.split_select_multiples(
                    row,
                    select_multiples,
                    self.VALUE_SELECT_MULTIPLES,
                    self.BINARY_SELECT_MULTIPLES,
                    show_choice_labels=self.SHOW_CHOICE_LABELS,
                    data_dictionary=self.data_dicionary,
                    language=self.language,
                )
            if not self.SPLIT_SELECT_MULTIPLES and self.SHOW_CHOICE_LABELS:
                for xpath in select_multiples:
                    # get the data matching this xpath
                    data = row.get(xpath) and str(row.get(xpath))
                    if data:
                        row[xpath] = get_choice_label_value(
                            xpath, data, self.data_dicionary, self.language
                        )

        if section_name in self.gps_fields:
            row = ExportBuilder.split_gps_components(row, self.gps_fields[section_name])

        if section_name in self.select_ones and self.SHOW_CHOICE_LABELS:
            for key in self.select_ones[section_name]:
                if key in row:
                    row[key] = get_choice_label_value(
                        key, row[key], self.data_dicionary, self.language
                    )

        # convert to native types
        for elm in section["elements"]:
            # only convert if its in our list and its not empty, just to
            # optimize
            value = row.get(elm["xpath"])
            if (
                elm["type"] in ExportBuilder.TYPES_TO_CONVERT
                and value is not None  # noqa W503
                and value != ""  # noqa W503
            ):
                row[elm["xpath"]] = ExportBuilder.convert_type(value, elm["type"])

        if SUBMISSION_TIME in row:
            row[SUBMISSION_TIME] = ExportBuilder.convert_type(
                row[SUBMISSION_TIME], "dateTime"
            )

        # Map dynamic values
        for key, value in row.items():
            if isinstance(value, str):
                dynamic_val_regex = r"\$\{\w+\}"  # noqa
                # Find substrings that match ${`any_text`}
                result = re.findall(dynamic_val_regex, value)
                if result:
                    for val in result:
                        val_key = val.replace("${", "").replace("}", "")
                        # Try retrieving value of ${`any_text`} from the
                        # row data and replace the value
                        if row.get(val_key):
                            value = value.replace(val, row.get(val_key))
                    row[key] = value

        return row

    # pylint: disable=too-many-locals,too-many-branches,unused-argument
    def to_zipped_csv(self, path, data, *args, **kwargs):
        """Export CSV formatted files from ``data`` and zip the files."""

        def write_row(row, csv_writer, fields):
            csv_writer.writerow([encode_if_str(row, field) for field in fields])

        csv_defs = {}
        dataview = kwargs.get("dataview")
        total_records = kwargs.get("total_records")

        for section in self.sections:
            csv_file = NamedTemporaryFile(suffix=".csv", mode="w")
            csv_writer = csv.writer(csv_file)
            csv_defs[section["name"]] = {"csv_file": csv_file, "csv_writer": csv_writer}

        # write headers
        if not self.INCLUDE_LABELS_ONLY:
            for section in self.sections:
                fields = self.get_fields(dataview, section, "title")
                csv_defs[section["name"]]["csv_writer"].writerow(list(fields))

        # write labels
        if self.INCLUDE_LABELS or self.INCLUDE_LABELS_ONLY:
            for section in self.sections:
                fields = self.get_fields(dataview, section, "label")
                csv_defs[section["name"]]["csv_writer"].writerow(list(fields))

        media_xpaths = (
            []
            if not self.INCLUDE_IMAGES
            else self.data_dicionary.get_media_survey_xpaths()
        )

        columns_with_hxl = kwargs.get("columns_with_hxl")
        # write hxl row
        if self.INCLUDE_HXL and columns_with_hxl:
            for section in self.sections:
                fields = self.get_fields(dataview, section, "title")
                hxl_row = [columns_with_hxl.get(col, "") for col in fields]
                if hxl_row:
                    writer = csv_defs[section["name"]]["csv_writer"]
                    writer.writerow(hxl_row)

        index = 1
        indices = {}
        survey_name = self.survey.name
        options = kwargs.get("options")
        host = options.get("host") if options else None
        for i, row_data in enumerate(data, start=1):
            # decode mongo section names
            joined_export = dict_to_joined_export(
                row_data,
                index,
                indices,
                survey_name,
                self.survey,
                row_data,
                host,
                media_xpaths,
            )
            output = decode_mongo_encoded_section_names(joined_export)
            # attach meta fields (index, parent_index, parent_table)
            # output has keys for every section
            if survey_name not in output:
                output[survey_name] = {}
            output[survey_name][INDEX] = index
            output[survey_name][PARENT_INDEX] = -1
            for section in self.sections:
                # get data for this section and write to csv
                section_name = section["name"]
                csv_def = csv_defs[section_name]
                fields = self.get_fields(dataview, section, "xpath")
                csv_writer = csv_def["csv_writer"]
                # section name might not exist within the output, e.g. data was
                # not provided for said repeat - write test to check this
                row = output.get(section_name, None)
                if isinstance(row, dict):
                    write_row(self.pre_process_row(row, section), csv_writer, fields)
                elif isinstance(row, list):
                    for child_row in row:
                        write_row(
                            self.pre_process_row(child_row, section), csv_writer, fields
                        )
            index += 1
            track_task_progress(i, total_records)

        # write zipfile
        with ZipFile(path, "w", ZIP_DEFLATED, allowZip64=True) as zip_file:
            for section_name, csv_def in iteritems(csv_defs):
                csv_file = csv_def["csv_file"]
                csv_file.seek(0)
                zip_file.write(
                    csv_file.name, "_".join(section_name.split("/")) + ".csv"
                )

        # close files when we are done
        for section_name, csv_def in iteritems(csv_defs):
            csv_def["csv_file"].close()

    @classmethod
    def get_valid_sheet_name(cls, desired_name, existing_names):
        """Returns a valid sheet_name based on the desired names"""
        # a sheet name has to be <= 31 characters and not a duplicate of an
        # existing sheet
        # truncate sheet_name to XLSDataFrameBuilder.SHEET_NAME_MAX_CHARS
        new_sheet_name = desired_name[: cls.XLS_SHEET_NAME_MAX_CHARS]

        # make sure its unique within the list
        i = 1
        generated_name = new_sheet_name
        while generated_name in existing_names:
            digit_length = len(str(i))
            allowed_name_len = cls.XLS_SHEET_NAME_MAX_CHARS - digit_length
            # make name the required len
            if len(generated_name) > allowed_name_len:
                generated_name = generated_name[:allowed_name_len]
            generated_name = f"{generated_name}{i}"
            i += 1
        return generated_name

    # pylint: disable=too-many-locals,too-many-statements,unused-argument
    def to_xlsx_export(self, path, data, *args, **kwargs):
        """Export data to a spreadsheet document."""

        def write_row(data, work_sheet, fields, work_sheet_titles):
            # update parent_table with the generated sheet's title
            data[PARENT_TABLE_NAME] = work_sheet_titles.get(data.get(PARENT_TABLE_NAME))
            work_sheet.append([data.get(f) for f in fields])

        dataview = kwargs.get("dataview")
        total_records = kwargs.get("total_records")

        work_book = Workbook(write_only=True)
        work_sheets = {}
        # map of section_names to generated_names
        work_sheet_titles = {}
        for section in self.sections:
            section_name = section["name"]
            work_sheet_title = ExportBuilder.get_valid_sheet_name(
                "_".join(section_name.split("/")), work_sheet_titles.values()
            )
            work_sheet_titles[section_name] = work_sheet_title
            work_sheets[section_name] = work_book.create_sheet(title=work_sheet_title)

        # write the headers
        if not self.INCLUDE_LABELS_ONLY:
            for section in self.sections:
                section_name = section["name"]
                headers = self.get_fields(dataview, section, "title")

                # get the worksheet
                work_sheet = work_sheets[section_name]
                work_sheet.append(headers)

        # write labels
        if self.INCLUDE_LABELS or self.INCLUDE_LABELS_ONLY:
            for section in self.sections:
                section_name = section["name"]
                labels = self.get_fields(dataview, section, "label")

                # get the worksheet
                work_sheet = work_sheets[section_name]
                work_sheet.append(labels)

        media_xpaths = (
            []
            if not self.INCLUDE_IMAGES
            else self.data_dicionary.get_media_survey_xpaths()
        )

        # write hxl header
        columns_with_hxl = kwargs.get("columns_with_hxl")
        if self.INCLUDE_HXL and columns_with_hxl:
            for section in self.sections:
                section_name = section["name"]
                headers = self.get_fields(dataview, section, "title")

                # get the worksheet
                work_sheet = work_sheets[section_name]

                hxl_row = [columns_with_hxl.get(col, "") for col in headers]
                if hxl_row:
                    work_sheet.append(hxl_row)

        index = 1
        indices = {}
        survey_name = self.survey.name

        options = kwargs.get("options")
        host = options.get("host") if options else None
        for i, row_data in enumerate(data, start=1):
            joined_export = dict_to_joined_export(
                row_data,
                index,
                indices,
                survey_name,
                self.survey,
                row_data,
                host,
                media_xpaths,
            )
            output = decode_mongo_encoded_section_names(joined_export)
            # attach meta fields (index, parent_index, parent_table)
            # output has keys for every section
            if survey_name not in output:
                output[survey_name] = {}
            output[survey_name][INDEX] = index
            output[survey_name][PARENT_INDEX] = -1
            for section in self.sections:
                # get data for this section and write to xls
                section_name = section["name"]
                fields = self.get_fields(dataview, section, "xpath")

                work_sheet = work_sheets[section_name]
                # section might not exist within the output, e.g. data was
                # not provided for said repeat - write test to check this
                row = output.get(section_name, None)
                if isinstance(row, dict):
                    write_row(
                        self.pre_process_row(row, section),
                        work_sheet,
                        fields,
                        work_sheet_titles,
                    )
                elif isinstance(row, list):
                    for child_row in row:
                        write_row(
                            self.pre_process_row(child_row, section),
                            work_sheet,
                            fields,
                            work_sheet_titles,
                        )
            index += 1
            track_task_progress(i, total_records)

        work_book.save(filename=path)

    # pylint: disable=too-many-locals,unused-argument
    def to_flat_csv_export(
        self, path, data, username, id_string, filter_query, **kwargs
    ):
        """
        Generates a flattened CSV file for submitted data.
        """
        # pylint: disable=import-outside-toplevel
        from onadata.libs.utils.csv_builder import CSVDataFrameBuilder

        start = kwargs.get("start")
        end = kwargs.get("end")
        dataview = kwargs.get("dataview")
        xform = kwargs.get("xform")
        options = kwargs.get("options", {})
        total_records = kwargs.get("total_records")
        host = options.get("host") if options else None
        win_excel_utf8 = options.get("win_excel_utf8") if options else False
        index_tags = options.get(REPEAT_INDEX_TAGS, self.REPEAT_INDEX_TAGS)
        show_choice_labels = options.get("show_choice_labels", False)
        language = options.get("language")
        entity_list = kwargs.get("entity_list")

        csv_builder = CSVDataFrameBuilder(
            username,
            id_string,
            filter_query,
            self.GROUP_DELIMITER,
            self.SPLIT_SELECT_MULTIPLES,
            self.BINARY_SELECT_MULTIPLES,
            start,
            end,
            self.TRUNCATE_GROUP_TITLE,
            xform,
            self.INCLUDE_LABELS,
            self.INCLUDE_LABELS_ONLY,
            self.INCLUDE_IMAGES,
            self.INCLUDE_HXL,
            win_excel_utf8=win_excel_utf8,
            total_records=total_records,
            index_tags=index_tags,
            value_select_multiples=self.VALUE_SELECT_MULTIPLES,
            show_choice_labels=show_choice_labels,
            include_reviews=self.INCLUDE_REVIEWS,
            language=language,
            host=host,
            entity_list=entity_list,
        )

        csv_builder.export_to(path, data, dataview=dataview)

    def get_default_language(self, languages):
        """Return the default languange of the XForm."""
        language = self.data_dicionary.default_language
        if languages and ((language and language not in languages) or not language):
            languages.sort()
            language = languages[0]

        return language

    def _get_sav_value_labels(self, xpath_var_names=None):
        """GET/SET SPSS `VALUE LABELS`. It takes the dictionary of the form
        `{varName: {value: valueLabel}}`:

        .. code-block: python

            {
                'favourite_color': {'red': 'Red', 'blue': 'Blue'},
                'available': {0: 'No', 1: 'Yes'}
            }
        """
        choice_questions = self.data_dicionary.get_survey_elements_with_choices()
        sav_value_labels = {}

        for question in choice_questions:
            if (
                xpath_var_names
                and get_abbreviated_xpath(question.get_xpath())
                not in xpath_var_names  # noqa W503
            ):
                continue
            var_name = (
                xpath_var_names.get(get_abbreviated_xpath(question.get_xpath()))
                if xpath_var_names
                else question["name"]
            )
            choices = question.to_json_dict().get("children")
            if choices is None:
                choices = self.survey.get("choices")
                if choices is not None and question.get("itemset"):
                    choices = choices.get(question.get("itemset"))
            _value_labels = {}
            if choices:
                is_numeric = is_all_numeric([c["name"] for c in choices])
                for choice in choices:
                    name = choice["name"].strip()
                    # should skip select multiple and zero padded numbers e.g
                    # 009 or 09, they should be treated as strings
                    if question.type != "select all that apply" and is_numeric:
                        try:
                            name = (
                                float(name) if (float(name) > int(name)) else int(name)
                            )
                        except ValueError:
                            pass
                    label = self.get_choice_label_from_dict(choice.get("label", ""))
                    _value_labels[name] = label.strip()
            sav_value_labels[var_name or question["name"]] = _value_labels

        return sav_value_labels

    # pylint: disable=too-many-locals
    def _get_sav_options(self, elements):
        """
        GET/SET SPSS options.
        @param elements - a list of survey elements
        @return dictionary with options for `SavWriter`:
        .. code-block: python
            {
                'varLabels': var_labels,  # a dict of varLabels
                'varNames': var_names,   # a list of varNames
                'varTypes': var_types,  # a dict of varTypes
                'valueLabels': value_labels,  # a dict of valueLabels
                'ioUtf8': True
            }
        """

        def _is_numeric(xpath, element_type, data_dictionary):
            var_name = xpath_var_names.get(xpath) or xpath
            if element_type in ["decimal", "int", "date"]:
                return True
            if element_type == "string":
                # check if it is a choice part of multiple choice
                # type is likely empty string, split multi select is binary
                element = data_dictionary.get_element(xpath)
                if (
                    element
                    and not isinstance(element, Option)
                    and element.type == SELECT_ONE
                ):
                    # Determine if all select1 choices are numeric in nature.
                    # If the choices are numeric in nature have the field type
                    # in spss be numeric
                    choices = list(all_value_labels[var_name])
                    if len(choices) != 0:
                        return is_all_numeric(choices)

                if element and isinstance(element, Option) and value_select_multiples:
                    return is_all_numeric([element.name])

                if element:
                    parent_xpath = "/".join(xpath.split("/")[:-1])
                    if parent_xpath:
                        parent = data_dictionary.get_element(parent_xpath)
                        return parent and parent.type == MULTIPLE_SELECT_TYPE

            return False

        value_select_multiples = self.VALUE_SELECT_MULTIPLES
        _var_types = {}
        value_labels = {}
        var_labels = {}
        var_names = []
        fields_and_labels = []
        _gps_fields = []
        _gps_parent_id = {}

        for section in self.gps_fields.values():
            _gps_fields += list(section.keys())

        elements += [
            {"title": f, "label": f, "xpath": f, "type": f} for f in self.extra_columns
        ]
        for element in elements:
            title = element["title"]
            parent = element.get("parent", "")
            if parent in _gps_parent_id:
                parent_id = _gps_parent_id[parent]
                title += f"_{parent_id}"

            _var_name, _var_names = _get_var_name(title, var_names)
            if element["xpath"] in _gps_fields:
                if len(_var_name.split("@")) == 2:
                    _gps_parent_id[element["xpath"]] = _var_name.split("@")[-1]

            var_names = _var_names
            fields_and_labels.append(
                (element["title"], element["label"], element["xpath"], _var_name)
            )

        xpath_var_names = {
            xpath: var_name for field, label, xpath, var_name in fields_and_labels
        }

        all_value_labels = self._get_sav_value_labels(xpath_var_names)

        duplicate_names = []  # list of (xpath, var_name)
        already_done = []  # list of xpaths
        for _field, label, xpath, var_name in fields_and_labels:
            var_labels[var_name] = label
            #  keep track of duplicates
            if xpath not in already_done:
                already_done.append(xpath)
                _var_types[xpath] = var_name
            else:
                duplicate_names.append((xpath, var_name))
            if var_name in all_value_labels:
                value_labels[var_name] = all_value_labels.get(var_name)

        def _get_element_type(element_xpath):
            for element in elements:
                if element["xpath"] == element_xpath:
                    return element["type"]

            return ""

        var_types = dict(
            [
                (
                    _var_types[element["xpath"]],
                    (
                        SAV_NUMERIC_TYPE
                        if _is_numeric(
                            element["xpath"], element["type"], self.data_dicionary
                        )
                        else SAV_255_BYTES_TYPE
                    ),
                )
                for element in elements
            ]
            + [  # noqa W503
                (
                    _var_types[item],
                    (
                        SAV_NUMERIC_TYPE
                        if item in ["_id", "_index", "_parent_index", SUBMISSION_TIME]
                        else SAV_255_BYTES_TYPE
                    ),
                )
                for item in self.extra_columns
            ]
            + [  # noqa W503
                (
                    x[1],
                    (
                        SAV_NUMERIC_TYPE
                        if _is_numeric(
                            x[0], _get_element_type(x[0]), self.data_dicionary
                        )
                        else SAV_255_BYTES_TYPE
                    ),
                )
                for x in duplicate_names
            ]
        )
        dates = [
            _var_types[element["xpath"]]
            for element in elements
            if element.get("type") == "date"
        ]
        formats = {d: "EDATE40" for d in dates}
        formats["@" + SUBMISSION_TIME] = "DATETIME40"

        return {
            "formats": formats,
            "varLabels": var_labels,
            "varNames": var_names,
            "varTypes": var_types,
            "valueLabels": value_labels,
            "ioUtf8": True,
        }

    # pylint: disable=too-many-locals
    def to_zipped_sav(self, path, data, *args, **kwargs):
        """Generates the SPSS zipped file format export."""
        if SavWriter is None:
            # Fail silently
            return

        total_records = kwargs.get("total_records")

        def write_row(row, sav_writer, fields):
            # replace character for osm fields
            fields = [field.replace(":", "_") for field in fields]
            sav_writer.writerow(
                [encode_if_str(row, field, sav_writer=sav_writer) for field in fields]
            )

        sav_defs = {}

        # write headers
        for section in self.sections:
            sav_options = self._get_sav_options(section["elements"])
            sav_file = NamedTemporaryFile(suffix=".sav")
            sav_writer = SavWriter(
                sav_file.name, ioLocale=str("en_US.UTF-8"), **sav_options
            )
            sav_defs[section["name"]] = {"sav_file": sav_file, "sav_writer": sav_writer}

        media_xpaths = (
            []
            if not self.INCLUDE_IMAGES
            else self.data_dicionary.get_media_survey_xpaths()
        )

        index = 1
        indices = {}
        survey_name = self.survey.name

        options = kwargs.get("options")
        host = options.get("host") if options else None
        for i, row_data in enumerate(data, start=1):
            # decode mongo section names
            joined_export = dict_to_joined_export(
                row_data,
                index,
                indices,
                survey_name,
                self.survey,
                row_data,
                host,
                media_xpaths,
            )
            output = decode_mongo_encoded_section_names(joined_export)
            # attach meta fields (index, parent_index, parent_table)
            # output has keys for every section
            if survey_name not in output:
                output[survey_name] = {}
            output[survey_name][INDEX] = index
            output[survey_name][PARENT_INDEX] = -1
            for section in self.sections:
                # get data for this section and write to csv
                section_name = section["name"]
                sav_def = sav_defs[section_name]
                fields = [element["xpath"] for element in section["elements"]]
                sav_writer = sav_def["sav_writer"]
                row = output.get(section_name, None)
                if isinstance(row, dict):
                    write_row(self.pre_process_row(row, section), sav_writer, fields)
                elif isinstance(row, list):
                    for child_row in row:
                        write_row(
                            self.pre_process_row(child_row, section), sav_writer, fields
                        )
            index += 1
            track_task_progress(i, total_records)

        for section_name, sav_def in iteritems(sav_defs):
            sav_def["sav_writer"].closeSavFile(sav_def["sav_writer"].fh, mode="wb")

        # write zipfile
        with ZipFile(path, "w", ZIP_DEFLATED, allowZip64=True) as zip_file:
            for section_name, sav_def in iteritems(sav_defs):
                sav_file = sav_def["sav_file"]
                sav_file.seek(0)
                zip_file.write(
                    sav_file.name, "_".join(section_name.split("/")) + ".sav"
                )

        # close files when we are done
        for section_name, sav_def in iteritems(sav_defs):
            sav_def["sav_file"].close()

    def get_fields(self, dataview, section, key):
        """
        Return list of element value with the key in section['elements'].
        """
        if dataview:
            columns = [
                (
                    element.get("_label_xpath") or element[key]
                    if self.SHOW_CHOICE_LABELS
                    else element[key]
                )
                for element in section["elements"]
                if element["title"] in dataview.columns
            ]

            # add extra columns
            for column in filter(lambda col: col not in columns, dataview.columns):
                if column in self.extra_columns:
                    columns.append(column)

            return columns

        return [
            (
                element.get("_label_xpath") or element[key]
                if self.SHOW_CHOICE_LABELS
                else element[key]
            )
            for element in section["elements"]
        ] + self.extra_columns
