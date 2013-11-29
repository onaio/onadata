from django.shortcuts import get_object_or_404
from odk_logger.models import Instance

from django import forms


class NoteForm(forms.Form):
    note = forms.CharField(min_length=1)
    instance_id = forms.IntegerField(widget=forms.HiddenInput())

    def save(self):
        data = self.cleaned_data
        instance = get_object_or_404(Instance, pk=data['instance_id'])
        instance.parsed_instance.add_note(data['note'])
        instance.parsed_instance.save()
        return data['instance_id']
