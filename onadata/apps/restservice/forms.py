from django import forms
from django.utils.translation import gettext_lazy

from onadata.apps.restservice import SERVICE_CHOICES


class RestServiceForm(forms.Form):
    service_name = \
        forms.CharField(max_length=50, label=gettext_lazy(u"Service Name"),
                        widget=forms.Select(choices=SERVICE_CHOICES))
    service_url = forms.URLField(label=gettext_lazy(u"Service URL"))
