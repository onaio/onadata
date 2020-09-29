import re
from rest_framework.decorators import action
from onadata.apps.logger.models.open_data import OpenData
from onadata.apps.api.viewsets.open_data_viewset import OpenDataViewSet
from onadata.apps.logger.models.xform import XForm
from onadata.libs.utils.common_tags import (DURATION, ID, ATTACHMENTS,
    	                                    MEDIA_ALL_RECEIVED, MEDIA_COUNT,
    	                                    NOTES, SUBMISSION_TIME, NA_REP,
                                            SUBMITTED_BY, TAGS, TOTAL_MEDIA,
                                            UUID, VERSION, REVIEW_STATUS,
                                            REVIEW_COMMENT, REPEAT_SELECT_TYPE,
                                            MULTIPLE_SELECT_TYPE)

def get_tableau_headers(xform):
    """
    Return a list of headers for Tableau.
    """
    def shorten(xpath):
        xpath_list = xpath.split('/')
        return '/'.join(xpath_list[2:])

    header_list = [
        shorten(xpath) for xpath in xform.xpaths(
            repeat_iterations=1)]
    header_list += [
        ID, UUID, SUBMISSION_TIME, TAGS, NOTES, REVIEW_STATUS,
        REVIEW_COMMENT, VERSION, DURATION, SUBMITTED_BY, TOTAL_MEDIA,
        MEDIA_COUNT, MEDIA_ALL_RECEIVED
    ]
    return header_list


class TableauViewSet(OpenDataViewSet):
    def data(self, request, **kwargs):
        return None
    
    @action(methods=['GET'], detail=True)
    def schema(self, request, **kwargs):
        data = {}
        self.object = self.get_object()
        if isinstance(self.object.content_object, XForm):
            xform = self.object.content_object
            headers = get_tableau_headers(xform)
            repeat_fields = []
            repeat_column_headers = []
            nested_repeat_column_headers = []

            for child in headers:
                # Use regex to identify indexes in headers
                repeat_count = re.findall(r"\[+\d+\]", child) 
                re_match = re.search(r"\[+\d+\]", child)
                if re_match:
                    # Using the repeat count length
                    # to check for nested repeats
                    if len(repeat_count) > 1:
                        nested_re_match = re.search(
                            r"\[+\d+\]",
                            child[re_match.span()[1]:]
                        )
                        if nested_re_match:
                            nested_repeat_column_headers.append(
                                re.sub(r"/", "", child[re_match.span()[1]:][
                                    nested_re_match.span()[1]:]))
                    else:
                        # Generate column headers for new tableau table
                        repeat_column_headers.append(
                            re.sub(r"/", "", child[re_match.span()[1]:]
                        ))
            data = [{
                'column_headers': headers,
                'connection_name': "%s_%s" % (xform.project_id,
                                              xform.id_string),
                'table_alias': xform.title
            },
            {
                'column_headers': repeat_column_headers,
                'connection_name': "%s_%s" % (xform.project_id,
                                              xform.id_string),
                'table_alias': xform.title
            },
            {
                'column_headers': nested_repeat_column_headers,
                'connection_name': "%s_%s" % (xform.project_id,
                                              xform.id_string),
                'table_alias': xform.title
            }]

