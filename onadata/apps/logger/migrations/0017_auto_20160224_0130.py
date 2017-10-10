# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0016_widget_aggregation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='instance',
            name='uuid',
            field=models.CharField(max_length=249),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='instance',
            name='xform',
            field=models.ForeignKey(related_name='instances', default=-1,
                                    to='logger.XForm'),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name='instance',
            unique_together=set([('xform', 'uuid')]),
        ),
    ]
