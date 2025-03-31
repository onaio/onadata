# -*- coding: utf-8 -*-
"""
Custom renderers for use with django rest_framework.
"""

import decimal
import json
import math
from datetime import timezone as tz
from io import BytesIO, StringIO
from typing import Tuple

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.encoding import force_str, smart_str
from django.utils.xmlutils import SimplerXMLGenerator

import six
from rest_framework import negotiation
from rest_framework.renderers import (
    BaseRenderer,
    JSONRenderer,
    StaticHTMLRenderer,
    TemplateHTMLRenderer,
)
from rest_framework.utils.encoders import JSONEncoder
from rest_framework_xml.renderers import XMLRenderer
from six import iteritems

from onadata.libs.utils.cache_tools import (
    XFORM_MANIFEST_CACHE_LOCK_TTL,
    XFORM_MANIFEST_CACHE_TTL,
    safe_cache_add,
    safe_cache_get,
    safe_cache_set,
    safe_delete,
)
from onadata.libs.utils.osm import get_combined_osm

IGNORE_FIELDS = [
    "formhub/uuid",
    "meta/contactID",
    "meta/deprecatedID",
    "meta/instanceID",
    "meta/sessionID",
]

FORMLIST_MANDATORY_FIELDS = ["formID", "name", "version", "hash", "downloadUrl"]


def pairing(val1, val2):
    """
    Pairing function, encodes two natural numbers into a single natural number.

    Reference: https://en.wikipedia.org/wiki/Pairing_function
    """
    return (((val1 + val2) * (val1 + val2 + 1)) / 2) + val2


def floip_rows_list(data):
    """
    Yields a row of FLOIP results data from dict data.
    """
    try:
        _submission_time = (
            parse_datetime(data["_submission_time"]).replace(tzinfo=tz.utc)
        ).isoformat()

    except ValueError:
        _submission_time = data["_submission_time"]

    for i, key in enumerate(data, 1):
        if not (key.startswith("_") or key in IGNORE_FIELDS):
            instance_id = data["_id"]
            yield [
                _submission_time,  # Timestamp
                int(pairing(instance_id, i)),  # Row ID
                data.get("meta/contactID", data.get("_submitted_by")),
                data.get("meta/sessionID") or data.get("_uuid") or instance_id,
                key,  # Question ID
                data[key],  # Response
                None,  # Response Metadata
            ]


def floip_list(data):
    """
    Yields FLOIP results data row from list data.
    """
    for item in data:
        yield from floip_rows_list(item)


def _pop_xml_attributes(xml_dictionary: dict) -> Tuple[dict, dict]:
    """
    Extracts XML attributes from the ``xml_dictionary``.
    """
    ret = xml_dictionary.copy()
    attributes = {}

    for key, value in xml_dictionary.items():
        if key.startswith("@"):
            attributes.update({key.replace("@", ""): value})
            del ret[key]

    return ret, attributes


class DecimalEncoder(JSONEncoder):
    """
    JSON DecimalEncoder that returns None for decimal nan json values.
    """

    # pylint: disable=method-hidden
    def default(self, obj):
        """
        JSON DecimalEncoder that returns None for decimal nan json values.
        """
        # Handle Decimal NaN values
        if isinstance(obj, decimal.Decimal) and math.isnan(obj):
            return None
        return JSONEncoder.default(self, obj)


