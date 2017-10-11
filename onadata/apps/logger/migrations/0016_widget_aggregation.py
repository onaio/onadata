# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0015_auto_20160222_0559'),
    ]

    operations = [
        migrations.AddField(
            model_name='widget',
            name='aggregation',
            field=models.CharField(default=None, max_length=255, null=True,
                                   blank=True),
            preserve_default=True,
        ),
    ]
