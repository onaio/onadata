from django import forms


class NoteForm(forms.Form):
    note = forms.CharField(min_length=1)

    def save(self, parsed_instance):
        parsed_instance.add_note(self.cleaned_data['note'])
        parsed_instance.save()
