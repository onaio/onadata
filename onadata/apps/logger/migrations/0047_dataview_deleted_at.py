# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-03-26 12:58
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logger", "0046_auto_20180314_1618"),
    ]

    operations = [
        migrations.AddField(
            model_name="dataview",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
