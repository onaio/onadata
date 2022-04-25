# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0009_auto_20151111_0438'),
    ]

    operations = [
        migrations.AddField(
            model_name='attachment',
            name='file_size',
            field=models.PositiveIntegerField(default=0),
            preserve_default=True,
        ),
    ]
