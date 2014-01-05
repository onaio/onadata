from django import forms
from django.utils.translation import ugettext_lazy

from apps.odk_viewer.models.data_dictionary import DataDictionary


class QuickConverter(forms.Form):
    xls_file = forms.FileField(label=ugettext_lazy("XLS File"))

    def publish(self, user):
        if self.is_valid():
            return DataDictionary.objects.create(
                user=user,
                xls=self.cleaned_data['xls_file'])
