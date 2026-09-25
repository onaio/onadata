# -*- coding: utf-8 -*-
"""Normalize an autodetected MetaData index name.

Pre-existing drift between the models state and the migrations state:
any ``makemigrations`` run regenerates this rename until it lands.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0019_userdeactivationpermissionsnapshot"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="metadata",
            new_name="main_metada_object__3d1433_idx",
            old_name="main_metada_object__363d70_idx",
        ),
    ]
