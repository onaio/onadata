import os
import re
import urllib2
from urlparse import urlparse

from django import forms
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.validators import URLValidator
from django.forms import ModelForm
from django.utils.translation import ugettext as _, ugettext_lazy
from django.conf import settings
from recaptcha.client import captcha
from registration.forms import RegistrationFormUniqueEmail
from registration.models import RegistrationProfile

from onadata.apps.main.models import UserProfile
from onadata.apps.logger.models import Project
from onadata.apps.viewer.models.data_dictionary import upload_to
from onadata.libs.utils.country_field import COUNTRIES
from onadata.libs.utils.logger_tools import publish_xls_form
from onadata.libs.utils.user_auth import get_user_default_project

FORM_LICENSES_CHOICES = (
    ('No License', ugettext_lazy('No License')),
    ('https://creativecommons.org/licenses/by/3.0/',
     ugettext_lazy('Attribution CC BY')),
    ('https://creativecommons.org/licenses/by-sa/3.0/',
     ugettext_lazy('Attribution-ShareAlike CC BY-SA')),
)

DATA_LICENSES_CHOICES = (
    ('No License', ugettext_lazy('No License')),
    ('http://opendatacommons.org/licenses/pddl/summary/',
     ugettext_lazy('PDDL')),
    ('http://opendatacommons.org/licenses/by/summary/',
     ugettext_lazy('ODC-BY')),
    ('http://opendatacommons.org/licenses/odbl/summary/',
     ugettext_lazy('ODBL')),
)

PERM_CHOICES = (
    ('view', ugettext_lazy('Can view')),
    ('edit', ugettext_lazy('Can edit')),
    ('report', ugettext_lazy('Can submit to')),
    ('remove', ugettext_lazy('Remove permissions')),
)


class DataLicenseForm(forms.Form):
    value = forms.ChoiceField(choices=DATA_LICENSES_CHOICES,
                              widget=forms.Select(
                                  attrs={'disabled': 'disabled',
                                         'id': 'data-license'}))


class FormLicenseForm(forms.Form):
    value = forms.ChoiceField(choices=FORM_LICENSES_CHOICES,
                              widget=forms.Select(
                                  attrs={'disabled': 'disabled',
                                         'id': 'form-license'}))


class PermissionForm(forms.Form):
    for_user = forms.CharField(
        widget=forms.TextInput(
            attrs={
                'id': 'autocomplete',
                'data-provide': 'typeahead',
                'autocomplete': 'off'
            })
    )
    perm_type = forms.ChoiceField(choices=PERM_CHOICES, widget=forms.Select())

    def __init__(self, username):
        self.username = username
        super(PermissionForm, self).__init__()


class UserProfileForm(ModelForm):

    class Meta:
        model = UserProfile
        exclude = ('user', 'created_by', 'num_of_submissions')
    email = forms.EmailField(widget=forms.TextInput())


class UserProfileFormRegister(forms.Form):

    REGISTRATION_REQUIRE_CAPTCHA = settings.REGISTRATION_REQUIRE_CAPTCHA
    RECAPTCHA_PUBLIC_KEY = settings.RECAPTCHA_PUBLIC_KEY
    RECAPTCHA_HTML = captcha.displayhtml(settings.RECAPTCHA_PUBLIC_KEY,
                                         use_ssl=settings.RECAPTCHA_USE_SSL)

    first_name = forms.CharField(widget=forms.TextInput(), required=True,
                                 max_length=255)
    last_name = forms.CharField(widget=forms.TextInput(), required=False,
                                max_length=255)
    city = forms.CharField(widget=forms.TextInput(), required=False,
                           max_length=255)
    country = forms.ChoiceField(widget=forms.Select(), required=False,
                                choices=COUNTRIES, initial='ZZ')
    organization = forms.CharField(widget=forms.TextInput(), required=False,
                                   max_length=255)
    home_page = forms.CharField(widget=forms.TextInput(), required=False,
                                max_length=255)
    twitter = forms.CharField(widget=forms.TextInput(), required=False,
                              max_length=255)

    recaptcha_challenge_field = forms.CharField(required=False, max_length=512)
    recaptcha_response_field = forms.CharField(
        max_length=100, required=settings.REGISTRATION_REQUIRE_CAPTCHA)

    def save(self, new_user):
        new_profile = \
            UserProfile(user=new_user, name=self.cleaned_data['first_name'],
                        city=self.cleaned_data['city'],
                        country=self.cleaned_data['country'],
                        organization=self.cleaned_data['organization'],
                        home_page=self.cleaned_data['home_page'],
                        twitter=self.cleaned_data['twitter'])
        new_profile.save()
        return new_profile


