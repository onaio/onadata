# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0019_auto_20160307_0256'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='last_edited',
            field=models.DateTimeField(default=None, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='instancehistory',
            name='submission_date',
            field=models.DateTimeField(default=None, null=True),
            preserve_default=True,
        ),
    ]
