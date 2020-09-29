import re
from rest_framework.decorators import action, schema
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


class TableauViewSet(OpenDataViewSet):
    def data(self, request, **kwargs):
        return None
    
    @action(methods=['GET'], detail=True)
    def schema(self, request, **kwargs):
        self.object = self.get_object()
        if isinstance(self.object.content_object, XForm):
            xform = self.object.content_object
            headers = xform.get_headers(repeat_iterations=1)
            schemas = {'data': {
                'connection_name': f"{xform.project_id}_{xform.id_string}",
                'headers': []
            }}

            for child in headers:
                # Use regex to identify number of repeats
                repeat_count = re.findall(r"\[+\d+\]", child)
                if re.search(r"\[+\d+\]", child):
                    table_name = child.split('/')[repeat_count - 1]
                    table_name = table_name.replace('[1]', '')
                    schemas['table_name']['headers'].append(
                        child.split('/')[repeat_count:])
                    if not schemas[table_name].get('connection_name'):
                        schemas[table_name]['connection_name'] = f"{xform.project_id}_{xform.id_string}_{table_name}"
                else:
                    # No need to split the repeats down
                    schemas['data']['headers'].append(child)
            return schemas
