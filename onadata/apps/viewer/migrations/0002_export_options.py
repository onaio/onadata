# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ("viewer", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="export",
            name="options",
            field=models.JSONField(default={}),
            preserve_default=True,
        ),
    ]
