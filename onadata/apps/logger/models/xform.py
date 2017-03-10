import base64
import json
import os
import pytz
import re

from hashlib import md5
from django.utils import timezone
from datetime import datetime
from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericRelation
from django.core.urlresolvers import reverse
from django.db.models.signals import post_save, post_delete, pre_save
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import ugettext_lazy, ugettext as _

from guardian.models import UserObjectPermissionBase
from guardian.models import GroupObjectPermissionBase

from pyxform import constants
from pyxform import SurveyElementBuilder
from pyxform.question import Question
from pyxform.section import RepeatingSection
from pyxform.xform2json import create_survey_element_from_xml

from taggit.managers import TaggableManager
from xml.dom import Node

from onadata.apps.logger.xform_instance_parser import XLSFormError
from onadata.apps.logger.xform_instance_parser import clean_and_parse_xml
from onadata.apps.main.models import MetaData
from onadata.libs.models.base_model import BaseModel
from onadata.libs.utils.cache_tools import (
    IS_ORG,
    PROJ_FORMS_CACHE,
    PROJ_NUM_DATASET_CACHE,
    PROJ_SUB_DATE_CACHE,
    safe_delete)
from onadata.libs.utils.common_tags import UUID, SUBMISSION_TIME, TAGS, NOTES,\
    VERSION, DURATION, SUBMITTED_BY, KNOWN_MEDIA_TYPES
from onadata.libs.utils.model_tools import queryset_iterator


QUESTION_TYPES_TO_EXCLUDE = [
    u'note',
]
XFORM_TITLE_LENGTH = 255
title_pattern = re.compile(r"<h:title>([^<]+)</h:title>")


def _encode_for_mongo(key):
    return reduce(lambda s, c: re.sub(c[0], base64.b64encode(c[1]), s),
                  [(r'^\$', '$'), (r'\.', '.')], key)


def question_types_to_exclude(_type):
    return _type in QUESTION_TYPES_TO_EXCLUDE


def upload_to(instance, filename):
    return os.path.join(
        instance.user.username,
        'xls',
        os.path.split(filename)[1])


def contains_xml_invalid_char(text, invalids=['&', '>', '<']):
    """Check whether 'text' contains ANY invalid xml chars"""
    return 1 in [c in text for c in invalids]


class DictOrganizer(object):

    def set_dict_iterator(self, dict_iterator):
        self._dict_iterator = dict_iterator

    # Every section will get its own table
    # I need to think of an easy way to flatten out a dictionary
    # parent name, index, table name, data
    def _build_obs_from_dict(self, d, obs, table_name,
                             parent_table_name, parent_index):
        if table_name not in obs:
            obs[table_name] = []
        this_index = len(obs[table_name])
        obs[table_name].append({
            u"_parent_table_name": parent_table_name,
            u"_parent_index": parent_index,
        })
        for k, v in d.items():
            if type(v) != dict and type(v) != list:
                assert k not in obs[table_name][-1]
                obs[table_name][-1][k] = v
        obs[table_name][-1][u"_index"] = this_index

        for k, v in d.items():
            if type(v) == dict:
                kwargs = {
                    "d": v,
                    "obs": obs,
                    "table_name": k,
                    "parent_table_name": table_name,
                    "parent_index": this_index
                }
                self._build_obs_from_dict(**kwargs)
            elif type(v) == list:
                for item in v:
                    kwargs = {
                        "d": item,
                        "obs": obs,
                        "table_name": k,
                        "parent_table_name": table_name,
                        "parent_index": this_index,
                    }
                    self._build_obs_from_dict(**kwargs)
        return obs

    def get_observation_from_dict(self, d):
        assert len(d.keys()) == 1
        root_name = d.keys()[0]
        kwargs = {
            "d": d[root_name],
            "obs": {},
            "table_name": root_name,
            "parent_table_name": u"",
            "parent_index": -1,
        }

        return self._build_obs_from_dict(**kwargs)


