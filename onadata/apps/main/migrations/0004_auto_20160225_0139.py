# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import oauth2client.contrib.django_orm


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0003_auto_20151015_0822'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tokenstoragemodel',
            name='token',
        ),
        migrations.AddField(
            model_name='tokenstoragemodel',
            name='credential',
            field=oauth2client.contrib.django_orm.CredentialsField(null=True),
            preserve_default=True,
        ),
    ]
