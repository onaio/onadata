import decimal
import json
import math
from future.utils import iteritems
from io import BytesIO

from django.utils.encoding import smart_text
from django.utils.xmlutils import SimplerXMLGenerator

from rest_framework import negotiation
from rest_framework.compat import six
from rest_framework.renderers import (BaseRenderer, JSONRenderer,
                                      StaticHTMLRenderer, TemplateHTMLRenderer)
from rest_framework.utils.encoders import JSONEncoder
from rest_framework_xml.renderers import XMLRenderer

from onadata.libs.utils.osm import get_combined_osm

IGNORE_FIELDS = ['meta/instanceID', 'formhub/uuid']


def pairing(val1, val2):
    """
    Pairing function, encodes two natural numbers into a single natural number.

    Reference: https://en.wikipedia.org/wiki/Pairing_function
    """
    return ((val1 + val2) * (val1 + val2 + 1) >> 1) + val2


def floip_rows_list(data):
    """
    Yields a row of FLOIP results data from dict data.
    """
    for i, key in enumerate(data, 1):
        if not (key.startswith('_') or key in IGNORE_FIELDS):
            session_id = data['_id']
            yield [data['_submission_time'], int(pairing(session_id, i)),
                   data.get('_submitted_by'), data['_id'], key, data[key],
                   None]


def floip_list(data):
    """
    Yields FLOIP results data row from list data.
    """
    for item in data:
        for i in floip_rows_list(item):
            yield i


class DecimalEncoder(JSONEncoder):
    def default(self, obj):
        # Handle Decimal NaN values
        if isinstance(obj, decimal.Decimal) and math.isnan(obj):
            return None
        return JSONEncoder.default(self, obj)


class XLSRenderer(BaseRenderer):
    media_type = 'application/vnd.openxmlformats'
    format = 'xls'
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class XLSXRenderer(XLSRenderer):
    format = 'xlsx'


class CSVRenderer(BaseRenderer):
    media_type = 'text/csv'
    format = 'csv'
    charset = 'utf-8'


class CSVZIPRenderer(BaseRenderer):
    media_type = 'application/octet-stream'
    format = 'csvzip'
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return json.dumps(data) if isinstance(data, dict) else data


class SAVZIPRenderer(BaseRenderer):
    media_type = 'application/octet-stream'
    format = 'savzip'
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return json.dumps(data) if isinstance(data, dict) else data


class SurveyRenderer(BaseRenderer):
    media_type = 'application/xml'
    format = 'xml'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data
# TODO add ZIP(attachments) support


class KMLRenderer(BaseRenderer):
    media_type = 'application/xml'
    format = 'kml'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class GoogleSheetsRenderer(XLSRenderer):
    format = 'gsheets'


class MediaFileContentNegotiation(negotiation.DefaultContentNegotiation):
    def filter_renderers(self, renderers, format):
        """
        If there is a '.json' style format suffix, filter the renderers
        so that we only negotiation against those that accept that format.
        If there is no renderer available, we use MediaFileRenderer.
        """
        renderers = [renderer for renderer in renderers
                     if renderer.format == format]
        if not renderers:
            renderers = [MediaFileRenderer()]

        return renderers


class MediaFileRenderer(BaseRenderer):
    media_type = '*/*'
    format = None
    charset = None
    render_style = 'binary'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class XFormListRenderer(BaseRenderer):
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
                xml.startElement(key, {})
                self._to_xml(xml, value)
                xml.endElement(key)

        elif data is None:
            # Don't output any value
            pass

        else:
            xml.characters(smart_text(data))


class XFormManifestRenderer(XFormListRenderer):
    root_node = "manifest"
    element_node = "mediaFile"
    xmlns = "http://openrosa.org/xforms/xformsManifest"


class TemplateXMLRenderer(TemplateHTMLRenderer):
    format = 'xml'
    media_type = 'text/xml'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context['response']

        if response and response.exception:
            return XMLRenderer().render(
                data, accepted_media_type, renderer_context)

        return super(TemplateXMLRenderer, self).render(
            data, accepted_media_type, renderer_context)


class StaticXMLRenderer(StaticHTMLRenderer):
    format = 'xml'
    media_type = 'text/xml'


class GeoJsonRenderer(BaseRenderer):
    media_type = 'application/json'
    format = 'geojson'
    charset = 'utf-8'

    def render(self, data, media_type=None, renderer_context=None):
        return json.dumps(data)


class OSMRenderer(BaseRenderer):
    media_type = 'text/xml'
    format = 'osm'
    charset = 'utf-8'

    def render(self, data, media_type=None, renderer_context=None):
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


class OSMExportRenderer(BaseRenderer):
    media_type = 'text/xml'
    format = 'osm'
    charset = 'utf-8'


class DebugToolbarRenderer(TemplateHTMLRenderer):
    media_type = 'text/html'
    charset = 'utf-8'
    format = 'debug'
    template_name = 'debug.html'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        data = {
            'debug_data': JSONRenderer().render(
                data, renderer_context=renderer_context
            )
        }

        return super(DebugToolbarRenderer, self).render(
            data, accepted_media_type, renderer_context
        )


class ZipRenderer(BaseRenderer):
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
