# -*- coding: utf-8 -*-
"""
Custom renderers for use with django rest_framework.
"""
import decimal
import json
import math
from io import BytesIO

import pytz
from django.utils.dateparse import parse_datetime
from django.utils.encoding import smart_text
from django.utils.xmlutils import SimplerXMLGenerator
from future.utils import iteritems
from rest_framework import negotiation
from rest_framework.compat import six
from rest_framework.renderers import (BaseRenderer, JSONRenderer,
                                      StaticHTMLRenderer, TemplateHTMLRenderer)
from rest_framework.utils.encoders import JSONEncoder
from rest_framework_xml.renderers import XMLRenderer

from onadata.libs.utils.osm import get_combined_osm

IGNORE_FIELDS = [
    'formhub/uuid',
    'meta/contactID',
    'meta/deprecatedID',
    'meta/instanceID',
    'meta/sessionID',
]

FORMLIST_MANDATORY_FIELDS = [
    'formID',
    'name',
    'version',
    'hash',
    'downloadUrl'
]


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
    _submission_time = pytz.timezone('UTC').localize(
        parse_datetime(data['_submission_time'])).isoformat()
    for i, key in enumerate(data, 1):
        if not (key.startswith('_') or key in IGNORE_FIELDS):
            instance_id = data['_id']
            yield [
                _submission_time,  # Timestamp
                int(pairing(instance_id, i)),  # Row ID
                data.get('meta/contactID', data.get('_submitted_by')),
                data.get('meta/sessionID') or data.get('_uuid') or instance_id,
                key,  # Question ID
                data[key],  # Response
                None,  # Response Metadata
            ]


def floip_list(data):
    """
    Yields FLOIP results data row from list data.
    """
    for item in data:
        for i in floip_rows_list(item):
            yield i


class DecimalEncoder(JSONEncoder):
    """
    JSON DecimalEncoder that returns None for decimal nan json values.
    """

    def default(self, obj):  # pylint: disable=method-hidden
        # Handle Decimal NaN values
        if isinstance(obj, decimal.Decimal) and math.isnan(obj):
            return None
        return JSONEncoder.default(self, obj)


class XLSRenderer(BaseRenderer):  # pylint: disable=R0903
    """
    XLSRenderer - renders .xls spreadsheet documents with
                  application/vnd.openxmlformats.
    """
    media_type = 'application/vnd.openxmlformats'
    format = 'xls'
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class XLSXRenderer(XLSRenderer):  # pylint: disable=too-few-public-methods
    """
    XLSRenderer - renders .xlsx spreadsheet documents with
                  application/vnd.openxmlformats.
    """
    format = 'xlsx'


class CSVRenderer(BaseRenderer):  # pylint: disable=abstract-method, R0903
    """
    XLSRenderer - renders comma separated files (CSV) with text/csv.
    """
    media_type = 'text/csv'
    format = 'csv'
    charset = 'utf-8'


class CSVZIPRenderer(BaseRenderer):  # pylint: disable=R0903
    """
    CSVZIPRenderer - renders a ZIP file that contains CSV files.
    """
    media_type = 'application/octet-stream'
    format = 'csvzip'
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return json.dumps(data) if isinstance(data, dict) else data


class SAVZIPRenderer(BaseRenderer):  # pylint: disable=too-few-public-methods
    """
    SAVZIPRenderer - renders a ZIP file that contains SPSS SAV files.
    """
    media_type = 'application/octet-stream'
    format = 'savzip'
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return json.dumps(data) if isinstance(data, dict) else data


class SurveyRenderer(BaseRenderer):  # pylint: disable=too-few-public-methods
    """
    SurveyRenderer - renders XML data.
    """
    media_type = 'application/xml'
    format = 'xml'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class KMLRenderer(BaseRenderer):  # pylint: disable=too-few-public-methods
    """
    KMLRenderer - renders KML XML data.
    """
    media_type = 'application/xml'
    format = 'kml'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class GoogleSheetsRenderer(XLSRenderer):  # pylint: disable=R0903
    """
    GoogleSheetsRenderer = Google Sheets excel exports.
    """
    format = 'gsheets'


class MediaFileContentNegotiation(negotiation.DefaultContentNegotiation):
    """
    MediaFileContentNegotiation - filters renders to only return renders with
                                  matching format.
    """

    def filter_renderers(self, renderers, format):  # pylint: disable=W0622
        """
        If there is a '.json' style format suffix, filter the renderers
        so that we only negotiation against those that accept that format.
        If there is no renderer available, we use MediaFileRenderer.
        """
        renderers = [
            renderer for renderer in renderers if renderer.format == format
        ]
        if not renderers:
            renderers = [MediaFileRenderer()]

        return renderers


