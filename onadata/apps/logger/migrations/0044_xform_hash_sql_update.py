# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('logger', '0043_auto_20171010_0403'),
    ]

    operations = [
        migrations.RunSQL(
            "UPDATE logger_xform SET hash = CONCAT('md5:', MD5(XML)) WHERE hash IS NULL;",  # noqa
            migrations.RunSQL.noop
        ),
    ]