# pylint: disable=abstract-method,too-few-public-methods
class XLSRenderer(BaseRenderer):
    """
    XLSRenderer - renders .xls spreadsheet documents with
                  application/vnd.openxmlformats.
    """

    media_type = "application/vnd.openxmlformats"
    format = "xls"
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Encode ``data`` string to 'utf-8'.
        """
        if isinstance(data, six.text_type):
            return data.encode("utf-8")
        return data


class XLSXRenderer(XLSRenderer):  # pylint: disable=too-few-public-methods
    """
    XLSRenderer - renders .xlsx spreadsheet documents with
                  application/vnd.openxmlformats.
    """

    format = "xlsx"


# pylint: disable=abstract-method, too-few-public-methods
class CSVRenderer(BaseRenderer):
    """
    XLSRenderer - renders comma separated files (CSV) with text/csv.
    """

    media_type = "text/csv"
    format = "csv"
    charset = "utf-8"


class CSVZIPRenderer(BaseRenderer):  # pylint: disable=too-few-public-methods
    """
    CSVZIPRenderer - renders a ZIP file that contains CSV files.
    """

    media_type = "application/octet-stream"
    format = "csvzip"
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, six.text_type):
            return data.encode("utf-8")
        if isinstance(data, dict):
            return json.dumps(data).encode("utf-8")
        return data


class SAVZIPRenderer(BaseRenderer):  # pylint: disable=too-few-public-methods
    """
    SAVZIPRenderer - renders a ZIP file that contains SPSS SAV files.
    """

    media_type = "application/octet-stream"
    format = "savzip"
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, six.text_type):
            return data.encode("utf-8")
        if isinstance(data, dict):
            return json.dumps(data).encode("utf-8")
        return data


class SurveyRenderer(BaseRenderer):  # pylint: disable=too-few-public-methods
    """
    SurveyRenderer - renders XML data.
    """

    media_type = "application/xml"
    format = "xml"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class KMLRenderer(BaseRenderer):  # pylint: disable=too-few-public-methods
    """
    KMLRenderer - renders KML XML data.
    """

    media_type = "application/xml"
    format = "kml"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class GoogleSheetsRenderer(XLSRenderer):  # pylint: disable=too-few-public-methods
    """
    GoogleSheetsRenderer = Google Sheets excel exports.
    """

    format = "gsheets"


class MediaFileContentNegotiation(negotiation.DefaultContentNegotiation):
    """
    MediaFileContentNegotiation - filters renders to only return renders with
                                  matching format.
    """

    def filter_renderers(self, renderers, format):  # pylint: disable=redefined-builtin
        """
        If there is a '.json' style format suffix, filter the renderers
        so that we only negotiation against those that accept that format.
        If there is no renderer available, we use MediaFileRenderer.
        """
        renderers = [renderer for renderer in renderers if renderer.format == format]
        if not renderers:
            renderers = [MediaFileRenderer()]

        return renderers


class MediaFileRenderer(BaseRenderer):  # pylint: disable=too-few-public-methods
    """
    MediaFileRenderer - render binary media files.
    """

    media_type = "*/*"
    format = None
    charset = None
    render_style = "binary"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, six.text_type):
            return data.encode("utf-8")
        return data


class XFormListRenderer(BaseRenderer):  # pylint: disable=too-few-public-methods
    """
    Renderer which serializes to XML.
    """

    media_type = "text/xml"
    format = "xml"
    charset = "utf-8"
    root_node = "xforms"
    element_node = "xform"
    xmlns = "http://openrosa.org/xforms/xformsList"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Renders *obj* into serialized XML.
        """
        if data is None:
            return ""
        if isinstance(data, six.string_types):
            return data

        stream = BytesIO()

        xml = SimplerXMLGenerator(stream, self.charset)
        xml.startDocument()
        xml.startElement(self.root_node, {"xmlns": self.xmlns})

        self._to_xml(xml, data)

        xml.endElement(self.root_node)
        xml.endDocument()

        return stream.getvalue()

    def _to_xml(self, xml, data):
        if isinstance(data, (list, tuple)):
            for item in data:
                xml.startElement(self.element_node, {})
                self._to_xml(xml, item)
                xml.endElement(self.element_node)

        elif isinstance(data, dict):
            for key, value in iteritems(data):
                if key not in FORMLIST_MANDATORY_FIELDS and value is None:
                    continue
                xml.startElement(key, {})
                self._to_xml(xml, value)
                xml.endElement(key)

        elif data is None:
            # Don't output any value
            pass

        else:
            xml.characters(smart_str(data))


