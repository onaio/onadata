# -*- coding: utf-8 -*-
"""
XlsWriter module - generate a spreadsheet workbook in XLSX format.
"""
from builtins import str as text
from collections import defaultdict
from io import StringIO
from pyxform import Section, Question
from xlwt import Workbook

from onadata.apps.logger.models.xform import question_types_to_exclude


# pylint: disable=too-many-instance-attributes,
class XlsWriter:
    """XlsWriter class - generate a spreadsheet workbook in XLSX format."""

    def __init__(self):
        self.set_file()
        self.reset_workbook()
        self.sheet_name_limit = 30
        self._generated_sheet_name_dict = {}
        self._data_dictionary = None

    def set_file(self, file_object=None):
        """
        If the file object is None use a StringIO object.
        """
        if file_object is not None:
            self._file = file_object
        else:
            self._file = StringIO()

    def reset_workbook(self):
        """Reset a Workbook to sensible default."""
        self._workbook = Workbook()
        self._sheets = {}
        self._columns = defaultdict(list)
        self._current_index = defaultdict(lambda: 1)
        self._generated_sheet_name_dict = {}

    def add_sheet(self, name):
        """Add a given ``name`` sheet to this workbook."""
        unique_sheet_name = self._unique_name_for_xls(name)
        sheet = self._workbook.add_sheet(unique_sheet_name)
        self._sheets[unique_sheet_name] = sheet

    def add_column(self, sheet_name, column_name):
        """Add a ``column_name`` to the given ``sheet_name`` to this workbook."""
        index = len(self._columns[sheet_name])
        sheet = self._sheets.get(sheet_name)
        if sheet:
            sheet.write(0, index, column_name)
            self._columns[sheet_name].append(column_name)

    def add_row(self, sheet_name, row):
        """Add a ``row`` to the given ``sheet_name`` to this workbook."""
        i = self._current_index[sheet_name]
        columns = self._columns[sheet_name]
        for key in list(row):
            if key not in columns:
                self.add_column(sheet_name, key)
        for j, column_name in enumerate(self._columns[sheet_name]):
            # leaving this untranslated as I'm not sure it's in django context
            self._sheets[sheet_name].write(i, j, row.get(column_name, "n/a"))
        self._current_index[sheet_name] += 1

    def add_obs(self, obs):
        """Add data in ``obs`` dictionary into specified sheets to this workbook."""
        self._fix_indices(obs)
        for sheet_name, rows in obs.items():
            for row in rows:
                actual_sheet_name = self._generated_sheet_name_dict.get(
                    sheet_name, sheet_name
                )
                self.add_row(actual_sheet_name, row)

    def _fix_indices(self, obs):
        for sheet_name, rows in obs.items():
            for row in rows:
                row["_index"] += self._current_index[sheet_name]
                if row["_parent_index"] == -1:
                    continue
                i = self._current_index[row["_parent_table_name"]]
                row["_parent_index"] += i

    def write_tables_to_workbook(self, tables):
        """
        tables should be a list of pairs, the first element in the
        pair is the name of the table, the second is the actual data.

        TODO: figure out how to write to the xls file rather than keep
        the whole workbook in memory.
        """
        self.reset_workbook()
        for table_name, table in tables:
            self.add_sheet(table_name)
            for i, row in enumerate(table):
                for j, value in enumerate(row):
                    self._sheets[table_name].write(i, j, text(value))
        return self._workbook

    def save_workbook_to_file(self):
        """Saves the XLSX workbook to a file."""
        self._workbook.save(self._file)
        return self._file

    def set_data_dictionary(self, data_dictionary):
        """Set the data_dictionary XForm model object for this class."""
        self._data_dictionary = data_dictionary
        self.reset_workbook()
        self._add_sheets()
        observations = self._data_dictionary.add_instances()
        for obs in observations:
            self.add_obs(obs)

    def _add_sheets(self):
        if self._data_dictionary:
            for survey_element in self._data_dictionary.get_survey_elements():
                if isinstance(survey_element, Section):
                    sheet_name = survey_element.name
                    self.add_sheet(sheet_name)
                    for field in survey_element.children:
                        if isinstance(
                            field, Question
                        ) and not question_types_to_exclude(field.type):
                            self.add_column(sheet_name, field.name)

    def _unique_name_for_xls(self, sheet_name):
        # excel worksheet name limit seems to be 31 characters (30 to be safe)
        unique_sheet_name = sheet_name[0 : self.sheet_name_limit]
        unique_sheet_name = self._generate_unique_sheet_name(unique_sheet_name)
        self._generated_sheet_name_dict[sheet_name] = unique_sheet_name
        return unique_sheet_name

    def _generate_unique_sheet_name(self, sheet_name):
        # check if sheet name exists
        if sheet_name not in self._sheets:
            return sheet_name

        i = 1
        unique_name = sheet_name
        while unique_name in self._sheets:
            number_len = len(text(i))
            allowed_name_len = self.sheet_name_limit - number_len
            # make name required len
            if len(unique_name) > allowed_name_len:
                unique_name = unique_name[0:allowed_name_len]
            unique_name = f"{unique_name}{i}"
            i = i + 1
        return unique_name
