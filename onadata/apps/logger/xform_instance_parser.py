# -*- coding: utf-8 -*-
"""
XForm submission XML parser utility functions.
"""

import logging
import re
from xml.dom import Node

from django.utils.encoding import smart_str
from django.utils.translation import gettext as _

import dateutil.parser
from defusedxml import minidom

from onadata.libs.utils.common_tags import VERSION, XFORM_ID_STRING
from onadata.libs.utils.common_tools import get_abbreviated_xpath


class XLSFormError(Exception):
    pass


class DuplicateInstance(Exception):
    def __str__(self):
        return _("Duplicate Instance")


class InstanceInvalidUserError(Exception):
    def __str__(self):
        return _("Could not determine the user.")


class InstanceParseError(Exception):
    def __str__(self):
        return _("The instance could not be parsed.")


class InstanceEmptyError(InstanceParseError):
    def __str__(self):
        return _("Empty instance")


class InstanceFormatError(Exception):
    pass


class AttachmentNameError(Exception):
    pass


class InstanceEncryptionError(Exception):
    pass


class InstanceMultipleNodeError(Exception):
    pass


class NonUniqueFormIdError(Exception):
    pass


class InstanceEditConflictError(Exception):
    """Raise when a submission edit conflicts with an existing edit."""


def get_meta_from_xml(xml_str, meta_name):
    """
    Return the meta section of an XForm submission XML.
    """
    xml = clean_and_parse_xml(xml_str)
    children = xml.childNodes
    # children ideally contains a single element
    # that is the parent of all survey elements
    if children.length == 0:
        raise ValueError(_("XML string must have a survey element."))
    survey_node = children[0]
    meta_tags = [
        n
        for n in survey_node.childNodes
        if n.nodeType == Node.ELEMENT_NODE
        and (n.tagName.lower() == "meta" or n.tagName.lower() == "orx:meta")
    ]
    if len(meta_tags) == 0:
        return None

    # get the requested tag
    meta_tag = meta_tags[0]
    uuid_tags = [
        n
        for n in meta_tag.childNodes
        if n.nodeType == Node.ELEMENT_NODE
        and (
            n.tagName.lower() == meta_name.lower()
            or n.tagName.lower() == f"orx:{meta_name.lower()}"
        )
    ]
    if len(uuid_tags) == 0:
        return None

    uuid_tag = uuid_tags[0]

    if meta_name == "entity":
        return uuid_tag

    return uuid_tag.firstChild.nodeValue.strip() if uuid_tag.firstChild else None


def get_uuid_from_xml(xml):
    """
    Returns the uuid of an XForm submisison XML
    """

    def _uuid_only(uuid, regex):
        matches = regex.match(uuid)
        if matches and len(matches.groups()) > 0:
            return matches.groups()[0]
        return None

    uuid = get_meta_from_xml(xml, "instanceID")
    regex = re.compile(r"uuid:(.*)")
    if uuid:
        return _uuid_only(uuid, regex)

    # check in survey_node attributes
    xml = clean_and_parse_xml(xml)
    children = xml.childNodes

    # children ideally contains a single element
    # that is the parent of all survey elements
    if children.length == 0:
        raise ValueError(_("XML string must have a survey element."))

    survey_node = children[0]
    uuid = survey_node.getAttribute("instanceID")
    if uuid != "":
        return _uuid_only(uuid, regex)

    return None


def get_submission_date_from_xml(xml):
    """
    Returns submissionDate from an XML submission.
    """
    # check in survey_node attributes
    xml = clean_and_parse_xml(xml)
    children = xml.childNodes
    # children ideally contains a single element
    # that is the parent of all survey elements
    if children.length == 0:
        raise ValueError(_("XML string must have a survey element."))
    survey_node = children[0]
    submission_date = survey_node.getAttribute("submissionDate")
    if submission_date != "":
        return dateutil.parser.parse(submission_date)
    return None


def get_deprecated_uuid_from_xml(xml):
    """
    Returns the deprecatedID from submission XML
    """
    uuid = get_meta_from_xml(xml, "deprecatedID")
    regex = re.compile(r"uuid:(.*)")
    if uuid:
        matches = regex.match(uuid)
        if matches and len(matches.groups()) > 0:
            return matches.groups()[0]
    return None


def clean_and_parse_xml(xml_string):
    """
    Removes spaces between XML tags in ``xml_string``

    Returns an XML object via minidom.parseString(xml_string)
    """
    clean_xml_str = re.sub(r">\s+<", "><", smart_str(xml_string.strip()))
    xml_obj = minidom.parseString(clean_xml_str)

    return xml_obj