class DuplicateUUIDError(Exception):
    pass


def get_forms_shared_with_user(user):
    """
    Return forms shared with a user
    """
    xforms = XForm.objects.filter(
        pk__in=user.xformuserobjectpermission_set.values_list(
            'content_object_id', flat=True
        ).distinct(), downloadable=True)

    return xforms.exclude(user=user).select_related('user')


class XFormMixin(object):

    GEODATA_SUFFIXES = [
        'latitude',
        'longitude',
        'altitude',
        'precision'
    ]

    PREFIX_NAME_REGEX = re.compile(r'(?P<prefix>.+/)(?P<name>[^/]+)$')

    def _set_uuid_in_xml(self, file_name=None):
        """
        Add bind to automatically set UUID node in XML.
        """
        if not file_name:
            file_name = self.file_name()
        file_name, file_ext = os.path.splitext(file_name)

        doc = clean_and_parse_xml(self.xml)
        model_nodes = doc.getElementsByTagName("model")
        if len(model_nodes) != 1:
            raise Exception(u"xml contains multiple model nodes")

        model_node = model_nodes[0]
        instance_nodes = [node for node in model_node.childNodes if
                          node.nodeType == Node.ELEMENT_NODE and
                          node.tagName.lower() == "instance" and
                          not node.hasAttribute("id")]

        if len(instance_nodes) != 1:
            raise Exception(u"Multiple instance nodes without the id "
                            u"attribute, can't tell which is the main one")

        instance_node = instance_nodes[0]

        # get the first child whose id attribute matches our id_string
        survey_nodes = [node for node in instance_node.childNodes
                        if node.nodeType == Node.ELEMENT_NODE and
                        (node.tagName == file_name or
                         node.attributes.get('id'))]

        if len(survey_nodes) != 1:
            raise Exception(
                u"Multiple survey nodes with the id '%s'" % self.id_string)

        survey_node = survey_nodes[0]
        formhub_nodes = [n for n in survey_node.childNodes
                         if n.nodeType == Node.ELEMENT_NODE and
                         n.tagName == "formhub"]

        if len(formhub_nodes) > 1:
            raise Exception(
                u"Multiple formhub nodes within main instance node")
        elif len(formhub_nodes) == 1:
            formhub_node = formhub_nodes[0]
        else:
            formhub_node = survey_node.insertBefore(
                doc.createElement("formhub"), survey_node.firstChild)

        uuid_nodes = [node for node in formhub_node.childNodes if
                      node.nodeType == Node.ELEMENT_NODE and
                      node.tagName == "uuid"]

        if len(uuid_nodes) == 0:
            formhub_node.appendChild(doc.createElement("uuid"))
        if len(formhub_nodes) == 0:
            # append the calculate bind node
            calculate_node = doc.createElement("bind")
            calculate_node.setAttribute(
                "nodeset", "/%s/formhub/uuid" % survey_node.tagName)
            calculate_node.setAttribute("type", "string")
            calculate_node.setAttribute("calculate", "'%s'" % self.uuid)
            model_node.appendChild(calculate_node)

        self.xml = doc.toprettyxml(indent="  ", encoding='utf-8')
        # hack
        # http://ronrothman.com/public/leftbraned/xml-dom-minidom-toprettyxml-\
        # and-silly-whitespace/
        text_re = re.compile('>\n\s+([^<>\s].*?)\n\s+</', re.DOTALL)
        output_re = re.compile('\n.*(<output.*>)\n(  )*')
        prettyXml = text_re.sub('>\g<1></', self.xml)
        inlineOutput = output_re.sub('\g<1>', prettyXml)
        inlineOutput = re.compile('<label>\s*\n*\s*\n*\s*</label>').sub(
            '<label></label>', inlineOutput)
        self.xml = inlineOutput

    class Meta:
        app_label = "viewer"
        proxy = True

    @property
    def has_id_string_changed(self):
        return getattr(self, '_id_string_changed', False)

    def add_instances(self):
        _get_observation_from_dict = DictOrganizer().get_observation_from_dict

        return [_get_observation_from_dict(d)
                for d in self.get_list_of_parsed_instances(flat=False)]

    def _id_string_already_exists_in_account(self, id_string):
        try:
            XForm.objects.get(user=self.user, id_string__iexact=id_string)
        except XForm.DoesNotExist:
            return False

        return True

    def get_unique_id_string(self, id_string, count=0):
        # used to generate a new id_string for new data_dictionary object if
        # id_string already existed
        if self._id_string_already_exists_in_account(id_string):
            if count != 0:
                if re.match(r'\w+_\d+$', id_string):
                    a = id_string.split('_')
                    id_string = "_".join(a[:-1])
            count += 1
            id_string = "{}_{}".format(id_string, count)

            return self.get_unique_id_string(id_string, count)

        return id_string

    def get_survey(self):
        if not hasattr(self, "_survey"):
            try:
                builder = SurveyElementBuilder()
                self._survey = \
                    builder.create_survey_element_from_json(self.json)
            except ValueError:
                xml = bytes(bytearray(self.xml, encoding='utf-8'))
                self._survey = create_survey_element_from_xml(xml)
        return self._survey

    survey = property(get_survey)

    def get_survey_elements(self):
        return self.survey.iter_descendants()

    def get_survey_element(self, name_or_xpath):
        """Searches survey element by xpath first,
        if that fails it searches by name, the first element matching
        the name will be returned.
        """
        # search by xpath first
        element = self.get_element(name_or_xpath)
        if element:
            return element

        # search by name if xpath fails
        fields = [field for field in self.get_survey_elements()
                  if field.name == name_or_xpath]

        return fields[0] if len(fields) else None

    def get_child_elements(self, name_or_xpath):
        """Returns a list of survey elements children in a flat list.
        If the element is a group or multiple select the child elements are
        appended to the list. If the name_or_xpath is a repeat we iterate
        through the child elements as well.
        """
        def flatten(elem, items=[]):
            results = []
            xpath = elem.get_abbreviated_xpath()
            if elem.type in ['group', 'select all that apply'] or \
                    (xpath == name_or_xpath and elem.type == 'repeat'):
                for child in elem.children:
                    results += flatten(child)
            else:
                results = [elem]

            return items + results

        element = self.get_survey_element(name_or_xpath)

        return flatten(element)

    def get_choice_label(self, field, choice_value, lang='English'):
        choices = [choice for choice in field.children
                   if choice.name == choice_value]
        if len(choices):
            choice = choices[0]
            label = choice.label

            if isinstance(label, dict):
                label = label.get(lang, choice.label.values()[0])

            return label

        return choice_value

    def get_mongo_field_names_dict(self):
        """
        Return a dictionary of fieldnames as saved in mongodb with
        corresponding xform field names e.g {"Q1Lg==1": "Q1.1"}
        """
        names = {}
        for elem in self.get_survey_elements():
            names[_encode_for_mongo(unicode(elem.get_abbreviated_xpath()))] = \
                elem.get_abbreviated_xpath()
        return names

    survey_elements = property(get_survey_elements)

    def get_field_name_xpaths_only(self):
        return [
            elem.get_abbreviated_xpath() for elem in self.survey_elements
            if elem.type != '' and elem.type != 'survey'
        ]

    def geopoint_xpaths(self):
        survey_elements = self.get_survey_elements()

        return [e.get_abbreviated_xpath() for e in survey_elements
                if e.bind.get(u'type') == u'geopoint']

    def xpath_of_first_geopoint(self):
        geo_xpaths = self.geopoint_xpaths()

        return len(geo_xpaths) and geo_xpaths[0]

    def xpaths(self, prefix='', survey_element=None, result=None,
               repeat_iterations=4):
        """
        Return a list of XPaths for this survey that will be used as
        headers for the csv export.
        """
        if survey_element is None:
            survey_element = self.survey
        elif question_types_to_exclude(survey_element.type):
            return []

        result = [] if result is None else result
        path = '/'.join([prefix, unicode(survey_element.name)])

        if survey_element.children is not None:
            # add xpaths to result for each child
            indices = [''] if type(survey_element) != RepeatingSection else \
                ['[%d]' % (i + 1) for i in range(repeat_iterations)]
            for i in indices:
                for e in survey_element.children:
                    self.xpaths(path + i, e, result, repeat_iterations)

        if isinstance(survey_element, Question):
            result.append(path)

        # replace the single question column with a column for each
        # item in a select all that apply question.
        if survey_element.bind.get(u'type') == u'select':
            result.pop()
            for child in survey_element.children:
                result.append('/'.join([path, child.name]))
        elif survey_element.bind.get(u'type') == u'geopoint':
            result += self.get_additional_geopoint_xpaths(path)

        return result

    @classmethod
    def get_additional_geopoint_xpaths(cls, xpath):
        """
        This will return a list of the additional fields that are
        added per geopoint.  For example, given a field 'group/gps' it will
        return 'group/_gps_(suffix)' for suffix in
        DataDictionary.GEODATA_SUFFIXES
        """
        match = cls.PREFIX_NAME_REGEX.match(xpath)
        prefix = ''
        name = xpath
        if match:
            prefix = match.groupdict()['prefix']
            name = match.groupdict()['name']

        return ['_'.join([prefix, name,  suffix])
                for suffix in cls.GEODATA_SUFFIXES]

    def _additional_headers(self):
        return [u'_xform_id_string', u'_percentage_complete', u'_status',
                u'_id', u'_attachments', u'_potential_duplicates']

    def get_headers(self, include_additional_headers=False):
        """
        Return a list of headers for a csv file.
        """
        def shorten(xpath):
            l = xpath.split('/')
            return '/'.join(l[2:])

        header_list = [shorten(xpath) for xpath in self.xpaths()]
        header_list += [UUID, SUBMISSION_TIME, TAGS, NOTES, VERSION, DURATION,
                        SUBMITTED_BY]
        if include_additional_headers:
            header_list += self._additional_headers()
        return header_list

    def get_keys(self):
        def remove_first_index(xpath):
            return re.sub(r'\[1\]', '', xpath)

        return [remove_first_index(header) for header in self.get_headers()]

    def get_element(self, abbreviated_xpath):
        if not hasattr(self, "_survey_elements"):
            self._survey_elements = {}
            for e in self.get_survey_elements():
                self._survey_elements[e.get_abbreviated_xpath()] = e

        def remove_all_indices(xpath):
            return re.sub(r"\[\d+\]", u"", xpath)

        clean_xpath = remove_all_indices(abbreviated_xpath)
        return self._survey_elements.get(clean_xpath)

    def get_default_language(self):
        if not hasattr(self, '_default_language'):
            self._default_language = \
                self.survey.to_json_dict().get('default_language')

        return self._default_language

    default_language = property(get_default_language)

    def get_language(self, languages, language_index=0):
        language = None
        if isinstance(languages, list) and len(languages):
            if self.default_language in languages:
                language_index = languages.index(self.default_language)

            language = languages[language_index]

        return language

    def get_label(self, abbreviated_xpath, elem=None, language_index=None):
        elem = self.get_element(abbreviated_xpath) if elem is None else elem

        if elem:
            label = elem.label

            if isinstance(label, dict):
                language = self.get_language(label.keys())
                label = label[language] if language else ''

            return label

    def get_xpath_cmp(self):
        if not hasattr(self, "_xpaths"):
            self._xpaths = [e.get_abbreviated_xpath()
                            for e in self.survey_elements]

        def xpath_cmp(x, y):
            # For the moment, we aren't going to worry about repeating
            # nodes.
            new_x = re.sub(r"\[\d+\]", u"", x)
            new_y = re.sub(r"\[\d+\]", u"", y)
            if new_x == new_y:
                return cmp(x, y)
            if new_x not in self._xpaths and new_y not in self._xpaths:
                return 0
            elif new_x not in self._xpaths:
                return 1
            elif new_y not in self._xpaths:
                return -1
            return cmp(self._xpaths.index(new_x), self._xpaths.index(new_y))

        return xpath_cmp

    def get_variable_name(self, abbreviated_xpath):
        """
        If the abbreviated_xpath has been renamed in
        self.variable_names_json return that new name, otherwise
        return the original abbreviated_xpath.
        """
        if not hasattr(self, "_keys"):
            self._keys = self.get_keys()
        if not hasattr(self, "_headers"):
            self._headers = self.get_headers()

        assert abbreviated_xpath in self._keys, abbreviated_xpath
        i = self._keys.index(abbreviated_xpath)
        header = self._headers[i]

        if not hasattr(self, "_variable_names"):
            from onadata.apps.viewer.models.column_rename import ColumnRename

            self._variable_names = ColumnRename.get_dict()
            assert type(self._variable_names) == dict

        if header in self._variable_names and self._variable_names[header]:
            return self._variable_names[header]

        return header

    def get_list_of_parsed_instances(self, flat=True):
        for i in queryset_iterator(self.instances_for_export(self)):
            # TODO: there is information we want to add in parsed xforms.
            yield i.get_dict(flat=flat)

    def _rename_key(self, d, old_key, new_key):
        assert new_key not in d, d
        d[new_key] = d[old_key]
        del d[old_key]

    def _expand_select_all_that_apply(self, d, key, e):
        if e and e.bind.get(u"type") == u"select":
            options_selected = d[key].split()
            for child in e.children:
                new_key = child.get_abbreviated_xpath()
                d[new_key] = child.name in options_selected

            del d[key]

    def _expand_geocodes(self, d, key, e):
        if e and e.bind.get(u"type") == u"geopoint":
            geodata = d[key].split()
            for i in range(len(geodata)):
                new_key = "%s_%s" % (key, self.geodata_suffixes[i])
                d[new_key] = geodata[i]

    def get_data_for_excel(self):
        for d in self.get_list_of_parsed_instances():
            for key in d.keys():
                e = self.get_element(key)
                self._expand_select_all_that_apply(d, key, e)
                self._expand_geocodes(d, key, e)
            yield d

    def _mark_start_time_boolean(self):
        starttime_substring = 'jr:preloadParams="start"'
        if self.xml.find(starttime_substring) != -1:
            self.has_start_time = True
        else:
            self.has_start_time = False

    def get_survey_elements_of_type(self, element_type):
        return [e for e in self.get_survey_elements()
                if e.type == element_type]

    def get_survey_elements_with_choices(self):
        if not hasattr(self, '_survey_elements_with_choices'):
            choices_type = [
                constants.SELECT_ONE,
                constants.SELECT_ALL_THAT_APPLY
            ]

            self._survey_elements_with_choices = [
                e for e in self.get_survey_elements() if e.type in choices_type
            ]

        return self._survey_elements_with_choices

    def get_media_survey_xpaths(self):
        return [
            e.get_abbreviated_xpath() for e in sum(
                [self.get_survey_elements_of_type(m)
                 for m in KNOWN_MEDIA_TYPES],
                []
            )
        ]

    def _check_version_set(self, survey):
        """
        Checks if the version has been set in the xls file and if not adds
        the default version in this datetime (yyyymmddhhmm) format.
        """

        # get the json and check for the version key
        survey_json = json.loads(survey.to_json())
        if not survey_json.get("version"):
            # set utc time as the default version
            survey_json['version'] = \
                datetime.utcnow().strftime("%Y%m%d%H%M")
            builder = SurveyElementBuilder()
            survey = builder.create_survey_element_from_json(
                json.dumps(survey_json))
        return survey


