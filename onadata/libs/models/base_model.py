from django.db import models


class BaseModel(models.Model):

    class Meta:
        abstract = True
