# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0014_note_instance_field'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='widget',
            options={'ordering': ('order',)},
        ),
        migrations.AddField(
            model_name='widget',
            name='order',
            field=models.PositiveIntegerField(default=0, editable=False,
                                              db_index=True),
            preserve_default=False,
        ),
    ]
