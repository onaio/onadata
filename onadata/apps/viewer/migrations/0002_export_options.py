# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('viewer', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='export',
            name='options',
            field=jsonfield.fields.JSONField(default={}),
            preserve_default=True,
        ),
    ]
