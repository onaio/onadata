import json
import os

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.core.files.storage import default_storage
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.exceptions import ParseError, ErrorDetail
from rest_framework.decorators import action

from onadata.celeryapp import app
from onadata.apps.api.tools import get_baseviewset_class
from onadata.apps.api.permissions import ImportPermissions
from onadata.apps.logger.models import XForm
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.authenticate_header_mixin import AuthenticateHeaderMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.utils.async_status import get_active_tasks
from onadata.libs.utils.csv_import import (
    submission_xls_to_csv,
    submit_csv,
    submit_csv_async,
)
from onadata.settings.common import CSV_EXTENSION, XLS_EXTENSIONS

BaseViewset = get_baseviewset_class()


def terminate_import_task(task_uuid: str, xform_pk: int) -> bool:
    task_details = app.control.inspect().query_task(task_uuid)
    if task_details and task_details["args"][1] == xform_pk:
        app.control.terminate(task_uuid)
        return True
    return False


class ImportsViewSet(
    AuthenticateHeaderMixin, ETagsMixin, CacheControlMixin, viewsets.ViewSet
):
    permission_classes = [ImportPermissions]
    queryset = XForm.objects.filter(deleted_at__isnull=True)
    task_names = ["onadata.libs.utils.csv_import.submit_csv_async"]

    def get_queryset(self):
        return XForm.objects.filter(deleted_at__isnull=True)

    def get_object(self, pk: int):
        queryset = self.get_queryset()
        obj = get_object_or_404(queryset, pk=pk)
        self.check_object_permissions(self.request, obj)
        return obj

    def _get_active_tasks(self, xform: XForm) -> str:
        """
        Utility function to retrieve the active tasks of an XForm
        """
        return get_active_tasks(self.task_names, xform)

    def create(self, request, pk: int = None) -> Response:
        """
        Starts a new Import task for a given form; The route processes imports asynchronously
        unless the `DISABLE_ASYNCHRONOUS_IMPORTS` setting is set to false.

        Curl example:

        $ curl -X POST "http://<domain>/api/v2/imports/<xform_id>"

        Supported Query Parameters:

        - [Optional] overwrite: bool = Whether the server should permanently delete the data currently available on
          the form then reimport the data using the csv_file/xls_file sent with the request.

        Required Request Arguements:

        - csv_file: file = A CSV File containing the forms data
        - xls_file: file = An XLSX file containing the forms data

        Possible Response status codes:

        - 202 Accepted: Server has successfully accepted your request for data import and has queued the task
        - 200 Ok: Server has successfully imported your data to the form; Only returned when asynchronous imports are disabled
        - 400 Bad Request: Request has been refused due to incorrect/missing csv_file or xls_file file
        - 403 Forbidden: The request was valid but the server refused to process it. An explanation on why it was refused can be found in the JSON Response
        - 401 Unauthorized: The request has been refused due to missing authentication
        """
        xform = self.get_object(pk)
        resp = {}
        csv_file = request.FILES.get("csv_file", None)
        xls_file = request.FILES.get("xls_file", None)
        status_code = status.HTTP_400_BAD_REQUEST

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
            overwrite = (
                overwrite.lower() == "true" if isinstance(overwrite, str) else overwrite
            )

            # Block imports from running when an overwrite is ongoing
            active_tasks = json.loads(self._get_active_tasks(xform))
            for task in active_tasks:
                if task.get("overwrite", False):
                    task_id = task.get("job_uuid")
                    resp.update(
                        {
                            "detail": ErrorDetail(
                                f"An ongoing overwrite request with the ID {task_id} is being processed"
                            )
                        }
                    )
                    status_code = status.HTTP_403_FORBIDDEN
                    break

            if not status_code == status.HTTP_403_FORBIDDEN:
                try:
                    csv_size = csv_file.size
                except AttributeError:
                    csv_size = csv_file.__sizeof__()
                csv_file.seek(0)

                if getattr(settings, "DISABLE_ASYNCHRONOUS_IMPORTS", False):
                    resp.update(submit_csv(request.user.username, xform, csv_file))
                    status_code = status.HTTP_200_OK
                else:
                    upload_to = os.path.join(
                        request.user.username, "csv_imports", csv_file.name
                    )
                    file_name = default_storage.save(upload_to, csv_file)
                    task = submit_csv_async.delay(
                        request.user.username, xform.pk, file_name, overwrite
                    )
                    if task is None:
                        raise ParseError("Task not found")
                    resp.update({"task_id": task.task_id})
                    status_code = status.HTTP_202_ACCEPTED

        return Response(data=resp, status=status_code, content_type="application/json")

    def retrieve(self, request, pk: int = None) -> Response:
        """Returns csv import async tasks that belong to this form"""
        xform = self.get_object(pk)

        return Response(
            data=self._get_active_tasks(xform),
            status=status.HTTP_200_OK,
            content_type="application/json",
        )

    def destroy(self, request, pk: int = None) -> Response:
        """
        Stops a queued/on-going import task

        Supported Query Parameters:

        - [Required] task_uuid: str = The unique task uuid for the form

        Possible Response status codes:

        - 204 No Content: Request was successfully processed. Task was terminated.
        - 400 Bad Request: Request was rejected either due to a missing `task_uuid` query parameter or because the `task_uuid` does not exist for the XForm
        """
        xform = self.get_object(pk)
        task_uuid = request.query_params.get("task_uuid")

        if not task_uuid:
            return Response(
                data={"error": "The task_uuid query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
                content_type="application/json",
            )

        successful = terminate_import_task(task_uuid, xform.pk)
        if not successful:
            return Response(
                data={"error": f"Queued task with ID {task_uuid} does not exist"},
                status=status.HTTP_400_BAD_REQUEST,
                content_type="application/json",
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