class StreamRendererMixin:
    """Mixin class for renderers that support stream responses"""

    def _get_current_buffer_data(self):
        if hasattr(self, "stream"):
            ret = self.stream.getvalue()
            self.stream.truncate(0)
            self.stream.seek(0)
            return ret
        return None

    def stream_data(self, data, serializer):
        """Returns a streaming response."""
        if data is None:
            yield ""

        # pylint: disable=attribute-defined-outside-init
        self.stream = StringIO()
        xml = SimplerXMLGenerator(self.stream, self.charset)
        xml.startDocument()
        yield self._get_current_buffer_data()
        xml.startElement(self.root_node, {"xmlns": self.xmlns})
        yield self._get_current_buffer_data()
        data = iter(data)

        try:
            out = next(data)
        except StopIteration:
            out = None

        while out:
            try:
                next_item = next(data)
                out = serializer(out).data
                out, attributes = _pop_xml_attributes(out)
                xml.startElement(self.element_node, attributes)
                self._to_xml(xml, out)
                xml.endElement(self.element_node)
                yield self._get_current_buffer_data()
                out = next_item
            except StopIteration:
                out = serializer(out).data
                out, attributes = _pop_xml_attributes(out)
                xml.startElement(self.element_node, attributes)
                self._to_xml(xml, out)
                xml.endElement(self.element_node)
                yield self._get_current_buffer_data()
                break

        xml.endElement(self.root_node)
        yield self._get_current_buffer_data()
        xml.endDocument()
        yield self._get_current_buffer_data()


# pylint: disable=too-few-public-methods
class XFormManifestRenderer(XFormListRenderer, StreamRendererMixin):
    """
    XFormManifestRenderer - render XFormManifest XML.
    """

    root_node = "manifest"
    element_node = "mediaFile"
    xmlns = "http://openrosa.org/xforms/xformsManifest"

    def __init__(self, cache_key=None) -> None:
        self.cache_key = cache_key
        self.can_update_cache = False
        self.cache_lock_key = None

    def _get_current_buffer_data(self):
        data = super()._get_current_buffer_data()

        if data and self.can_update_cache:
            data = data.strip()
            cached_manifest: str | None = safe_cache_get(self.cache_key)

            if cached_manifest is not None:
                cached_manifest += data
                safe_cache_set(
                    self.cache_key, cached_manifest, XFORM_MANIFEST_CACHE_TTL
                )

                if data.endswith("</manifest>"):
                    # We are done, release the lock
                    safe_delete(self.cache_lock_key)

            else:
                safe_cache_set(self.cache_key, data, XFORM_MANIFEST_CACHE_TTL)

        return data

    def stream_data(self, data, serializer):
        if self.cache_key:
            # In the case of concurrent requests, we ensure only the first
            # request is updating the cache
            self.cache_lock_key = f"{self.cache_key}_lock"
            self.can_update_cache = safe_cache_add(
                self.cache_lock_key, "true", XFORM_MANIFEST_CACHE_LOCK_TTL
            )

        return super().stream_data(data, serializer)


# pylint: disable=too-few-public-methods
class TemplateXMLRenderer(TemplateHTMLRenderer):
    """
    TemplateXMLRenderer - Render XML template.
    """

    format = "xml"
    media_type = "text/xml"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context["response"]

        if response and response.exception:
            return XMLRenderer().render(data, accepted_media_type, renderer_context)

        return super().render(data, accepted_media_type, renderer_context)


