# -*- coding: utf-8 -*-
"""
forms module.
"""
import os
import random
import re

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.validators import URLValidator
from django.forms import ModelForm
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

import requests
from registration.forms import RegistrationFormUniqueEmail
from six.moves.urllib.parse import urlparse

# pylint: disable=ungrouped-imports
from onadata.apps.logger.models import Project
from onadata.apps.main.models import UserProfile
from onadata.apps.viewer.models.data_dictionary import upload_to
from onadata.libs.utils.country_field import COUNTRIES
from onadata.libs.utils.logger_tools import publish_xls_form, publish_xml_form
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

VALID_XLSFORM_CONTENT_TYPES = [
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
    "application/vnd.ms-excel",
]

VALID_FILE_EXTENSIONS = [".xlsx", ".csv"]

DEFAULT_REQUEST_TIMEOUT = getattr(settings, "DEFAULT_REQUEST_TIMEOUT", 30)

# pylint: disable=invalid-name
User = get_user_model()


def get_filename(response):
    """
    Get filename from a Content-Desposition header.
    """
    # pylint: disable=line-too-long
    # the value of 'content-disposition' contains the filename and has the
    # following format:
    # 'attachment; filename="ActApp_Survey_System.xlsx"; filename*=UTF-8\'\'ActApp_Survey_System.xlsx' # noqa
    cleaned_xls_file = ""
    content = response.headers.get("Content-Disposition").split("; ")
    counter = [a for a in content if a.startswith("filename=")]
    if counter:
        filename_key_val = counter[0]
        filename = filename_key_val.split("=")[1].replace('"', "")
        name, extension = os.path.splitext(filename)

        if extension in VALID_FILE_EXTENSIONS and name:
            cleaned_xls_file = filename

    return cleaned_xls_file


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
    legal_usernames_re = re.compile(r"^\w+$")

    def clean_username(self):
        """
        Validate a new user username.
        """
        username = self.cleaned_data["username"].lower()

        if username in self.RESERVED_USERNAMES:
            raise forms.ValidationError(
                _(f"{username} is a reserved name, please choose another")
            )
        if not self.legal_usernames_re.search(username):
            raise forms.ValidationError(
                _("username may only contain alpha-numeric characters and underscores")
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
                raise forms.ValidationError(_(f"Unknown project id: {project}")) from e

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

                # assigning the filename to a random string (quick fix)

                random_string = "".join(
                    random.sample("abcdefghijklmnopqrstuvwxyz0123456789", 6)
                )
                rand_name = f"uploaded_form_{random_string}.csv"

                cleaned_xls_file = default_storage.save(
                    upload_to(None, rand_name, user.username),
                    ContentFile(csv_data.encode()),
                )
            if "xls_file" in self.cleaned_data and self.cleaned_data["xls_file"]:
                cleaned_xls_file = self.cleaned_data["xls_file"]
            if "floip_file" in self.cleaned_data and self.cleaned_data["floip_file"]:
                cleaned_xls_file = self.cleaned_data["floip_file"]

            cleaned_url = (
                self.cleaned_data["xls_url"].strip()
                or self.cleaned_data["dropbox_xls_url"]
                or self.cleaned_data["csv_url"]
            )

            if cleaned_url:
                self.validate(cleaned_url)
                cleaned_xls_file = urlparse(cleaned_url)
                cleaned_xls_file = "_".join(cleaned_xls_file.path.split("/")[-2:])
                name, extension = os.path.splitext(cleaned_xls_file)

                if extension not in VALID_FILE_EXTENSIONS and name:
                    response = requests.head(
                        cleaned_url,
                        allow_redirects=True,
                        timeout=DEFAULT_REQUEST_TIMEOUT,
                    )
                    if (
                        response.headers.get("content-type")
                        in VALID_XLSFORM_CONTENT_TYPES
                        and response.status_code < 400
                    ):
                        cleaned_xls_file = get_filename(response)

                cleaned_xls_file = upload_to(None, cleaned_xls_file, user.username)
                response = requests.get(cleaned_url, timeout=DEFAULT_REQUEST_TIMEOUT)
                if response.status_code < 400:
                    xls_data = ContentFile(response.content)
                    cleaned_xls_file = default_storage.save(cleaned_xls_file, xls_data)

            project = self.cleaned_data["project"]

            if project is None:
                project = get_user_default_project(user)
            else:
                project = self._project

            cleaned_xml_file = self.cleaned_data["xml_file"]
            if cleaned_xml_file:
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
