# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-04-08 07:25
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("logger", "0019_auto_20160307_0256"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dataview",
            name="columns",
            field=django.contrib.postgres.fields.jsonb.JSONField(),
        ),
        migrations.AlterField(
            model_name="dataview",
            name="query",
            field=django.contrib.postgres.fields.jsonb.JSONField(
                blank=True, default=dict
            ),
        ),
        migrations.AlterField(
            model_name="instance",
            name="json",
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict),
        ),
        migrations.AlterField(
            model_name="osmdata",
            name="tags",
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict),
        ),
        migrations.AlterField(
            model_name="project",
            name="metadata",
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True),
        ),
        migrations.AlterField(
            model_name="widget",
            name="metadata",
            field=django.contrib.postgres.fields.jsonb.JSONField(
                blank=True, default=dict
            ),
        ),
    ]
