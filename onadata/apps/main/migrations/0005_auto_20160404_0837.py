# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0004_auto_20160215_0345'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tokenstoragemodel',
            name='id',
            field=models.OneToOneField(
                related_name='google_id', primary_key=True, serialize=False,
                to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='date_modified',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
