from django.db import models


class BaseModel(models.Model):
    class Meta:
        abstract = True

    def reload(self):
        new_self = self.__class__.objects.get(pk=self.pk)
        # Clear and update the old dict.
        self.__dict__.clear()
        self.__dict__.update(new_self.__dict__)