class MediaFileRenderer(BaseRenderer):  # pylint: disable=R0903
    """
    MediaFileRenderer - render binary media files.
    """
    media_type = '*/*'
    format = None
    charset = None
    render_style = 'binary'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class XFormListRenderer(BaseRenderer):  # pylint: disable=R0903
    """
    Renderer which serializes to XML.
    """

    media_type = 'text/xml'
    format = 'xml'
    charset = 'utf-8'
    root_node = 'xforms'
    element_node = 'xform'
    xmlns = "http://openrosa.org/xforms/xformsList"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Renders *obj* into serialized XML.
        """
        if data is None:
            return ''
        elif isinstance(data, six.string_types):
            return data

        stream = BytesIO()

        xml = SimplerXMLGenerator(stream, self.charset)
        xml.startDocument()
        xml.startElement(self.root_node, {'xmlns': self.xmlns})

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
            for (key, value) in iteritems(data):
                if key not in FORMLIST_MANDATORY_FIELDS and value is None:
                    continue
                xml.startElement(key, {})
                self._to_xml(xml, value)
                xml.endElement(key)

        elif data is None:
            # Don't output any value
            pass

        else:
            xml.characters(smart_text(data))


class XFormManifestRenderer(XFormListRenderer):  # pylint: disable=R0903
    """
    XFormManifestRenderer - render XFormManifest XML.
    """
    root_node = "manifest"
    element_node = "mediaFile"
    xmlns = "http://openrosa.org/xforms/xformsManifest"


class TemplateXMLRenderer(TemplateHTMLRenderer):  # pylint: disable=R0903
    """
    TemplateXMLRenderer - Render XML template.
    """
    format = 'xml'
    media_type = 'text/xml'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context['response']

        if response and response.exception:
            return XMLRenderer().render(data, accepted_media_type,
                                        renderer_context)

        return super(TemplateXMLRenderer,
                     self).render(data, accepted_media_type, renderer_context)


class StaticXMLRenderer(StaticHTMLRenderer):  # pylint: disable=R0903
    """
    StaticXMLRenderer - render static XML document.
    """
    format = 'xml'
    media_type = 'text/xml'


class GeoJsonRenderer(BaseRenderer):  # pylint: disable=R0903
    """
    GeoJsonRenderer - render .geojson data as json.
    """
    media_type = 'application/json'
    format = 'geojson'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return json.dumps(data)


class OSMRenderer(BaseRenderer):  # pylint: disable=R0903
    """
    OSMRenderer - render .osm data as XML.
    """
    media_type = 'text/xml'
    format = 'osm'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        # Process error before making a list
        if isinstance(data, dict):
            if 'detail' in data:
                return u'<error>' + data['detail'] + '</error>'

        # Combine/concatenate the list of osm files to one file
        def _list(list_or_item):
            if isinstance(list_or_item, list):
                return list_or_item

            return [list_or_item]

        data = [item for item_or_list in data for item in _list(item_or_list)]

        return get_combined_osm(data)


class OSMExportRenderer(BaseRenderer):  # pylint: disable=R0903, W0223
    """
    OSMExportRenderer - render .osm data as XML.
    """
    media_type = 'text/xml'
    format = 'osm'
    charset = 'utf-8'


class DebugToolbarRenderer(TemplateHTMLRenderer):  # pylint: disable=R0903
    """
    DebugToolbarRenderer - render .debug as HTML.
    """
    media_type = 'text/html'
    charset = 'utf-8'
    format = 'debug'
    template_name = 'debug.html'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        data = {
            'debug_data':
            JSONRenderer().render(data, renderer_context=renderer_context)
        }

        return super(DebugToolbarRenderer, self).render(
            data, accepted_media_type, renderer_context)


class ZipRenderer(BaseRenderer):  # pylint: disable=R0903
    """
    ZipRenderer - render .zip files.
    """
    media_type = 'application/octet-stream'
    format = 'zip'
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return json.dumps(data) if isinstance(data, dict) else data


class DecimalJSONRenderer(JSONRenderer):
    """
    Extends the default json renderer to handle Decimal('NaN') values
    """
    encoder_class = DecimalEncoder


class FLOIPRenderer(JSONRenderer):
    """
    FLOIP Results data renderer.
    """
    media_type = 'application/vnd.org.flowinterop.results+json'
    format = 'json'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        request = renderer_context['request']
        response = renderer_context['response']
        results = data
        if request.method == 'GET' and response.status_code == 200:
            if isinstance(data, dict):
                results = [i for i in floip_rows_list(data)]
            else:
                results = [i for i in floip_list(data)]

        return super(FLOIPRenderer, self).render(results, accepted_media_type,
                                                 renderer_context)
