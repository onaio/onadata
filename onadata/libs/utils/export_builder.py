import csv
from datetime import datetime, date
import six
import uuid
from zipfile import ZipFile

from django.conf import settings
from django.core.files.temp import NamedTemporaryFile
from openpyxl.utils.datetime import to_excel
from openpyxl.workbook import Workbook
from pyxform.question import Question
from pyxform.section import Section, RepeatingSection
from savReaderWriter import SavWriter

from onadata.apps.logger.models.xform import _encode_for_mongo,\
    QUESTION_TYPES_TO_EXCLUDE
from onadata.apps.viewer.models.data_dictionary import DataDictionary
from onadata.libs.utils.common_tags import (
    ID, XFORM_ID_STRING, STATUS, ATTACHMENTS, GEOLOCATION, BAMBOO_DATASET_ID,
    DELETEDAT, INDEX, PARENT_INDEX, PARENT_TABLE_NAME,
    SUBMISSION_TIME, UUID, TAGS, NOTES, VERSION, SUBMITTED_BY, DURATION)
from onadata.libs.utils.mongo import _is_invalid_for_mongo,\
    _decode_from_mongo


# the bind type of select multiples that we use to compare
MULTIPLE_SELECT_BIND_TYPE = u"select"
GEOPOINT_BIND_TYPE = u"geopoint"


def current_site_url(path):
    """
    Returns fully qualified URL (no trailing slash) for the current site.
    :param path
    :return: complete url
    """
    from django.contrib.sites.models import Site
    current_site = Site.objects.get_current()
    protocol = getattr(settings, 'ONA_SITE_PROTOCOL', 'http')
    port = getattr(settings, 'ONA_SITE_PORT', '')
    url = '%s://%s' % (protocol, current_site.domain)
    if port:
        url += ':%s' % port
    if path:
        url += '%s' % path

    return url


def get_value_or_attachment_uri(
        key, value, row, data_dictionary, media_xpaths,
        attachment_list=None):
    """
     Gets either the attachment value or the attachment url
     :param key: used to retrieve survey element
     :param value: filename
     :param row: current records row
     :param data_dictionary: form structure
     :param include_images: boolean value to either inlcude images or not
     :param attachment_list: to be used incase row doesn't have ATTACHMENTS key
     :return: value
    """
    if not media_xpaths:
        return value

    if key in media_xpaths:
        attachments = [
            a
            for a in row.get(ATTACHMENTS, attachment_list or [])
            if a.get('filename') and a.get('filename').endswith(value)
        ]
        if attachments:
            value = current_site_url(
                attachments[0].get('download_url', '')
            )

    return value


def get_data_dictionary_from_survey(survey):
    dd = DataDictionary()
    dd._survey = survey

    return dd


def encode_if_str(row, key, encode_dates=False):
    val = row.get(key)

    if isinstance(val, six.string_types):
        return val.encode('utf-8')

    if encode_dates and (isinstance(val, datetime) or isinstance(val, date)):
        return val.isoformat()

    return val


def dict_to_joined_export(data, index, indices, name, survey, row,
                          media_xpaths=[]):
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
    # TODO: test for _geolocation and attachment lists
    if isinstance(data, dict):
        for key, val in data.iteritems():
            if isinstance(val, list) and key not in [NOTES, ATTACHMENTS, TAGS]:

                output[key] = []
                for child in val:
                    if key not in indices:
                        indices[key] = 0
                    indices[key] += 1
                    child_index = indices[key]
                    new_output = dict_to_joined_export(
                        child, child_index, indices, key, survey, row,
                        media_xpaths)
                    d = {INDEX: child_index, PARENT_INDEX: index,
                         PARENT_TABLE_NAME: name}
                    # iterate over keys within new_output and append to
                    # main output
                    for out_key, out_val in new_output.iteritems():
                        if isinstance(out_val, list):
                            if out_key not in output:
                                output[out_key] = []
                            output[out_key].extend(out_val)
                        else:
                            d.update(out_val)
                    output[key].append(d)
            else:
                if name not in output:
                    output[name] = {}
                if key in [TAGS]:
                    output[name][key] = ",".join(val)
                elif key in [NOTES]:
                    note_list = [v if isinstance(v, six.string_types)
                                 else v['note'] for v in val]
                    output[name][key] = "\r\n".join(note_list)
                else:
                    data_dictionary = get_data_dictionary_from_survey(survey)
                    output[name][key] = get_value_or_attachment_uri(
                        key, val, data, data_dictionary, media_xpaths,
                        row and row.get(ATTACHMENTS)
                    )

    return output


