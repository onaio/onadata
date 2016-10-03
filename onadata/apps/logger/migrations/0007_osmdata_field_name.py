# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0006_auto_20151106_0130'),
    ]

    operations = [
        migrations.AddField(
            model_name='osmdata',
            name='field_name',
            field=models.CharField(default=b'', max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
