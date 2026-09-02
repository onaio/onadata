import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


try:
    ONADATA_BASE_URL = settings.ONADATA_BASE_URL
except AttributeError:
    raise ImproperlyConfigured(
        "ONADATA_BASE_URL must be set in Django settings (e.g. 'https://api.ona.io')."
    )
ONADATA_API_TOKEN = getattr(settings, "ONADATA_API_TOKEN", None)


class OnadataError(Exception):
    """Base exception for Onadata client failures."""


class FormNotFoundError(OnadataError):
    def __init__(self, form_id):
        self.form_id = form_id
        super().__init__(f"Form '{form_id}' does not exist on Onadata.")


class OnadataAuthError(OnadataError):
    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__("Invalid or missing Onadata credentials.")


class OnadataUpstreamError(OnadataError):
    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__(f"Onadata API returned an unexpected status: {status_code}")


class OnadataClient:
    """
    Encapsulates connection setup and requests to the Onadata API.
    """

    def __init__(self, **kwargs):
        self.session = requests.Session()
        retries = Retry(
            total=2,
            backoff_factor=0.2,
            status_forcelist=[429, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.session.headers.update({"Accept": "application/json"})
        if ONADATA_API_TOKEN:
            self.session.headers.update({"Authorization": f"Token {ONADATA_API_TOKEN}"})

    def fetch_form_submissions(self, form_id: int) -> list | dict:
        url = f"{ONADATA_BASE_URL}/api/v1/data/{form_id}"
        response = self.session.get(url, timeout=(1.5, 3.0))

        if response.status_code == 404:
            raise FormNotFoundError(form_id)
        if response.status_code in (401, 403):
            raise OnadataAuthError(response.status_code)
        response.raise_for_status()

        if response.status_code != 200:
            raise OnadataUpstreamError(response.status_code)

        return response.json()


onadata_client = OnadataClient()