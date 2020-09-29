import re
from rest_framework import status
from collections import defaultdict
from rest_framework.decorators import action
from rest_framework.response import Response
from onadata.apps.logger.models.xform import XForm
from onadata.apps.api.viewsets.open_data_viewset import OpenDataViewSet


class TableauViewSet(OpenDataViewSet):
    def data(self, request, **kwargs):
        return None

    @action(methods=['GET'], detail=True)
    def schema(self, request, **kwargs):
        self.object = self.get_object()
        if isinstance(self.object.content_object, XForm):
            xform = self.object.content_object
            headers = xform.get_headers(repeat_iterations=1)
            schemas = defaultdict(dict)

            for child in headers:
                # Use regex to identify number of repeats
                repeat_count = len(re.findall(r"\[+\d+\]", child))
                if re.search(r"\[+\d+\]", child):
                    table_name = child.split('/')[repeat_count - 1]
                    table_name = table_name.replace('[1]', '')
                    if not schemas[table_name].get('headers'):
                        schemas[table_name]['headers'] = []
                    schemas[table_name]['headers'].append(
                        child.split('/')[repeat_count:])
                    if not schemas[table_name].get('connection_name'):
                        schemas[table_name]['connection_name'] =\
                            f"{xform.project_id}_{xform.id_string}_{table_name}"  # noqa
                    if not schemas[table_name].get('table_alias'):
                        schemas[table_name]['table_alias'] =\
                            f"{xform.title}_{xform.id_string}_{table_name}"
                else:
                    if not schemas['data'].get('headers'):
                        schemas['data']['headers'] = []
                    if not schemas['data'].get('connection_name'):
                        schemas['data']['connection_name'] =\
                            f"{xform.project_id}_{xform.id_string}"
                    if not schemas['data'].get('table_alias'):
                        schemas['data']['table_alias'] =\
                            f"{xform.title}_{xform.id_string}"

                    # No need to split the repeats down
                    schemas['data']['headers'].append(child)
            response_data = [
                v for k, v in dict(schemas).items()]
            return Response(data=response_data, status=status.HTTP_200_OK)

        return Response(status=status.HTTP_404_NOT_FOUND)
