from django.db import models


class ColumnRename(models.Model):
    xpath = models.CharField(max_length=255, unique=True)
    column_name = models.CharField(max_length=32)

    class Meta:
        app_label = "viewer"

    @classmethod
    def get_dict(cls):
        return dict([(cr.xpath, cr.column_name) for cr in cls.objects.all()])
