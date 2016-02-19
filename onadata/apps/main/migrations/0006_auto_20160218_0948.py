# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0005_projectmetadata_xformmetadata'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='metadata',
            unique_together=set([('object_id', 'data_type', 'data_value', 'content_type')]),
        ),
    ]
