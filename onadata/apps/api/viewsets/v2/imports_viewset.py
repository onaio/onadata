import os

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.core.files.storage import default_storage
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.exceptions import ParseError
from rest_framework.decorators import action

from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.api.permissions import XFormPermissions
from onadata.apps.logger.models import XForm
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.utils.async_status import get_active_tasks
from onadata.libs.utils.csv_import import submission_xls_to_csv, submit_csv, submit_csv_async
from onadata.settings.common import CSV_EXTENSION, XLS_EXTENSIONS

BaseViewset = get_baseviewset_class()


class ImportsViewSet(ETagsMixin, CacheControlMixin,
                     viewsets.ViewSet):
    permission_classes = [XFormPermissions]
    queryset = XForm.objects.filter(deleted_at__isnull=True)

    def get_queryset(self):
        return XForm.objects.filter(deleted_at__isnull=True)

    def get_object(self, pk: int):
        queryset = self.get_queryset()
        obj = get_object_or_404(queryset, pk=pk)
        self.check_object_permissions(self.request, obj)
        return obj

    @action(detail=True, methods=["POST"])
    def start(self, request, pk: int = None):
        xform = self.get_object(pk)
        resp = {}
        import ipdb; ipdb.set_trace()
        csv_file = request.FILES.get("csv_file", None)
        xls_file = request.FILES.get("xls_file", None)
        if csv_file is None and xls_file is None:
            resp.update({"error": "csv_file and xls_file field empty"})
        elif xls_file and xls_file.name.split(".")[-1] not in XLS_EXTENSIONS:
            resp.update({"error": "xls_file not an excel file"})
        elif csv_file and csv_file.name.split(".")[-1] != CSV_EXTENSION:
            resp.update({"error": "csv_file not a csv file"})
        else:
            if xls_file and xls_file.name.split(".")[-1] in XLS_EXTENSIONS:
                csv_file = submission_xls_to_csv(xls_file)
            overwrite = request.query_params.get("overwrite")
            overwrite = (overwrite.lower() == "true" if isinstance(
                overwrite, str) else overwrite)
            size_threshold = settings.CSV_FILESIZE_IMPORT_ASYNC_THRESHOLD
            try:
                csv_size = csv_file.size
            except AttributeError:
                csv_size = csv_file.__sizeof__()
            csv_file.seek(0)
            upload_to = os.path.join(request.user.username, "csv_imports",
                                     csv_file.name)
            file_name = default_storage.save(upload_to, csv_file)
            task = submit_csv_async.delay(request.user.username,
                                          self.object.pk, file_name, overwrite)
            if task is None:
                raise ParseError("Task not found")
            resp.update({"task_id": task.task_id})

            return Response(
                data=resp,
                status=status.HTTP_200_OK
                if resp.get("error") is None else status.HTTP_400_BAD_REQUEST,
                content_type="application/json"
            )

    def retrieve(self, request, pk: int = None):
        """Returns csv import async tasks that belong to this form"""
        xform = self.get_object(pk)

        task_names = ["onadata.libs.utils.csv_import.submit_csv_async"]
        if xform:
            return Response(
                data=get_active_tasks(task_names, xform),
                status=status.HTTP_200_OK,
                content_type="application/json",
            )