class XForm(XFormMixin, BaseModel):
    CLONED_SUFFIX = '_cloned'
    MAX_ID_LENGTH = 100

    xls = models.FileField(upload_to=upload_to, null=True)
    json = models.TextField(default=u'')
    description = models.TextField(default=u'', null=True, blank=True)
    xml = models.TextField()

    user = models.ForeignKey(User, related_name='xforms', null=True)
    require_auth = models.BooleanField(default=False)
    shared = models.BooleanField(default=False)
    shared_data = models.BooleanField(default=False)
    downloadable = models.BooleanField(default=True)
    allows_sms = models.BooleanField(default=False)
    encrypted = models.BooleanField(default=False)

    # the following fields are filled in automatically
    sms_id_string = models.SlugField(
        editable=False,
        verbose_name=ugettext_lazy("SMS ID"),
        max_length=MAX_ID_LENGTH,
        default=''
    )
    id_string = models.SlugField(
        editable=False,
        verbose_name=ugettext_lazy("ID"),
        max_length=MAX_ID_LENGTH
    )
    title = models.CharField(editable=False, max_length=XFORM_TITLE_LENGTH)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    last_submission_time = models.DateTimeField(blank=True, null=True)
    has_start_time = models.BooleanField(default=False)
    uuid = models.CharField(max_length=32, default=u'')

    uuid_regex = re.compile(r'(<instance>.*?id="[^"]+">)(.*</instance>)(.*)',
                            re.DOTALL)
    instance_id_regex = re.compile(r'<instance>.*?id="([^"]+)".*</instance>',
                                   re.DOTALL)
    uuid_node_location = 2
    uuid_bind_location = 4
    bamboo_dataset = models.CharField(max_length=60, default=u'')
    instances_with_geopoints = models.BooleanField(default=False)
    instances_with_osm = models.BooleanField(default=False)
    num_of_submissions = models.IntegerField(default=0)
    version = models.CharField(max_length=XFORM_TITLE_LENGTH, null=True,
                               blank=True)
    project = models.ForeignKey('Project')
    created_by = models.ForeignKey(User, null=True, blank=True)
    metadata_set = GenericRelation(MetaData,
                                   content_type_field='content_type_id',
                                   object_id_field="object_id")
    has_hxl_support = models.BooleanField(default=False)
    last_updated_at = models.DateTimeField(auto_now=True)

    tags = TaggableManager()

    class Meta:
        app_label = 'logger'
        unique_together = (("user", "id_string", "project"),
                           ("user", "sms_id_string", "project"))
        verbose_name = ugettext_lazy("XForm")
        verbose_name_plural = ugettext_lazy("XForms")
        ordering = ("id_string",)
        permissions = (
            ("view_xform", _("Can view associated data")),
            ("view_xform_all", _("Can view all associated data")),
            ("view_xform_data", _("Can view submitted data")),
            ("report_xform", _("Can make submissions to the form")),
            ("move_xform", _(u"Can move form between projects")),
            ("transfer_xform", _(u"Can transfer form ownership.")),
            ("can_export_xform_data", _(u"Can export form data")),
            ("delete_submission", _(u"Can delete submissions from form")),
        )

    def file_name(self):
        return self.id_string + ".xml"

    def url(self):
        return reverse(
            "download_xform",
            kwargs={
                "username": self.user.username,
                "id_string": self.id_string
            }
        )

    @property
    def has_instances_with_geopoints(self):
        return self.instances_with_geopoints

    def _set_id_string(self):
        matches = self.instance_id_regex.findall(self.xml)
        if len(matches) != 1:
            raise XLSFormError(_("There should be a single id string."))
        self.id_string = matches[0]

    def _set_title(self):
        text = re.sub(r"\s+", " ", self.xml)
        matches = title_pattern.findall(text)
        title_xml = matches[0][:XFORM_TITLE_LENGTH]

        if len(matches) != 1:
            raise XLSFormError(_("There should be a single title."), matches)

        if self.title and title_xml != self.title:
            title_xml = self.title[:XFORM_TITLE_LENGTH]
            if isinstance(self.xml, str):
                self.xml = self.xml.decode('utf-8')
            self.xml = title_pattern.sub(
                u"<h:title>%s</h:title>" % title_xml, self.xml)

        if contains_xml_invalid_char(title_xml):
            raise XLSFormError(_("Title shouldn't have any invalid xml "
                                 "characters ('>' '&' '<')"))

        self.title = title_xml

    def _set_encrypted_field(self):
        if self.json and self.json != '':
            json_dict = json.loads(self.json)
            if 'submission_url' in json_dict and 'public_key' in json_dict:
                self.encrypted = True
            else:
                self.encrypted = False

    def update(self, *args, **kwargs):
        super(XForm, self).save(*args, **kwargs)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if update_fields:
            kwargs['update_fields'] = list(set(
                list(update_fields) + ['date_modified']
            ))
        if update_fields is None or 'title' in update_fields:
            self._set_title()
        if update_fields is None or 'encrypted' in update_fields:
            self._set_encrypted_field()
        if update_fields is None or 'id_string' in update_fields:
            old_id_string = self.id_string
            if not self.deleted_at:
                self._set_id_string()
            # check if we have an existing id_string,
            # if so, the one must match but only if xform is NOT new
            if self.pk and old_id_string and old_id_string != self.id_string \
                    and self.num_of_submissions > 0:
                raise XLSFormError(
                    _(u"Your updated form's id_string '%(new_id)s' must match "
                      "the existing forms' id_string '%(old_id)s', if form has"
                      " submissions." %
                      {'new_id': self.id_string, 'old_id': old_id_string}))

            if getattr(settings, 'STRICT', True) and \
                    not re.search(r"^[\w-]+$", self.id_string):
                raise XLSFormError(_(u'In strict mode, the XForm ID must be a '
                                     'valid slug and contain no spaces.'))

        if not self.sms_id_string and (update_fields is None or
                                       'id_string' in update_fields):
            try:
                # try to guess the form's wanted sms_id_string
                # from it's json rep (from XLSForm)
                # otherwise, use id_string to ensure uniqueness
                self.sms_id_string = json.loads(self.json).get('sms_keyword',
                                                               self.id_string)
            except:
                self.sms_id_string = self.id_string

        if 'skip_xls_read' in kwargs:
            del kwargs['skip_xls_read']

        super(XForm, self).save(*args, **kwargs)

    def __unicode__(self):
        return getattr(self, "id_string", "")

    def soft_delete(self):
        """
        Return the soft deletion timestamp
        Mark the XForm as soft deleted, appending a timestamped suffix to the
        id_string and sms_id_string to make the initial values available
        without violating the uniqueness constraint.
        """

        soft_deletion_time = datetime.now()
        deletion_suffix = soft_deletion_time.strftime('-deleted-at-%s')
        self.deleted_at = soft_deletion_time
        self.id_string = self.id_string + deletion_suffix
        self.sms_id_string = self.sms_id_string + deletion_suffix
        self.save()

    def submission_count(self, force_update=False):
        if self.num_of_submissions == 0 or force_update:
            count = self.instances.filter(deleted_at__isnull=True).count()
            if count:
                self.num_of_submissions = count
                self.save(update_fields=['num_of_submissions'])
        return self.num_of_submissions
    submission_count.short_description = ugettext_lazy("Submission Count")

    @property
    def submission_count_for_today(self):
        current_timzone_name = timezone.get_current_timezone_name()
        current_timezone = pytz.timezone(current_timzone_name)
        today = datetime.today()
        current_date = current_timezone.localize(
            datetime(today.year,
                     today.month,
                     today.day))
        count = self.instances.filter(
            deleted_at__isnull=True,
            date_created=current_date).count()
        return count

    def geocoded_submission_count(self):
        """Number of geocoded submissions."""
        return self.instances.filter(deleted_at__isnull=True,
                                     geom__isnull=False).count()

    def time_of_last_submission(self):
        if self.last_submission_time is None and self.num_of_submissions > 0:
            try:
                last_submission = self.instances.\
                    filter(deleted_at__isnull=True).latest("date_created")
            except ObjectDoesNotExist:
                pass
            else:
                self.last_submission_time = last_submission.date_created
                self.save()
        return self.last_submission_time

    def time_of_last_submission_update(self):
        try:
            # we also consider deleted instances in this case
            return self.instances.latest("date_modified").date_modified
        except ObjectDoesNotExist:
            pass

    @property
    def hash(self):
        return u'%s' % md5(self.xml.encode('utf8')).hexdigest()

    @property
    def can_be_replaced(self):
        if hasattr(self.submission_count, '__call__'):
            num_submissions = self.submission_count()
        else:
            num_submissions = self.submission_count
        return num_submissions == 0

    @classmethod
    def public_forms(cls):
        return cls.objects.filter(shared=True)


