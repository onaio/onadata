# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0008_osmdata_osm_type'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='osmdata',
            unique_together=set([('instance', 'field_name')]),
        ),
    ]
