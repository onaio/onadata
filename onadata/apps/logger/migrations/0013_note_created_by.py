# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('logger', '0012_auto_20160114_0708'),
    ]

    operations = [
        migrations.AddField(
            model_name='note',
            name='created_by',
            field=models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL,
                                    null=True),
            preserve_default=True,
        ),
    ]
