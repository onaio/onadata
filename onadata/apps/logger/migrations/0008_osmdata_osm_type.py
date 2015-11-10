# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0007_osmdata_field_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='osmdata',
            name='osm_type',
            field=models.CharField(default=b'way', max_length=10),
            preserve_default=True,
        ),
    ]