# order of inheritance control order of form display
class RegistrationFormUserProfile(RegistrationFormUniqueEmail,
                                  UserProfileFormRegister):
    class Meta:
        pass
    _reserved_usernames = settings.RESERVED_USERNAMES
    username = forms.CharField(widget=forms.TextInput(), max_length=30)
    email = forms.EmailField(widget=forms.TextInput())
    legal_usernames_re = re.compile("^\w+$")

    def clean(self):
        cleaned_data = super(UserProfileFormRegister, self).clean()

        # don't check captcha if it's disabled
        if not self.REGISTRATION_REQUIRE_CAPTCHA:
            if 'recaptcha_response_field' in self._errors:
                del self._errors['recaptcha_response_field']
            return cleaned_data

        response = captcha.submit(
            cleaned_data.get('recaptcha_challenge_field'),
            cleaned_data.get('recaptcha_response_field'),
            settings.RECAPTCHA_PRIVATE_KEY,
            None)

        if not response.is_valid:
            raise forms.ValidationError(_(u"The Captcha is invalid. "
                                          u"Please, try again."))
        return cleaned_data

    def clean_username(self):
        username = self.cleaned_data['username'].lower()
        if username in self._reserved_usernames:
            raise forms.ValidationError(
                _(u'%s is a reserved name, please choose another') % username)
        elif not self.legal_usernames_re.search(username):
            raise forms.ValidationError(
                _(u'username may only contain alpha-numeric characters and '
                  u'underscores'))
        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            return username
        raise forms.ValidationError(_(u'%s already exists') % username)

    def save(self, profile_callback=None):
        new_user = RegistrationProfile.objects.create_inactive_user(
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password1'],
            email=self.cleaned_data['email'])
        UserProfileFormRegister.save(self, new_user)
        return new_user


class SourceForm(forms.Form):
    source = forms.FileField(label=ugettext_lazy(u"Source document"),
                             required=True)


class SupportDocForm(forms.Form):
    doc = forms.FileField(label=ugettext_lazy(u"Supporting document"),
                          required=True)


class MediaForm(forms.Form):
    media = forms.FileField(label=ugettext_lazy(u"Media upload"),
                            required=True)

    def clean_media(self):
        data_type = self.cleaned_data['media'].content_type
        if data_type not in ['image/jpeg', 'image/png', 'audio/mpeg']:
            raise forms.ValidationError('Only these media types are \
                                        allowed .png .jpg .mp3 .3gp .wav')


class MapboxLayerForm(forms.Form):
    map_name = forms.CharField(widget=forms.TextInput(), required=True,
                               max_length=255)
    attribution = forms.CharField(widget=forms.TextInput(), required=False,
                                  max_length=255)
    link = forms.URLField(label=ugettext_lazy(u'JSONP url'),
                          required=True)


class QuickConverterFile(forms.Form):
    xls_file = forms.FileField(
        label=ugettext_lazy(u'XLS File'), required=False)


class QuickConverterURL(forms.Form):
    xls_url = forms.URLField(label=ugettext_lazy('XLS URL'),
                             required=False)


