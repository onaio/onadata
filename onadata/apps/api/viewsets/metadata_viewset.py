from rest_framework import renderers
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import detail_route
from django.contrib.auth.models import User
from oauth2client.contrib.django_orm import Storage

from onadata.apps.api.permissions import MetaDataObjectPermissions
from onadata.apps.api.tools import get_media_file_response
from onadata.apps.main.models import TokenStorageModel
from onadata.apps.main.models.meta_data import MetaData
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer
from onadata.libs import filters
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.renderers.renderers import MediaFileContentNegotiation, \
    MediaFileRenderer
from onadata.libs.utils.google_sheets import SheetsClient
from onadata.libs.utils.common_tags import (
    GOOGLE_SHEET_ID,
    GOOGLE_SHEET_TITLE,
    GOOGLE_SHEET_DATA_TYPE,
    USER_ID
)
from onadata.apps.api.tools import get_baseviewset_class


BaseViewset = get_baseviewset_class()


class MetaDataViewSet(AuthenticateHeaderMixin,
                      CacheControlMixin,
                      ETagsMixin,
                      BaseViewset,
                      viewsets.ModelViewSet):
    """
    This endpoint provides access to form metadata.
    """

    content_negotiation_class = MediaFileContentNegotiation
    filter_backends = (filters.MetaDataFilter,)
    queryset = MetaData.objects.select_related()
    permission_classes = (MetaDataObjectPermissions,)
    renderer_classes = (
        renderers.JSONRenderer,
        renderers.BrowsableAPIRenderer,
        MediaFileRenderer)
    serializer_class = MetaDataSerializer

    def retrieve(self, request, *args, **kwargs):
        self.object = self.get_object()

        if isinstance(request.accepted_renderer, MediaFileRenderer) \
                and self.object.data_file is not None:

            return get_media_file_response(self.object, request)

        serializer = self.get_serializer(self.object)

        return Response(serializer.data)

    def get_google_sheet_title(self, google_sheet_details):
        '''
        Returns a dictionary with the 'name' and 'updated' keys representing
        the name of the title and a boolean value of whether the title has been
        updated or not
        :param gsheet_details: google sheet metadata dict
        return dict
        '''
        spreadsheet_id = google_sheet_details.get(GOOGLE_SHEET_ID)
        user_id = google_sheet_details.get(USER_ID)
        user = User.objects.get(pk=user_id)
        storage = Storage(TokenStorageModel, 'id', user, 'credential')
        credential = storage.get()
        sheets_client = SheetsClient(auth=credential)
        title = sheets_client.get_google_sheet_title(spreadsheet_id)

        return {
            'name': title,
            'updated': title != google_sheet_details.get(GOOGLE_SHEET_TITLE)
        }

    def get_new_google_sheet_metadata_value(self, gsheet_details, new_details):
        '''
        Returns an updated google sheet metadata string value (data_value)
        :param gsheet_details - dict with current details
        :param new_details - dict with new details
        :return string
        '''
        new_list = []
        for key, val in gsheet_details.items():
            if key in new_details:
                new_list.append('%s %s' % (key, new_details.get(key)))
            else:
                new_list.append('%s %s' % (key, val))

        return ' | '.join(new_list)

    @detail_route(methods=['GET'])
    def google_sheet_title(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        self.object = MetaData.objects.filter(
            data_type=GOOGLE_SHEET_DATA_TYPE, object_id=pk).first()
        if self.object and self.object.data_type == GOOGLE_SHEET_DATA_TYPE:
            google_sheet_details = MetaData.get_google_sheet_details(
                self.object.data_value)
            title = self.get_google_sheet_title(google_sheet_details)

            if title.get('updated'):
                self.object.data_value = self.\
                    get_new_google_sheet_metadata_value(
                        google_sheet_details,
                        {GOOGLE_SHEET_TITLE: title.get('name')}
                    )
                self.object.save()

            return Response({'title': title.get('name')})

        return Response("Google export hasn't been enabled for this form")
