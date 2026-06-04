# -*- coding: utf-8 -*-
"""
forms module.
"""

import ipaddress
import os
import re
import socket

from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.validators import URLValidator
from django.forms import ModelForm
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

import requests
from registration.forms import RegistrationFormUniqueEmail
from requests.exceptions import RequestException
from rest_framework.exceptions import AuthenticationFailed
from six.moves.urllib.parse import urljoin, urlparse

# pylint: disable=ungrouped-imports
from onadata.apps.api.constants import USERNAME_VALIDATION_REGEX
from onadata.apps.logger.models import Project
from onadata.apps.main.models import UserProfile
from onadata.apps.viewer.models.data_dictionary import upload_to
from onadata.libs.utils.content_disposition import (
    ContentDispositionError,
    parse_filename,
)
from onadata.libs.utils.country_field import COUNTRIES
from onadata.libs.utils.logger_tools import publish_xls_form, publish_xml_form
from onadata.libs.utils.upload_validation import (
    XLSFORM_ALLOWED_EXTENSIONS,
    XLSFORM_UPLOAD_CONTEXT,
    UploadValidationError,
    get_upload_max_bytes,
    validate_uploaded_file,
)
from onadata.libs.utils.user_auth import get_user_default_project

FORM_LICENSES_CHOICES = (
    ("No License", gettext_lazy("No License")),
    (
        "https://creativecommons.org/licenses/by/3.0/",
        gettext_lazy("Attribution CC BY"),
    ),
    (
        "https://creativecommons.org/licenses/by-sa/3.0/",
        gettext_lazy("Attribution-ShareAlike CC BY-SA"),
    ),
)

DATA_LICENSES_CHOICES = (
    ("No License", gettext_lazy("No License")),
    ("http://opendatacommons.org/licenses/pddl/summary/", gettext_lazy("PDDL")),
    ("http://opendatacommons.org/licenses/by/summary/", gettext_lazy("ODC-BY")),
    ("http://opendatacommons.org/licenses/odbl/summary/", gettext_lazy("ODBL")),
)

PERM_CHOICES = (
    ("view", gettext_lazy("Can view")),
    ("edit", gettext_lazy("Can edit")),
    ("report", gettext_lazy("Can submit to")),
    ("remove", gettext_lazy("Remove permissions")),
)

VALID_FILE_EXTENSIONS = [f".{extension}" for extension in XLSFORM_ALLOWED_EXTENSIONS]

DEFAULT_REQUEST_TIMEOUT = getattr(settings, "DEFAULT_REQUEST_TIMEOUT", 30)

# pylint: disable=invalid-name
User = get_user_model()


def get_filename(response):
    """
    Get filename from a Content-Disposition header.
    """
    content_disposition = response.headers.get("Content-Disposition")
    if not content_disposition:
        return ""

    try:
        parsed = parse_filename(content_disposition)
    except ContentDispositionError:
        # A malformed upstream header carries no usable filename; fall back to
        # the caller's original name rather than raising.
        return ""

    filename = os.path.basename(parsed or "")
    name, extension = os.path.splitext(filename)

    if extension in VALID_FILE_EXTENSIONS and name:
        return filename

    return ""


def _validate_xlsform_upload(uploaded_file, allowed_extensions=None):
    """Validate XLSForm-family uploads and map errors to form errors.

    Returns the :class:`ValidatedUpload`. Does NOT mutate ``uploaded_file.name``
    because XLSForm publishing reads the original filename via pyxform to
    derive ``fallback_form_name`` (and, for forms without an explicit
    ``settings.id_string``, the form's ``id_string``). Storage-path
    randomisation for ``XForm.xls`` happens at the FileField ``upload_to``
    callable instead.
    """
    try:
        result = validate_uploaded_file(
            uploaded_file,
            allowed_extensions or XLSFORM_ALLOWED_EXTENSIONS,
            XLSFORM_UPLOAD_CONTEXT,
        )
    except UploadValidationError as error:
        raise forms.ValidationError(str(error)) from error

    uploaded_file.content_type = result.content_type

    return result


