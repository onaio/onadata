# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0011_dataview_matches_parent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attachment',
            name='mimetype',
            field=models.CharField(default=b'', max_length=100, blank=True),
            preserve_default=True,
        ),
    ]
