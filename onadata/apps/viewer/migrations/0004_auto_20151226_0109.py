# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('viewer', '0003_auto_20151226_0100'),
    ]

    operations = [
        migrations.AlterField(
            model_name='export',
            name='internal_status',
            field=models.SmallIntegerField(default=0),
        ),
    ]
