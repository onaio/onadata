# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('viewer', '0002_export_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='export',
            name='created_on',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
