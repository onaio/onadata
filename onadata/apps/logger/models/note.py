from django.db import models
from .instance import Instance

from django.contrib.auth.models import User


class Note(models.Model):
    note = models.TextField()
    instance = models.ForeignKey(Instance, related_name='notes')
    instance_field = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'logger'
        permissions = (
            ('view_note', 'View note'),
        )