class ExportBuilder(object):
    IGNORED_COLUMNS = [XFORM_ID_STRING, STATUS, ATTACHMENTS, GEOLOCATION,
                       BAMBOO_DATASET_ID, DELETEDAT]
    # fields we export but are not within the form's structure
    EXTRA_FIELDS = [ID, UUID, SUBMISSION_TIME, INDEX, PARENT_TABLE_NAME,
                    PARENT_INDEX, TAGS, NOTES, VERSION, DURATION,
                    SUBMITTED_BY]
    SPLIT_SELECT_MULTIPLES = True
    BINARY_SELECT_MULTIPLES = False

    # column group delimiters get_value_or_attachment_uri
    GROUP_DELIMITER_SLASH = '/'
    GROUP_DELIMITER_DOT = '.'
    GROUP_DELIMITER = GROUP_DELIMITER_SLASH
    GROUP_DELIMITERS = [GROUP_DELIMITER_SLASH, GROUP_DELIMITER_DOT]

    INCLUDE_LABELS = False
    INCLUDE_LABELS_ONLY = False
    INCLUDE_HXL = False
    INCLUDE_IMAGES = settings.EXPORT_WITH_IMAGE_DEFAULT

    TYPES_TO_CONVERT = ['int', 'decimal', 'date']  # , 'dateTime']
    CONVERT_FUNCS = {
        'int': lambda x: int(x),
        'decimal': lambda x: float(x),
        'date': lambda x: ExportBuilder.string_to_date_with_xls_validation(x),
        'dateTime': lambda x: datetime.strptime(x[:19], '%Y-%m-%dT%H:%M:%S')
    }

    TRUNCATE_GROUP_TITLE = False

    XLS_SHEET_NAME_MAX_CHARS = 31
    url = None

    @classmethod
    def string_to_date_with_xls_validation(cls, date_str):
        if not isinstance(date_str, six.string_types):
            return date_str
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            to_excel(date_obj)
        except ValueError:
            return date_str
        else:
            return date_obj

    @classmethod
    def format_field_title(cls, abbreviated_xpath, field_delimiter,
                           data_dictionary, remove_group_name=False):
        title = abbreviated_xpath
        # Check if to truncate the group name prefix
        if remove_group_name:
            elem = data_dictionary.get_survey_element(abbreviated_xpath)
            # incase abbreviated_xpath is a choices xpath
            if elem is None:
                pass
            elif elem.type == u'':
                title = u'/'.join([elem.parent.name, elem.name])
            else:
                title = elem.name

        if field_delimiter != '/':
            title = field_delimiter.join(title.split('/'))

        return title

    def get_choice_label_from_dict(self, label):
        if isinstance(label, dict):
            language = self.get_default_language(label.keys())
            label = label.get(language)

        return label

    def _get_select_mulitples_choices(self, child, dd, field_delimiter,
                                      remove_group_name):
        def get_choice_dict(xpath, label):
            title = ExportBuilder.format_field_title(
                xpath, field_delimiter, dd, remove_group_name
            )

            return {
                'label': field_delimiter.join([
                    child.name, label or title
                ]),
                'title': title,
                'xpath': xpath,
                'type': 'string'
            }

        choices = []

        if not child.children and child.choice_filter and child.itemset:
            itemset = dd.survey.to_json_dict()['choices'].get(child.itemset)
            choices = [get_choice_dict(
                u'/'.join([child.get_abbreviated_xpath(), i['name']]),
                self.get_choice_label_from_dict(i['label'])
            ) for i in itemset] if itemset else choices
        else:
            choices = [get_choice_dict(
                c.get_abbreviated_xpath(),
                dd.get_label(c.get_abbreviated_xpath(), elem=c)
            ) for c in child.children]

        return choices

    def set_survey(self, survey):
        dd = get_data_dictionary_from_survey(survey)

        def build_sections(
                current_section, survey_element, sections, select_multiples,
                gps_fields, encoded_fields, field_delimiter='/',
                remove_group_name=False):

            for child in survey_element.children:
                current_section_name = current_section['name']
                # if a section, recurs
                if isinstance(child, Section):
                    # if its repeating, build a new section
                    if isinstance(child, RepeatingSection):
                        # section_name in recursive call changes
                        section = {
                            'name': child.get_abbreviated_xpath(),
                            'elements': []}
                        self.sections.append(section)
                        build_sections(
                            section, child, sections, select_multiples,
                            gps_fields, encoded_fields, field_delimiter,
                            remove_group_name)
                    else:
                        # its a group, recurs using the same section
                        build_sections(
                            current_section, child, sections, select_multiples,
                            gps_fields, encoded_fields, field_delimiter,
                            remove_group_name)
                elif isinstance(child, Question) and child.bind.get(u"type")\
                        not in QUESTION_TYPES_TO_EXCLUDE:
                    # add to survey_sections
                    if isinstance(child, Question):
                        child_xpath = child.get_abbreviated_xpath()
                        _title = ExportBuilder.format_field_title(
                            child.get_abbreviated_xpath(),
                            field_delimiter, dd, remove_group_name
                        )
                        _label = \
                            dd.get_label(child_xpath, elem=child) or _title
                        current_section['elements'].append({
                            'label': _label,
                            'title': _title,
                            'xpath': child_xpath,
                            'type': child.bind.get(u"type")
                        })

                        if _is_invalid_for_mongo(child_xpath):
                            if current_section_name not in encoded_fields:
                                encoded_fields[current_section_name] = {}
                            encoded_fields[current_section_name].update(
                                {child_xpath: _encode_for_mongo(child_xpath)})

                    # if its a select multiple, make columns out of its choices
                    if child.bind.get(u"type") == MULTIPLE_SELECT_BIND_TYPE\
                            and self.SPLIT_SELECT_MULTIPLES:
                        choices = self._get_select_mulitples_choices(
                            child, dd, field_delimiter, remove_group_name
                        )
                        for choice in choices:
                            if choice not in current_section['elements']:
                                current_section['elements'].append(choice)

                        choices_xpaths = [c['xpath'] for c in choices]
                        _append_xpaths_to_section(
                            current_section_name, select_multiples,
                            child.get_abbreviated_xpath(), choices_xpaths
                        )

                    # split gps fields within this section
                    if child.bind.get(u"type") == GEOPOINT_BIND_TYPE:
                        # add columns for geopoint components
                        xpaths = DataDictionary.get_additional_geopoint_xpaths(
                            child.get_abbreviated_xpath())
                        for xpath in xpaths:
                            _title = ExportBuilder.format_field_title(
                                xpath, field_delimiter, dd,
                                remove_group_name
                            )
                            current_section['elements'].append({
                                'label': _title,
                                'title': _title,
                                'xpath': xpath,
                                'type': 'decimal'
                            })
                        _append_xpaths_to_section(
                            current_section_name, gps_fields,
                            child.get_abbreviated_xpath(), xpaths)

        def _append_xpaths_to_section(current_section_name, field_list, xpath,
                                      xpaths):
            if current_section_name not in field_list:
                field_list[current_section_name] = {}
            field_list[
                current_section_name][xpath] = xpaths

        self.dd = dd
        self.survey = survey
        self.select_multiples = {}
        self.gps_fields = {}
        self.encoded_fields = {}
        main_section = {'name': survey.name, 'elements': []}
        self.sections = [main_section]
        build_sections(
            main_section, self.survey, self.sections,
            self.select_multiples, self.gps_fields, self.encoded_fields,
            self.GROUP_DELIMITER, self.TRUNCATE_GROUP_TITLE)

    def section_by_name(self, name):
        matches = filter(lambda s: s['name'] == name, self.sections)
        assert(len(matches) == 1)
        return matches[0]

    @classmethod
    def split_select_multiples(cls, row, select_multiples):
        # for each select_multiple, get the associated data and split it
        for xpath, choices in select_multiples.iteritems():
            # get the data matching this xpath
            data = row.get(xpath) and unicode(row.get(xpath))
            selections = []
            if data:
                selections = [
                    u'{0}/{1}'.format(
                        xpath, selection) for selection in data.split()]
            if not cls.BINARY_SELECT_MULTIPLES:
                row.update(dict(
                    [(choice, choice in selections if selections else None)
                     for choice in choices]))
            else:
                YES = 1
                NO = 0
                row.update(dict(
                    [(choice, YES if choice in selections else NO)
                     for choice in choices]))
        return row

    @classmethod
    def split_gps_components(cls, row, gps_fields):
        # for each gps_field, get associated data and split it
        for xpath, gps_components in gps_fields.iteritems():
            data = row.get(xpath)
            if data:
                gps_parts = data.split()
                if len(gps_parts) > 0:
                    row.update(zip(gps_components, gps_parts))
        return row

    @classmethod
    def decode_mongo_encoded_fields(cls, row, encoded_fields):
        for xpath, encoded_xpath in encoded_fields.iteritems():
            if row.get(encoded_xpath):
                val = row.pop(encoded_xpath)
                row.update({xpath: val})
        return row

    @classmethod
    def decode_mongo_encoded_section_names(cls, data):
        return dict([(_decode_from_mongo(k), v) for k, v in data.iteritems()])

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

    def pre_process_row(self, row, section):
        """
        Split select multiples, gps and decode . and $
        """
        section_name = section['name']

        # first decode fields so that subsequent lookups
        # have decoded field names
        if section_name in self.encoded_fields:
            row = ExportBuilder.decode_mongo_encoded_fields(
                row, self.encoded_fields[section_name])

        if self.SPLIT_SELECT_MULTIPLES and\
                section_name in self.select_multiples:
            row = ExportBuilder.split_select_multiples(
                row, self.select_multiples[section_name])

        if section_name in self.gps_fields:
            row = ExportBuilder.split_gps_components(
                row, self.gps_fields[section_name])

        # convert to native types
        for elm in section['elements']:
            # only convert if its in our list and its not empty, just to
            # optimize
            value = row.get(elm['xpath'])
            if elm['type'] in ExportBuilder.TYPES_TO_CONVERT\
                    and value is not None and value != '':
                row[elm['xpath']] = ExportBuilder.convert_type(
                    value, elm['type'])

        return row

    def to_zipped_csv(self, path, data, *args, **kwargs):
        def write_row(row, csv_writer, fields):
            csv_writer.writerow(
                [encode_if_str(row, field) for field in fields])

        csv_defs = {}
        dataview = kwargs.get('dataview')

        for section in self.sections:
            csv_file = NamedTemporaryFile(suffix=".csv")
            csv_writer = csv.writer(csv_file)
            csv_defs[section['name']] = {
                'csv_file': csv_file, 'csv_writer': csv_writer}

        # write headers
        if not self.INCLUDE_LABELS_ONLY:
            for section in self.sections:
                fields = self.get_fields(dataview, section, 'title')
                csv_defs[section['name']]['csv_writer'].writerow(
                    [f.encode('utf-8') for f in fields])

        # write labels
        if self.INCLUDE_LABELS or self.INCLUDE_LABELS_ONLY:
            for section in self.sections:
                fields = self.get_fields(dataview, section, 'label')
                csv_defs[section['name']]['csv_writer'].writerow(
                    [f.encode('utf-8') for f in fields])

        media_xpaths = [] if not self.INCLUDE_IMAGES \
            else self.dd.get_media_survey_xpaths()

        columns_with_hxl = kwargs.get('columns_with_hxl')
        # write hxl row
        if self.INCLUDE_HXL and columns_with_hxl:
            for section in self.sections:
                fields = self.get_fields(dataview, section, 'title')
                hxl_row = [columns_with_hxl.get(col, '')
                           for col in fields]
                if hxl_row:
                    writer = csv_defs[section['name']]['csv_writer']
                    writer.writerow(hxl_row)

        index = 1
        indices = {}
        survey_name = self.survey.name
        for d in data:
            # decode mongo section names
            joined_export = dict_to_joined_export(d, index, indices,
                                                  survey_name,
                                                  self.survey, d,
                                                  media_xpaths)
            output = ExportBuilder.decode_mongo_encoded_section_names(
                joined_export)
            # attach meta fields (index, parent_index, parent_table)
            # output has keys for every section
            if survey_name not in output:
                output[survey_name] = {}
            output[survey_name][INDEX] = index
            output[survey_name][PARENT_INDEX] = -1
            for section in self.sections:
                # get data for this section and write to csv
                section_name = section['name']
                csv_def = csv_defs[section_name]
                fields = self.get_fields(dataview, section, 'xpath')
                csv_writer = csv_def['csv_writer']
                # section name might not exist within the output, e.g. data was
                # not provided for said repeat - write test to check this
                row = output.get(section_name, None)
                if type(row) == dict:
                    write_row(
                        self.pre_process_row(row, section),
                        csv_writer, fields)
                elif type(row) == list:
                    for child_row in row:
                        write_row(
                            self.pre_process_row(child_row, section),
                            csv_writer, fields)
            index += 1

        # write zipfile
        with ZipFile(path, 'w') as zip_file:
            for section_name, csv_def in csv_defs.iteritems():
                csv_file = csv_def['csv_file']
                csv_file.seek(0)
                zip_file.write(
                    csv_file.name, "_".join(section_name.split("/")) + ".csv")

        # close files when we are done
        for section_name, csv_def in csv_defs.iteritems():
            csv_def['csv_file'].close()

    @classmethod
    def get_valid_sheet_name(cls, desired_name, existing_names):
        # a sheet name has to be <= 31 characters and not a duplicate of an
        # existing sheet
        # truncate sheet_name to XLSDataFrameBuilder.SHEET_NAME_MAX_CHARS
        new_sheet_name = \
            desired_name[:cls.XLS_SHEET_NAME_MAX_CHARS]

        # make sure its unique within the list
        i = 1
        generated_name = new_sheet_name
        while generated_name in existing_names:
            digit_length = len(str(i))
            allowed_name_len = cls.XLS_SHEET_NAME_MAX_CHARS - \
                digit_length
            # make name the required len
            if len(generated_name) > allowed_name_len:
                generated_name = generated_name[:allowed_name_len]
            generated_name = "{0}{1}".format(generated_name, i)
            i += 1
        return generated_name

    def to_xls_export(self, path, data, *args, **kwargs):
        def write_row(data, work_sheet, fields, work_sheet_titles):
            # update parent_table with the generated sheet's title
            data[PARENT_TABLE_NAME] = work_sheet_titles.get(
                data.get(PARENT_TABLE_NAME))
            work_sheet.append([data.get(f) for f in fields])

        dataview = kwargs.get('dataview')
        wb = Workbook(optimized_write=True)
        work_sheets = {}
        # map of section_names to generated_names
        work_sheet_titles = {}
        for section in self.sections:
            section_name = section['name']
            work_sheet_title = ExportBuilder.get_valid_sheet_name(
                "_".join(section_name.split("/")), work_sheet_titles.values())
            work_sheet_titles[section_name] = work_sheet_title
            work_sheets[section_name] = wb.create_sheet(
                title=work_sheet_title)

        # write the headers
        if not self.INCLUDE_LABELS_ONLY:
            for section in self.sections:
                section_name = section['name']
                headers = self.get_fields(dataview, section, 'title')

                # get the worksheet
                ws = work_sheets[section_name]
                ws.append(headers)

        # write labels
        if self.INCLUDE_LABELS or self.INCLUDE_LABELS_ONLY:
            for section in self.sections:
                section_name = section['name']
                labels = self.get_fields(dataview, section, 'label')

                # get the worksheet
                ws = work_sheets[section_name]
                ws.append(labels)

        media_xpaths = [] if not self.INCLUDE_IMAGES \
            else self.dd.get_media_survey_xpaths()

        # write hxl header
        columns_with_hxl = kwargs.get('columns_with_hxl')
        if self.INCLUDE_HXL and columns_with_hxl:
            for section in self.sections:
                section_name = section['name']
                headers = self.get_fields(dataview, section, 'title')

                # get the worksheet
                ws = work_sheets[section_name]

                hxl_row = [columns_with_hxl.get(col, '')
                           for col in headers]
                hxl_row and ws.append(hxl_row)

        index = 1
        indices = {}
        survey_name = self.survey.name
        for d in data:
            joined_export = dict_to_joined_export(d, index, indices,
                                                  survey_name,
                                                  self.survey, d,
                                                  media_xpaths)
            output = ExportBuilder.decode_mongo_encoded_section_names(
                joined_export)
            # attach meta fields (index, parent_index, parent_table)
            # output has keys for every section
            if survey_name not in output:
                output[survey_name] = {}
            output[survey_name][INDEX] = index
            output[survey_name][PARENT_INDEX] = -1
            for section in self.sections:
                # get data for this section and write to xls
                section_name = section['name']
                fields = self.get_fields(dataview, section, 'xpath')

                ws = work_sheets[section_name]
                # section might not exist within the output, e.g. data was
                # not provided for said repeat - write test to check this
                row = output.get(section_name, None)
                if type(row) == dict:
                    write_row(
                        self.pre_process_row(row, section),
                        ws, fields, work_sheet_titles)
                elif type(row) == list:
                    for child_row in row:
                        write_row(
                            self.pre_process_row(child_row, section),
                            ws, fields, work_sheet_titles)
            index += 1

        wb.save(filename=path)

    def to_flat_csv_export(
            self, path, data, username, id_string, filter_query, **kwargs):
        # TODO resolve circular import
        from onadata.libs.utils.csv_builder import CSVDataFrameBuilder
        start = kwargs.get('start')
        end = kwargs.get('end')
        dataview = kwargs.get('dataview')
        xform = kwargs.get('xform')
        options = kwargs.get('options')
        win_excel_utf8 = options.get('win_excel_utf8') if options else False

        csv_builder = CSVDataFrameBuilder(
            username, id_string, filter_query, self.GROUP_DELIMITER,
            self.SPLIT_SELECT_MULTIPLES, self.BINARY_SELECT_MULTIPLES,
            start, end, self.TRUNCATE_GROUP_TITLE, xform,
            self.INCLUDE_LABELS, self.INCLUDE_LABELS_ONLY, self.INCLUDE_IMAGES,
            self.INCLUDE_HXL, win_excel_utf8=win_excel_utf8
        )

        csv_builder.export_to(path, dataview=dataview)

    def get_default_language(self, languages):
        language = self.dd.default_language
        if languages and \
                ((language and language not in languages) or not language):
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
        if not hasattr(self, '_sav_value_labels'):
            choice_questions = self.dd.get_survey_elements_with_choices()
            self._sav_value_labels = {}

            for q in choice_questions:
                var_name = xpath_var_names.get(q.get_abbreviated_xpath()) if \
                    xpath_var_names else q['name']
                choices = q.to_json_dict().get('children')
                if choices is None:
                    choices = self.survey.get('choices')
                    if choices is not None and q.get('itemset'):
                        choices = choices.get(q.get('itemset'))
                _value_labels = {}
                for choice in choices:
                    name = choice['name'].strip()
                    label = self.get_choice_label_from_dict(choice['label'])
                    _value_labels[name] = label.strip()
                self._sav_value_labels[var_name or q['name']] = _value_labels

        return self._sav_value_labels

    def _get_var_name(self, title, var_names):
        """GET valid SPSS varName.
                @param title - survey element title/name
                @param var_names - list of existing var_names

                @return valid varName and list of var_names with new var name
                 appended

                """
        var_name = title.replace('/', '.').replace('-', '_')
        var_name = self._check_sav_column(var_name, var_names)
        var_name = '@' + var_name if var_name.startswith('_') else var_name
        var_names.append(var_name)
        return var_name, var_names

    def _get_sav_options(self, elements):
        """GET/SET SPSS options.
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
        _var_types = {}
        value_labels = {}
        var_labels = {}
        var_names = []
        fields_and_labels = []
        elements += [{'title': f, "label": f, "xpath": f, 'type': f}
                     for f in self.EXTRA_FIELDS]

        for element in elements:
            title = element['title']
            _var_name, _var_names = self._get_var_name(title, var_names)
            var_names = _var_names
            fields_and_labels.append((element['title'], element['label'],
                                      element['xpath'], _var_name))

        xpath_var_names = dict([(xpath, var_name)
                                for field, label, xpath, var_name
                                in fields_and_labels])
        all_value_labels = self._get_sav_value_labels(xpath_var_names)

        for field, label, xpath, var_name in fields_and_labels:
            var_labels[var_name] = label
            _var_types[xpath] = var_name
            if var_name in all_value_labels:
                value_labels[var_name] = all_value_labels.get(var_name)

        var_types = dict(
            [(_var_types[element['xpath']],
                0 if element['type'] in ['decimal', 'int'] else 255)
                for element in elements] +
            [(_var_types[item],
                0 if item in ['_id', '_index', '_parent_index'] else 255)
                for item in self.EXTRA_FIELDS]
        )

        return {
            'varLabels': var_labels,
            'varNames': var_names,
            'varTypes': var_types,
            'valueLabels': value_labels,
            'ioUtf8': True
        }

    def _check_sav_column(self, column, columns):
        """
        Check for duplicates and append @ 4 chars uuid.
        Also checks for column length more than 64 chars
        :param column:
        :return: truncated column
        """

        if len(column) > 64:
            col_len_diff = len(column) - 64
            column = column[:-col_len_diff]

        if column in columns:
            if len(column) > 59:
                column = column[:-5]
            column = column + "@" + str(uuid.uuid4()).split("-")[1]

        return column

    def to_zipped_sav(self, path, data, *args, **kwargs):
        def write_row(row, csv_writer, fields):
            sav_writer.writerow(
                [encode_if_str(row, field, True) for field in fields])

        sav_defs = {}

        # write headers
        for section in self.sections:
            sav_options = self._get_sav_options(section['elements'])
            sav_file = NamedTemporaryFile(suffix=".sav")
            sav_writer = SavWriter(sav_file.name, ioLocale="en_US.UTF-8",
                                   **sav_options)
            sav_defs[section['name']] = {
                'sav_file': sav_file, 'sav_writer': sav_writer}

        media_xpaths = [] if not self.INCLUDE_IMAGES \
            else self.dd.get_media_survey_xpaths()

        index = 1
        indices = {}
        survey_name = self.survey.name
        for d in data:
            # decode mongo section names
            joined_export = dict_to_joined_export(d, index, indices,
                                                  survey_name,
                                                  self.survey, d,
                                                  media_xpaths)
            output = ExportBuilder.decode_mongo_encoded_section_names(
                joined_export)
            # attach meta fields (index, parent_index, parent_table)
            # output has keys for every section
            if survey_name not in output:
                output[survey_name] = {}
            output[survey_name][INDEX] = index
            output[survey_name][PARENT_INDEX] = -1
            for section in self.sections:
                # get data for this section and write to csv
                section_name = section['name']
                sav_def = sav_defs[section_name]
                fields = [
                    element['xpath'] for element in
                    section['elements']]
                sav_writer = sav_def['sav_writer']
                row = output.get(section_name, None)
                if type(row) == dict:
                    write_row(
                        self.pre_process_row(row, section),
                        sav_writer, fields)
                elif type(row) == list:
                    for child_row in row:
                        write_row(
                            self.pre_process_row(child_row, section),
                            sav_writer, fields)
            index += 1

        for section_name, sav_def in sav_defs.iteritems():
            sav_def['sav_writer'].closeSavFile(
                sav_def['sav_writer'].fh, mode='wb')

        # write zipfile
        with ZipFile(path, 'w') as zip_file:
            for section_name, sav_def in sav_defs.iteritems():
                sav_file = sav_def['sav_file']
                sav_file.seek(0)
                zip_file.write(
                    sav_file.name, "_".join(section_name.split("/")) + ".sav")

        # close files when we are done
        for section_name, sav_def in sav_defs.iteritems():
            sav_def['sav_file'].close()

    def get_fields(self, dataview, section, key):
        if dataview:
            return [element[key] for element in section['elements']
                    if [col for col in dataview.columns
                        if element[key].startswith(col)]] + self.EXTRA_FIELDS

        else:
            return [element[key] for element in
                    section['elements']] + self.EXTRA_FIELDS
