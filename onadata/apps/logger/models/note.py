from __future__ import absolute_import

from django.conf import settings
from django.db import models


class Note(models.Model):
    note = models.TextField()
    instance = models.ForeignKey(
        'logger.Instance', related_name='notes')
    instance_field = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'logger'
        permissions = (('view_note', 'View note'), )

    def get_data(self):
        owner = ""
        created_by_id = ""
        if self.created_by:
            owner = self.created_by.username
            created_by_id = self.created_by.id
        return {
            "id": self.id,
            "owner": owner,
            "note": self.note,
            "instance_field": self.instance_field,
            "created_by": created_by_id
        }
