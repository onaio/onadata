from django.db import models

from .xform import XForm


class MergedXForm(XForm):
    xforms = models.ManyToManyField(XForm, related_name='mergedxform_ptr')

    class Meta:
        app_label = 'logger'
