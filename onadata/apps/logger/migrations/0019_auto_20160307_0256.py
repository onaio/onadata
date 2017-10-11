# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0018_auto_20160301_0330'),
    ]

    operations = [
        migrations.AddField(
            model_name='widget',
            name='metadata',
            field=jsonfield.fields.JSONField(default={}, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='instance',
            name='uuid',
            field=models.CharField(default='', max_length=249),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='instance',
            name='xform',
            field=models.ForeignKey(related_name='instances',
                                    to='logger.XForm', null=True),
            preserve_default=True,
        ),
    ]
