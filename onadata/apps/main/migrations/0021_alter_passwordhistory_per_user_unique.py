# -*- coding: utf-8 -*-
"""Make PasswordHistory uniqueness per-user instead of global."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0020_pendingemailchange_and_more"),
    ]

    operations = [
        # Drop the global UNIQUE on hashed_password (keep it indexed) ...
        migrations.AlterField(
            model_name="passwordhistory",
            name="hashed_password",
            field=models.CharField(db_index=True, max_length=128),
        ),
        # ... and re-scope uniqueness to (user, hashed_password).
        migrations.AlterUniqueTogether(
            name="passwordhistory",
            unique_together={("user", "hashed_password")},
        ),
    ]
