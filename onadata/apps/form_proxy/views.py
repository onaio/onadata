import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from requests.exceptions import Timeout, RequestException
from .services import onadata_client, FormNotFoundError, OnadataAuthError, OnadataUpstreamError


logger = logging.getLogger(__name__)


class FormSubmissionsView(APIView):
    """Fetches and returns Onadata form submissions as JSON."""

    def get(self, request, form_id:str):
        try:
            data = onadata_client.fetch_form_submissions(form_id)
            return Response(data, status=status.HTTP_200_OK)

        except FormNotFoundError as err:
            return Response({"error": "Form Not Found", "detail": str(err)}, status=status.HTTP_404_NOT_FOUND)

        except OnadataAuthError as err:
            return Response({"error": "Authentication Failed", "detail": str(err)}, status=err.status_code)

        except OnadataUpstreamError as err:
            logger.error("Upstream error %s for form %s", err.status_code, form_id)
            return Response({"error": "Bad Gateway", "detail": str(err)}, status=status.HTTP_502_BAD_GATEWAY)

        except Timeout:
            logger.warning("Timeout fetching form %s", form_id)
            return Response({"error": "Gateway Timeout"}, status=status.HTTP_504_GATEWAY_TIMEOUT)

        except RequestException as err:
            logger.exception("Network error for form %s: %s", form_id, err)
            return Response({"error": "Service Unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)