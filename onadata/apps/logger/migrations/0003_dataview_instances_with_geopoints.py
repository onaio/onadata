# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0002_auto_20150717_0048'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataview',
            name='instances_with_geopoints',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
