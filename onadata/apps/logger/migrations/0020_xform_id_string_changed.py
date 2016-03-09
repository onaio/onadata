# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0019_auto_20160307_0256'),
    ]

    operations = [
        migrations.AddField(
            model_name='xform',
            name='id_string_changed',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
