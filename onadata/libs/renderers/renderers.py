from rest_framework.renderers import BaseRenderer


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


class SAVZIPRenderer(BaseRenderer):
    media_type = 'application/octet-stream'
    format = 'savzip'
    charset = None


# TODO add KML, ZIP(attachments) support


class SurveyRenderer(BaseRenderer):
    media_type = 'application/xml'
    format = 'xml'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data