# pylint: disable=too-many-branches
def _xml_node_to_dict(node, repeats=None, encrypted=False):  # noqa C901
    repeats = [] if repeats is None else repeats
    if len(node.childNodes) == 0:
        # there's no data for this leaf node
        return None
    if len(node.childNodes) == 1 and node.childNodes[0].nodeType == node.TEXT_NODE:
        # there is data for this leaf node
        return {node.nodeName: node.childNodes[0].nodeValue}
    # this is an internal node
    value = {}

    for child in node.childNodes:
        # handle CDATA str section
        if child.nodeType == child.CDATA_SECTION_NODE:
            return {child.parentNode.nodeName: child.nodeValue}

        child_dict = _xml_node_to_dict(child, repeats)

        if child_dict is None:
            continue

        child_name = child.nodeName
        child_xpath = xpath_from_xml_node(child)
        if list(child_dict) != [child_name]:
            raise AssertionError()
        node_type = dict
        # check if name is in list of repeats and make it a list if so
        # All the photo attachments in an encrypted form use name media
        if child_xpath in repeats or (encrypted and child_name == "media"):
            node_type = list

        if node_type is dict:
            if child_name not in value:
                value[child_name] = child_dict[child_name]
            else:
                # node is repeated, aggregate node values
                node_value = value[child_name]
                # 1. check if the node values is a list
                if not isinstance(node_value, list):
                    # if not a list create
                    value[child_name] = [node_value]
                # 2. parse the node
                child_dict = _xml_node_to_dict(child, repeats)
                # 3. aggregate
                value[child_name].append(child_dict[child_name])
        else:
            if child_name not in value:
                value[child_name] = [child_dict[child_name]]
            else:
                value[child_name].append(child_dict[child_name])
    if not value:
        return None

    return {node.nodeName: value}


def _flatten_dict(data_dict, prefix):
    """
    Return a list of XPath, value pairs.

    :param data_dict: A python dictionary object
    :param prefix: A list of prefixes
    """
    for key, value in data_dict.items():
        new_prefix = prefix + [key]

        if isinstance(value, dict):
            yield from _flatten_dict(value, new_prefix)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                item_prefix = list(new_prefix)  # make a copy
                # note on indexing xpaths: IE5 and later has
                # implemented that [0] should be the first node, but
                # according to the W3C standard it should have been
                # [1]. I'm adding 1 to i to start at 1.
                if i > 0:
                    # hack: removing [1] index to be consistent across
                    # surveys that have a single repitition of the
                    # loop versus mutliple.
                    item_prefix[-1] += f"[{str(i + 1)}]"

                if isinstance(item, dict):
                    yield from _flatten_dict(item, item_prefix)
                else:
                    yield (item_prefix, item)
        else:
            yield (new_prefix, value)


def _flatten_dict_nest_repeats(data_dict, prefix):
    """
    Return a list of XPath, value pairs.

    :param data_dict: A python dictionary object
    :param prefix: A list of prefixes
    :param prefix: A list of prefixes
    """
    for key, value in data_dict.items():
        new_prefix = prefix + [key]
        if isinstance(value, dict):
            yield from _flatten_dict_nest_repeats(value, new_prefix)
        elif isinstance(value, list):
            repeats = []

            for _i, item in enumerate(value):
                item_prefix = list(new_prefix)  # make a copy
                if isinstance(item, dict):
                    repeat = {}

                    for path, r_value in _flatten_dict_nest_repeats(item, item_prefix):
                        # This only considers the first level of repeats
                        repeat.update({"/".join(path[1:]): r_value})
                    repeats.append(repeat)
                else:
                    repeats.append({"/".join(item_prefix[1:]): item})
            yield (new_prefix, repeats)
        else:
            yield (new_prefix, value)


def _gather_parent_node_list(node):
    node_names = []

    # also check for grand-parent node to skip document element
    if node.parentNode and node.parentNode.parentNode:
        node_names.extend(_gather_parent_node_list(node.parentNode))

    node_names.extend([node.nodeName])

    return node_names


def xpath_from_xml_node(node):
    """
    Returns the xpath of an XML node.
    """
    node_names = _gather_parent_node_list(node)

    return "/".join(node_names[1:])


def _get_all_attributes(node):
    """
    Go through an XML document returning all the attributes we see.
    """
    if hasattr(node, "hasAttributes") and node.hasAttributes():
        for key in node.attributes.keys():
            yield key, node.getAttribute(key), node.tagName

    for child in node.childNodes:
        yield from _get_all_attributes(child)


