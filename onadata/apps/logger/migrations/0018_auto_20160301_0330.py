# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('logger', '0017_auto_20160224_0130'),
    ]

    operations = [
        migrations.AddField(
            model_name='instancehistory',
            name='geom',
            field=django.contrib.gis.db.models.fields.GeometryCollectionField(
                srid=4326, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='instancehistory',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True),
            preserve_default=True,
        ),
    ]
