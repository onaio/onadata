# -*- coding: utf-8 -*-
"""Normalize an autodetected MetaData index name.

Unrelated to the email-change feature — split out of
0020_pendingemailchange_and_more so that feature migration only creates the
PendingEmailChange model.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0021_alter_passwordhistory_per_user_unique"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="metadata",
            new_name="main_metada_object__3d1433_idx",
            old_name="main_metada_object__363d70_idx",
        ),
    ]
