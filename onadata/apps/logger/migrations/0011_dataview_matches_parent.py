# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0010_attachment_file_size'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataview',
            name='matches_parent',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
