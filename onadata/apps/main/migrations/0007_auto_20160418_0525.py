# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-04-18 09:25
from __future__ import unicode_literals

from django.db import migrations
from onadata.apps.main.models.google_oath import CredentialsField


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0006_auto_20160408_0325'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tokenstoragemodel',
            name='token',
        ),
        migrations.AddField(
            model_name='tokenstoragemodel',
            name='credential',
            field=CredentialsField(null=True),
        ),
    ]