def update_profile_num_submissions(sender, instance, **kwargs):
    profile_qs = User.profile.get_queryset()
    try:
        profile = profile_qs.select_for_update()\
            .get(pk=instance.user.profile.pk)
    except ObjectDoesNotExist:
        pass
    else:
        profile.num_of_submissions -= instance.num_of_submissions
        if profile.num_of_submissions < 0:
            profile.num_of_submissions = 0
        profile.save()


post_delete.connect(update_profile_num_submissions, sender=XForm,
                    dispatch_uid='update_profile_num_submissions')


def set_object_permissions(sender, instance=None, created=False, **kwargs):
    # clear cache
    safe_delete('{}{}'.format(PROJ_FORMS_CACHE, instance.project.pk))
    safe_delete('{}{}'.format(IS_ORG, instance.pk))

    if created:
        from onadata.libs.permissions import OwnerRole
        OwnerRole.add(instance.user, instance)

        if instance.created_by and instance.user != instance.created_by:
            OwnerRole.add(instance.created_by, instance)

        from onadata.libs.utils.project_utils import set_project_perms_to_xform
        set_project_perms_to_xform(instance, instance.project)


post_save.connect(set_object_permissions, sender=XForm,
                  dispatch_uid='xform_object_permissions')


def save_project(sender, instance=None, created=False, **kwargs):
    instance.project.save(update_fields=['date_modified'])