def _is_non_public_ip(ip_address):
    """Return True for addresses an XLSForm download must never reach."""
    return any(
        (
            ip_address.is_private,
            ip_address.is_loopback,
            ip_address.is_link_local,
            ip_address.is_reserved,
            ip_address.is_multicast,
            ip_address.is_unspecified,
        )
    )


def _assert_url_not_internal(url):
    """Reject XLSForm URLs that resolve to non-public addresses (SSRF guard).

    The host is resolved and every returned address is checked; the download is
    blocked if any maps to a private, loopback, link-local, reserved, multicast
    or unspecified address. Hosts listed in
    ``settings.XLSFORM_URL_ALLOWED_HOSTS`` bypass the check so deployments can
    permit trusted internal form hosts explicitly.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise forms.ValidationError(_("Only http and https URLs are allowed."))

    hostname = parsed.hostname
    if not hostname:
        raise forms.ValidationError(_("Could not determine the URL host."))

    allowed_hosts = getattr(settings, "XLSFORM_URL_ALLOWED_HOSTS", None) or []
    if hostname in allowed_hosts:
        return

    try:
        addrinfo = socket.getaddrinfo(hostname, None)
    except socket.gaierror as error:
        raise forms.ValidationError(
            _("Could not resolve URL host: %(host)s") % {"host": hostname}
        ) from error

    for info in addrinfo:
        if _is_non_public_ip(ipaddress.ip_address(info[4][0])):
            raise forms.ValidationError(
                _("Downloading XLSForms from this URL host is not permitted.")
            )


MAX_DOWNLOAD_REDIRECTS = 5


def _get_with_ssrf_guard(url):
    """GET ``url`` following redirects manually, validating every hop.

    Redirects are not auto-followed; instead each URL in the chain (the initial
    URL and every ``Location``) is checked with :func:`_assert_url_not_internal`
    before it is requested, so a public URL cannot redirect the download into an
    internal address. The chain is capped at :data:`MAX_DOWNLOAD_REDIRECTS`.
    """
    current_url = url
    for _hop in range(MAX_DOWNLOAD_REDIRECTS + 1):
        _assert_url_not_internal(current_url)
        try:
            response = requests.get(
                current_url,
                stream=True,
                timeout=DEFAULT_REQUEST_TIMEOUT,
                allow_redirects=False,
            )
        except RequestException as error:
            raise forms.ValidationError(
                _("Could not download XLSForm from URL: %(url)s") % {"url": url}
            ) from error

        if not response.is_redirect:
            return response

        location = response.headers.get("Location")
        response.close()
        if not location:
            raise forms.ValidationError(
                _("Could not download XLSForm from URL: %(url)s") % {"url": url}
            )
        current_url = urljoin(current_url, location)

    raise forms.ValidationError(_("Too many redirects while downloading the XLSForm."))


def _download_url_upload(cleaned_url, original_name):
    """Download a remote XLSForm body with SSRF guards and the byte cap."""
    response = _get_with_ssrf_guard(cleaned_url)

    if response.status_code >= 400:
        raise forms.ValidationError(
            _("Could not download XLSForm from URL: %(url)s") % {"url": cleaned_url}
        )

    _name, extension = os.path.splitext(original_name)
    if extension not in VALID_FILE_EXTENSIONS:
        original_name = get_filename(response) or original_name

    max_bytes = get_upload_max_bytes(XLSFORM_UPLOAD_CONTEXT)
    chunks = []
    total_size = 0
    try:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total_size += len(chunk)
            if total_size > max_bytes:
                raise forms.ValidationError(
                    _("File exceeds the maximum upload size of %(max_bytes)d bytes.")
                    % {"max_bytes": max_bytes}
                )
            chunks.append(chunk)
    except RequestException as error:
        raise forms.ValidationError(
            _("Could not download XLSForm from URL: %(url)s") % {"url": cleaned_url}
        ) from error

    downloaded_file = ContentFile(b"".join(chunks), name=original_name)
    downloaded_file.content_type = response.headers.get("Content-Type", "")
    return downloaded_file


class DataLicenseForm(forms.Form):
    """ "
    Data license form.
    """

    value = forms.ChoiceField(
        choices=DATA_LICENSES_CHOICES,
        widget=forms.Select(attrs={"disabled": "disabled", "id": "data-license"}),
    )


class FormLicenseForm(forms.Form):
    """
    Form license form.
    """

    value = forms.ChoiceField(
        choices=FORM_LICENSES_CHOICES,
        widget=forms.Select(attrs={"disabled": "disabled", "id": "form-license"}),
    )


class PermissionForm(forms.Form):
    """
    Permission assignment form.
    """

    for_user = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "id": "autocomplete",
                "data-provide": "typeahead",
                "autocomplete": "off",
            }
        )
    )
    perm_type = forms.ChoiceField(choices=PERM_CHOICES, widget=forms.Select())

    def __init__(self, username):
        self.username = username
        super().__init__()


class UserProfileForm(ModelForm):
    """
    User profile form base class.
    """

    class Meta:
        model = UserProfile
        # pylint: disable=modelform-uses-exclude
        exclude = ("user", "created_by", "num_of_submissions")

    email = forms.EmailField(widget=forms.TextInput())

    def clean_metadata(self):
        """
        Returns an empty dict if metadata is None.
        """
        metadata = self.cleaned_data.get("metadata")

        return metadata if metadata is not None else {}


class UserProfileFormRegister(forms.Form):
    """
    User profile registration form.
    """

    first_name = forms.CharField(
        widget=forms.TextInput(), required=True, max_length=255
    )
    last_name = forms.CharField(
        widget=forms.TextInput(), required=False, max_length=255
    )
    city = forms.CharField(widget=forms.TextInput(), required=False, max_length=255)
    country = forms.ChoiceField(
        widget=forms.Select(), required=False, choices=COUNTRIES, initial="ZZ"
    )
    organization = forms.CharField(
        widget=forms.TextInput(), required=False, max_length=255
    )
    home_page = forms.CharField(
        widget=forms.TextInput(), required=False, max_length=255
    )
    twitter = forms.CharField(widget=forms.TextInput(), required=False, max_length=255)

    def save_user_profile(self, new_user):
        """
        Creates and returns a new_user profile.
        """
        new_profile = UserProfile(
            user=new_user,
            name=self.cleaned_data["first_name"],
            city=self.cleaned_data["city"],
            country=self.cleaned_data["country"],
            organization=self.cleaned_data["organization"],
            home_page=self.cleaned_data["home_page"],
            twitter=self.cleaned_data["twitter"],
        )
        new_profile.save()
        return new_profile


# pylint: disable=too-many-ancestors
# order of inheritance control order of form display
class RegistrationFormUserProfile(RegistrationFormUniqueEmail, UserProfileFormRegister):
    """
    User profile registration form.
    """

    RESERVED_USERNAMES = settings.RESERVED_USERNAMES
    username = forms.CharField(widget=forms.TextInput(), max_length=30)
    email = forms.EmailField(widget=forms.TextInput())
    legal_usernames_re = re.compile(USERNAME_VALIDATION_REGEX)

    def clean_username(self):
        """
        Validate a new user username.
        """
        username = self.cleaned_data["username"].lower()

        if username in self.RESERVED_USERNAMES:
            raise forms.ValidationError(
                _("%(username)s is a reserved name, please choose another")
                % {"username": username}
            )
        # Use match() with the validation regex that includes ^ and $ anchors
        if not self.legal_usernames_re.match(username):
            raise forms.ValidationError(
                _(
                    "username may only contain alphanumeric characters, dots, hyphens, "
                    "underscores, emails, or phone numbers, and cannot end with "
                    ".json, .csv, .xls, .xlsx, or .kml"
                )
            )
        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            return username

        raise forms.ValidationError(_("%s already exists") % username)


class SourceForm(forms.Form):
    """
    Source document form.
    """

    source = forms.FileField(label=gettext_lazy("Source document"), required=True)


class SupportDocForm(forms.Form):
    """
    Supporting document.
    """

    doc = forms.FileField(label=gettext_lazy("Supporting document"), required=True)


class MediaForm(forms.Form):
    """
    Media file upload form.
    """

    media = forms.FileField(label=gettext_lazy("Media upload"), required=True)

    def clean_media(self):
        """
        Validate media upload file.
        """
        data_type = self.cleaned_data["media"].content_type
        if data_type not in ["image/jpeg", "image/png", "audio/mpeg"]:
            raise forms.ValidationError(
                "Only these media types are \
                                        allowed .png .jpg .mp3 .3gp .wav"
            )


class MapboxLayerForm(forms.Form):
    """
    Mapbox layers form.
    """

    map_name = forms.CharField(widget=forms.TextInput(), required=True, max_length=255)
    attribution = forms.CharField(
        widget=forms.TextInput(), required=False, max_length=255
    )
    link = forms.URLField(label=gettext_lazy("JSONP url"), required=True)


class QuickConverterFile(forms.Form):
    """
    Uploads XLSForm form.
    """

    xls_file = forms.FileField(label=gettext_lazy("XLS File"), required=False)


class QuickConverterURL(forms.Form):
    """
    Uploads XLSForm from a URL.
    """

    xls_url = forms.URLField(label=gettext_lazy("XLS URL"), required=False)


class QuickConverterDropboxURL(forms.Form):
    """
    Uploads XLSForm from Dropbox.
    """

    dropbox_xls_url = forms.URLField(label=gettext_lazy("XLS URL"), required=False)


class QuickConverterCsvFile(forms.Form):
    """
    Uploads CSV XLSForm.
    """

    csv_url = forms.URLField(label=gettext_lazy("CSV URL"), required=False)


class QuickConverterTextXlsForm(forms.Form):
    """
    Uploads Text XLSForm.
    """

    text_xls_form = forms.CharField(
        label=gettext_lazy("XLSForm Representation"), required=False
    )


class QuickConverterXmlFile(forms.Form):
    """
    Uploads an XForm XML.
    """

    xml_file = forms.FileField(label=gettext_lazy("XML File"), required=False)


class QuickConverterFloipFile(forms.Form):
    """
    Uploads a FLOIP results data package descriptor file.
    """

    floip_file = forms.FileField(
        label=gettext_lazy("FlOIP results data packages descriptor File"),
        required=False,
    )


# pylint: disable=too-many-ancestors
class QuickConverter(
    QuickConverterFile,
    QuickConverterURL,
    QuickConverterDropboxURL,
    QuickConverterTextXlsForm,
    QuickConverterCsvFile,
    QuickConverterXmlFile,
    QuickConverterFloipFile,
):
    """
    Publish XLSForm and convert to XForm.
    """

    project = forms.IntegerField(required=False)
    validate = URLValidator()

    def clean_project(self):
        """
        Project validation.
        """
        project = self.cleaned_data["project"]
        if project is not None:
            try:
                # pylint: disable=attribute-defined-outside-init,no-member
                self._project = Project.objects.get(pk=int(project))
            except (Project.DoesNotExist, ValueError) as e:
                raise forms.ValidationError(
                    _("Unknown project id: %(project)s") % {"project": project}
                ) from e

        return project

    # pylint: disable=too-many-locals
    def publish(self, user, id_string=None, created_by=None):
        """
        Publish XLSForm.
        """
        if self.is_valid():
            # If a text (csv) representation of the xlsform is present,
            # this will save the file and pass it instead of the 'xls_file'
            # field.
            cleaned_xls_file = None
            if (
                "text_xls_form" in self.cleaned_data
                and self.cleaned_data["text_xls_form"].strip()
            ):
                csv_data = self.cleaned_data["text_xls_form"]
                csv_file = ContentFile(csv_data.encode(), name="uploaded_form.csv")
                csv_file.content_type = "text/csv"
                validated_upload = _validate_xlsform_upload(
                    csv_file, allowed_extensions=("csv",)
                )
                cleaned_xls_file = default_storage.save(
                    upload_to(None, validated_upload.storage_basename, user.username),
                    csv_file,
                )
            if "xls_file" in self.cleaned_data and self.cleaned_data["xls_file"]:
                cleaned_xls_file = self.cleaned_data["xls_file"]
                _validate_xlsform_upload(
                    cleaned_xls_file, allowed_extensions=("csv", "xls", "xlsx")
                )
            if "floip_file" in self.cleaned_data and self.cleaned_data["floip_file"]:
                cleaned_xls_file = self.cleaned_data["floip_file"]
                _validate_xlsform_upload(cleaned_xls_file, allowed_extensions=("json",))

            cleaned_url = (
                self.cleaned_data["xls_url"].strip()
                or self.cleaned_data["dropbox_xls_url"]
                or self.cleaned_data["csv_url"]
            )

            if cleaned_url:
                self.validate(cleaned_url)
                parsed_url = urlparse(cleaned_url)
                cleaned_xls_file = os.path.basename(parsed_url.path)
                downloaded_file = _download_url_upload(cleaned_url, cleaned_xls_file)
                validated_upload = _validate_xlsform_upload(
                    downloaded_file, allowed_extensions=("csv", "xls", "xlsx")
                )
                cleaned_xls_file = upload_to(
                    None, validated_upload.storage_basename, user.username
                )
                cleaned_xls_file = default_storage.save(
                    cleaned_xls_file, downloaded_file
                )

            project = self.cleaned_data["project"]

            if project is None:
                project = get_user_default_project(user)
            else:
                project = self._project

            cleaned_xml_file = self.cleaned_data["xml_file"]
            if cleaned_xml_file:
                _validate_xlsform_upload(cleaned_xml_file, allowed_extensions=("xml",))
                return publish_xml_form(
                    cleaned_xml_file, user, project, id_string, created_by or user
                )

            if cleaned_xls_file is None:
                raise forms.ValidationError(
                    _(
                        "XLSForm not provided, expecting either of these"
                        " params: 'xml_file', 'xls_file', 'xls_url', 'csv_url',"
                        " 'dropbox_xls_url', 'text_xls_form', 'floip_file'"
                    )
                )
            # publish the xls
            return publish_xls_form(
                cleaned_xls_file, user, project, id_string, created_by or user
            )
        return None


class ActivateSMSSupportForm(forms.Form):
    """
    Enable SMS support form.
    """

    enable_sms_support = forms.TypedChoiceField(
        coerce=lambda x: x == "True",
        choices=((False, "No"), (True, "Yes")),
        widget=forms.Select,
        label=gettext_lazy("Enable SMS Support"),
    )
    sms_id_string = forms.CharField(
        max_length=50, required=True, label=gettext_lazy("SMS Keyword")
    )

    def clean_sms_id_string(self):
        """
        SMS id_string validation.
        """
        sms_id_string = self.cleaned_data.get("sms_id_string", "").strip()

        if not re.match(r"^[a-z0-9\_\-]+$", sms_id_string):
            raise forms.ValidationError(
                "id_string can only contain alphanum characters"
            )

        return sms_id_string


class ExternalExportForm(forms.Form):
    """
    XLS reports form.
    """

    template_name = forms.CharField(label="Template Name", max_length=20)
    template_token = forms.URLField(label="Template URL", max_length=100)


# Deprecated
ActivateSMSSupportFom = ActivateSMSSupportForm


class LoginLockoutAuthenticationForm(AuthenticationForm):
    """Authentication form that enforces the failed-login lockout.

    Mirrors the lockout enforced by the digest authentication flow
    (``onadata.libs.authentication``): blocks all logins while locked out,
    counts failed attempts and triggers a lockout (and lockout email) once
    ``MAX_LOGIN_ATTEMPTS`` is reached, keyed on IP + username.
    """

    def clean(self):
        # Avoid circular import
        from onadata.libs.authentication import (
            add_login_attempt,
            assert_not_locked_out,
            get_client_ip,
        )

        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        ip_address = get_client_ip(self.request)

        try:
            assert_not_locked_out(ip_address, username)
        except AuthenticationFailed as exc:
            raise self._lockout_error() from exc

        if username is not None and password:
            self.user_cache = authenticate(
                self.request, username=username, password=password
            )
            if self.user_cache is None:
                try:
                    add_login_attempt(ip_address, username)
                except AuthenticationFailed as exc:
                    raise self._lockout_error() from exc
                raise forms.ValidationError(
                    _("Invalid username or password"), code="invalid_login"
                )
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    @staticmethod
    def _lockout_error():
        return forms.ValidationError(
            _("Maximum login attempts exceeded. Please try again later."),
            code="locked_out",
        )
