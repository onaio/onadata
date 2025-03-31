# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-08-18 12:43
from __future__ import unicode_literals

import datetime
from datetime import timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("logger", "0024_xform_has_hxl_support"),
    ]

    operations = [
        migrations.AddField(
            model_name="xform",
            name="last_updated_at",
            field=models.DateTimeField(
                auto_now=True,
                default=datetime.datetime(
                    2016, 8, 18, 12, 43, 30, 316792, tzinfo=timezone.utc
                ),
            ),
            preserve_default=False,
        ),
    ]