pre_save.connect(save_project, sender=XForm,
                 dispatch_uid='save_project_xform')


def xform_post_delete_callback(sender, instance, **kwargs):
    if instance.project_id:
        safe_delete('{}{}'.format(PROJ_FORMS_CACHE, instance.project_id))
        safe_delete('{}{}'.format(PROJ_SUB_DATE_CACHE, instance.project_id))
        safe_delete('{}{}'.format(PROJ_NUM_DATASET_CACHE, instance.project_id))


post_delete.connect(xform_post_delete_callback,
                    sender=XForm,
                    dispatch_uid='xform_post_delete_callback')


class XFormUserObjectPermission(UserObjectPermissionBase):
    """Guardian model to create direct foreign keys."""

    content_object = models.ForeignKey(XForm)


class XFormGroupObjectPermission(GroupObjectPermissionBase):
    """Guardian model to create direct foreign keys."""

    content_object = models.ForeignKey(XForm)


def update_xform_uuid(username, id_string, new_uuid):
    xform = XForm.objects.get(user__username=username, id_string=id_string)
    # check for duplicate uuid
    count = XForm.objects.filter(uuid=new_uuid).count()

    if count > 0:
        raise DuplicateUUIDError(
            "An xform with uuid: %s already exists" % new_uuid)

    xform.uuid = new_uuid
    xform.save()
