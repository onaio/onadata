from __future__ import absolute_import

from django.contrib.auth.models import User
from django.db import models

from .instance import Instance


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

    def get_data(self):
        owner = ""
        created_by_id = ""
        if self.created_by:
            owner = self.created_by.username
            created_by_id = self.created_by.id
        return {"id": self.id,
                "owner": owner,
                "note": self.note,
                "instance_field": self.instance_field,
                "created_by": created_by_id
                }
