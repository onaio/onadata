# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-08-30 05:28
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logger", "0053_submissionreview"),
    ]

    operations = [
        migrations.AddField(
            model_name="instance",
            name="has_a_review",
            field=models.BooleanField(default=False, verbose_name="has_a_review"),
        ),
    ]