class XFormInstanceParser:
    """
    XFormInstanceParser - parses an XML string into an XML object.
    """

    def __init__(self, xml_str, data_dictionary):
        # pylint: disable=invalid-name
        self.data_dicionary = data_dictionary
        self.parse(xml_str)

    def parse(self, xml_str):
        """
        Parses a submission XML into a python dictionary object.
        """
        self._xml_obj = clean_and_parse_xml(xml_str)
        self._root_node = self._xml_obj.documentElement
        repeats = [
            get_abbreviated_xpath(e.get_xpath())
            for e in self.data_dicionary.get_survey_elements_of_type("repeat")
        ]

        self._dict = _xml_node_to_dict(
            self._root_node, repeats, self.data_dicionary.encrypted
        )
        self._flat_dict = {}

        if self._dict is None:
            raise InstanceEmptyError

        for path, value in _flatten_dict_nest_repeats(self._dict, []):
            self._flat_dict["/".join(path[1:])] = value
        self._set_attributes()

    def get_root_node(self):
        return self._root_node

    def get_root_node_name(self):
        return self._root_node.nodeName

    def get(self, abbreviated_xpath):
        return self.to_flat_dict()[abbreviated_xpath]

    def to_dict(self):
        return self._dict

    def to_flat_dict(self):
        return self._flat_dict

    def get_attributes(self):
        return self._attributes

    def _set_attributes(self):
        # pylint: disable=attribute-defined-outside-init
        self._attributes = {}
        all_attributes = list(_get_all_attributes(self._root_node))
        for key, value, node_name in all_attributes:
            # Since enketo forms may have the template attribute in
            # multiple xml tags, overriding and log when this occurs
            if node_name == "entity":
                # We ignore attributes for the entity node
                continue

            if key in self._attributes:
                logger = logging.getLogger("console_logger")
                logger.debug(
                    "Skipping duplicate attribute: %s with value %s", key, value
                )
                logger.debug(str(all_attributes))
            else:
                self._attributes[key] = value

    def get_xform_id_string(self):
        """
        Returns the submission XML `id` attribute.
        """
        return self._attributes["id"]

    def get_version(self):
        """
        Returns the submission XML version attribute.
        """
        return self._attributes.get("version")

    def get_flat_dict_with_attributes(self):
        """
        Adds the submission XML top level attributes to the resulting python object.
        """
        result = self.to_flat_dict().copy()
        result[XFORM_ID_STRING] = self.get_xform_id_string()

        version = self.get_version()
        if version:
            result[VERSION] = self.get_version()

        return result


def xform_instance_to_dict(xml_str, data_dictionary):
    """
    Parses an XForm submission XML into a python object.
    """
    parser = XFormInstanceParser(xml_str, data_dictionary)
    return parser.to_dict()


def xform_instance_to_flat_dict(xml_str, data_dictionary):
    """
    Parses an XForm submission XML into a flattened python object.
    """
    parser = XFormInstanceParser(xml_str, data_dictionary)
    return parser.to_flat_dict()


def parse_xform_instance(xml_str, data_dictionary):
    """
    Parses an XForm submission XML into a flattened python object
    with additional attributes.
    """
    parser = XFormInstanceParser(xml_str, data_dictionary)
    return parser.get_flat_dict_with_attributes()


def get_entity_uuid_from_xml(xml):
    """Returns the uuid for the XML submission's entity"""
    entity_node = get_meta_from_xml(xml, "entity")
    return entity_node.getAttribute("id")


def get_entity_nodes_from_xml(xml_str):
    """Return all entity nodes in a submission XML in document order.

    A submission can define more than one entity when the entity is created
    within a repeat, so entity nodes are collected from every meta section and
    not just the top-level one.
    """
    xml = clean_and_parse_xml(xml_str)
    entity_nodes = []

    def is_meta(node):
        return node.nodeType == Node.ELEMENT_NODE and node.tagName.lower() in (
            "meta",
            "orx:meta",
        )

    def is_entity(node):
        return node.nodeType == Node.ELEMENT_NODE and node.tagName.lower() in (
            "entity",
            "orx:entity",
        )

    def collect(node):
        for child in node.childNodes:
            if child.nodeType != Node.ELEMENT_NODE:
                continue

            if is_meta(child):
                entity_nodes.extend(n for n in child.childNodes if is_entity(n))
            else:
                collect(child)

    collect(xml)

    return entity_nodes


def get_entity_label_from_node(entity_node):
    """Return the label defined within a submission's entity node."""
    for child in entity_node.childNodes:
        if child.nodeType == Node.ELEMENT_NODE and child.tagName.lower() in (
            "label",
            "orx:label",
        ):
            return child.firstChild.nodeValue if child.firstChild else None

    return None


def _get_node_index(node):
    """Return the position of ``node`` among its same-named siblings."""
    index = 0
    sibling = node.previousSibling

    while sibling is not None:
        if sibling.nodeType == Node.ELEMENT_NODE and sibling.tagName == node.tagName:
            index += 1

        sibling = sibling.previousSibling

    return index


def get_entity_group_data(entity_node, instance_data):
    """Return the submission field values for an entity node's group.

    For an entity defined within a repeat, only the fields of the specific
    repeat instance the entity belongs to are returned. For a top-level entity,
    all the submission fields are returned.

    :param entity_node: The submission's entity XML node
    :param instance_data: The submission's flat data dictionary
    """
    # entity -> meta -> group holding the entity
    node = entity_node.parentNode.parentNode
    root_node = node.ownerDocument.documentElement

    while node is not None and node is not root_node:
        repeat_data = instance_data.get(xpath_from_xml_node(node))

        if isinstance(repeat_data, list):
            index = _get_node_index(node)

            if index < len(repeat_data):
                return repeat_data[index]

            return {}

        node = node.parentNode

    return instance_data
