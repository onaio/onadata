# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0013_note_created_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='note',
            name='instance_field',
            field=models.TextField(null=True, blank=True),
            preserve_default=True,
        ),
    ]