class QuickConverterDropboxURL(forms.Form):
    dropbox_xls_url = forms.URLField(
        label=ugettext_lazy('XLS URL'), required=False)


class QuickConverterCsvFile(forms.Form):
    csv_url = forms.URLField(
        label=ugettext_lazy('CSV URL'), required=False)


class QuickConverterTextXlsForm(forms.Form):
    text_xls_form = forms.CharField(
        label=ugettext_lazy('XLSForm Representation'), required=False)


class QuickConverter(QuickConverterFile, QuickConverterURL,
                     QuickConverterDropboxURL, QuickConverterTextXlsForm,
                     QuickConverterCsvFile):
    project = forms.IntegerField(required=False)
    validate = URLValidator()

    def clean_project(self):
        project = self.cleaned_data['project']
        if project is not None:
            try:
                self._project = Project.objects.get(pk=int(project))
            except (Project.DoesNotExist, ValueError):
                raise forms.ValidationError(
                    _(u"Unknown project id: %s" % project))

        return project

    def publish(self, user, id_string=None, created_by=None):
        if self.is_valid():
            # If a text (csv) representation of the xlsform is present,
            # this will save the file and pass it instead of the 'xls_file'
            # field.
            if 'text_xls_form' in self.cleaned_data\
               and self.cleaned_data['text_xls_form'].strip():
                csv_data = self.cleaned_data['text_xls_form']

                # assigning the filename to a random string (quick fix)
                import random
                rand_name = "uploaded_form_%s.csv" % ''.join(
                    random.sample("abcdefghijklmnopqrstuvwxyz0123456789", 6))

                cleaned_xls_file = \
                    default_storage.save(
                        upload_to(None, rand_name, user.username),
                        ContentFile(csv_data))
            else:
                cleaned_xls_file = self.cleaned_data['xls_file']

            if not cleaned_xls_file:
                cleaned_url = (
                    self.cleaned_data['xls_url'].strip() or
                    self.cleaned_data['dropbox_xls_url'] or
                    self.cleaned_data['csv_url'])

                cleaned_xls_file = urlparse(cleaned_url)
                cleaned_xls_file = \
                    '_'.join(cleaned_xls_file.path.split('/')[-2:])
                name, extension = os.path.splitext(cleaned_xls_file)
                if extension not in ['.xls', '.xlsx', '.csv']:
                    cleaned_xls_file += '.xls'
                cleaned_xls_file = \
                    upload_to(None, cleaned_xls_file, user.username)
                self.validate(cleaned_url)
                xls_data = ContentFile(urllib2.urlopen(cleaned_url).read())
                cleaned_xls_file = \
                    default_storage.save(cleaned_xls_file, xls_data)

            project = self.cleaned_data['project']

            if project is None:
                project = get_user_default_project(user)
            else:
                project = self._project

            # publish the xls
            return publish_xls_form(cleaned_xls_file, user, project,
                                    id_string, created_by or user)


class ActivateSMSSupportFom(forms.Form):

    enable_sms_support = forms.TypedChoiceField(coerce=lambda x: x == 'True',
                                                choices=((False, 'No'),
                                                         (True, 'Yes')),
                                                widget=forms.Select,
                                                label=ugettext_lazy(
                                                    u"Enable SMS Support"))
    sms_id_string = forms.CharField(max_length=50, required=True,
                                    label=ugettext_lazy(u"SMS Keyword"))

    def clean_sms_id_string(self):
        sms_id_string = self.cleaned_data.get('sms_id_string', '').strip()

        if not re.match(r'^[a-z0-9\_\-]+$', sms_id_string):
            raise forms.ValidationError(u"id_string can only contain alphanum"
                                        u" characters")

        return sms_id_string


class ExternalExportForm(forms.Form):
    template_name = forms.CharField(label='Template Name', max_length=20)
    template_token = forms.URLField(label='Template URL', max_length=100)
