# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import onadata.apps.main.models.meta_data


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
        ('main', '0003_auto_20151015_0822'),
    ]

    operations = [
        migrations.AlterField(
            model_name='metadata',
            name='xform',
            field=models.PositiveIntegerField(null=True, blank=True),
            preserve_default=True,
        ),
        migrations.RenameField(
            model_name='metadata',
            old_name='xform',
            new_name='object_id'
        ),
        migrations.AddField(
            model_name='metadata',
            name='content_type',
            field=models.ForeignKey(
                default=onadata.apps.main.models.meta_data.get_default_content_type,  # noqa
                to='contenttypes.ContentType'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='metadata',
            unique_together=set(
                [('object_id', 'data_type', 'data_value', 'content_type')]),
        ),
    ]