class InstanceXMLRenderer(XMLRenderer, StreamRendererMixin):
    """
    InstanceXMLRenderer - Renders Instance XML
    """

    root_tag_name = "submission-batch"
    item_tag_name = "submission-item"

    def stream_data(self, data, serializer):
        """Returns a streaming response."""
        if data is None:
            yield ""

        # pylint: disable=attribute-defined-outside-init
        self.stream = StringIO()

        xml = SimplerXMLGenerator(self.stream, self.charset)
        xml.startDocument()
        xml.startElement(self.root_tag_name, {"serverTime": timezone.now().isoformat()})

        yield self._get_current_buffer_data()

        data = iter(data)

        try:
            out = next(data)
        except StopIteration:
            out = None

        while out:
            try:
                next_item = next(data)
                out = serializer(out).data
                out, attributes = _pop_xml_attributes(out)
                xml.startElement(self.item_tag_name, attributes)
                self._to_xml(xml, out)
                xml.endElement(self.item_tag_name)
                yield self._get_current_buffer_data()
                out = next_item
            except StopIteration:
                out = serializer(out).data
                out, attributes = _pop_xml_attributes(out)
                xml.startElement(self.item_tag_name, attributes)
                self._to_xml(xml, out)
                xml.endElement(self.item_tag_name)
                yield self._get_current_buffer_data()
                break

        xml.endElement(self.root_tag_name)
        xml.endDocument()

        yield self._get_current_buffer_data()

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return ""

        if not isinstance(data, list):
            return data

        stream = StringIO()

        xml = SimplerXMLGenerator(stream, self.charset)
        xml.startDocument()
        xml.startElement(self.root_tag_name, {"serverTime": timezone.now().isoformat()})

        self._to_xml(xml, data)

        xml.endElement(self.root_tag_name)
        xml.endDocument()

        return stream.getvalue()

    def _to_xml(self, xml, data):
        if isinstance(data, (list, tuple)):
            for item in data:
                item, attributes = _pop_xml_attributes(item)
                xml.startElement(self.item_tag_name, attributes)
                self._to_xml(xml, item)
                xml.endElement(self.item_tag_name)

        elif isinstance(data, dict):
            for key, value in data.items():
                if not key:
                    self._to_xml(xml, value)
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        xml.startElement(key, {})
                        self._to_xml(xml, item)
                        xml.endElement(key)

                elif isinstance(value, dict):
                    value, attributes = _pop_xml_attributes(value)
                    xml.startElement(key, attributes)
                    self._to_xml(xml, value)
                    xml.endElement(key)
                else:
                    xml.startElement(key, {})
                    self._to_xml(xml, value)
                    xml.endElement(key)

        elif data is None:
            pass

        else:
            xml.characters(force_str(data))


class StaticXMLRenderer(StaticHTMLRenderer):  # pylint: disable=too-few-public-methods
    """
    StaticXMLRenderer - render static XML document.
    """

    format = "xml"
    media_type = "text/xml"


class GeoJsonRenderer(BaseRenderer):  # pylint: disable=too-few-public-methods
    """
    GeoJsonRenderer - render .geojson data as json.
    """

    media_type = "application/json"
    format = "geojson"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return json.dumps(data)


class OSMRenderer(BaseRenderer):  # pylint: disable=too-few-public-methods
    """
    OSMRenderer - render .osm data as XML.
    """

    media_type = "text/xml"
    format = "osm"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        # Process error before making a list
        if isinstance(data, dict):
            if "detail" in data:
                return "<error>" + data["detail"] + "</error>"

        # Combine/concatenate the list of osm files to one file
        def _list(list_or_item):
            if isinstance(list_or_item, list):
                return list_or_item

            return [list_or_item]

        data = [item for item_or_list in data for item in _list(item_or_list)]

        return get_combined_osm(data)


# pylint: disable=too-few-public-methods,abstract-method
class OSMExportRenderer(BaseRenderer):
    """
    OSMExportRenderer - render .osm data as XML.
    """

    media_type = "text/xml"
    format = "osm"
    charset = "utf-8"


# pylint: disable=too-few-public-methods
class DebugToolbarRenderer(TemplateHTMLRenderer):
    """
    DebugToolbarRenderer - render .debug as HTML.
    """

    media_type = "text/html"
    charset = "utf-8"
    format = "debug"
    template_name = "debug.html"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        data = {
            "debug_data": str(
                JSONRenderer().render(data, renderer_context=renderer_context),
                self.charset,
            )
        }

        return super().render(data, accepted_media_type, renderer_context)


class ZipRenderer(BaseRenderer):  # pylint: disable=too-few-public-methods
    """
    ZipRenderer - render .zip files.
    """

    media_type = "application/octet-stream"
    format = "zip"
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, six.text_type):
            return data.encode("utf-8")
        if isinstance(data, dict):
            return json.dumps(data).encode("utf-8")
        return data


class DecimalJSONRenderer(JSONRenderer):
    """
    Extends the default json renderer to handle Decimal('NaN') values
    """

    encoder_class = DecimalEncoder


class FLOIPRenderer(JSONRenderer):
    """
    FLOIP Results data renderer.
    """

    media_type = "application/vnd.org.flowinterop.results+json"
    format = "json"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        request = renderer_context["request"]
        response = renderer_context["response"]
        results = data
        if request.method == "GET" and response.status_code == 200:
            if isinstance(data, dict):
                results = list(floip_rows_list(data))
            else:
                results = list(floip_list(data))

        return super().render(results, accepted_media_type, renderer_context)
