"""Backfill validation_status for submissions decrypted before it was tracked."""

from django.db import migrations


# pylint: disable=unused-argument
def backfill_validation_status(apps, schema_editor):
    """Record already decrypted submissions as valid.

    Until valigetta 0.3.0 a submission whose content did not match its
    signature was rejected outright, so every submission that decrypted
    successfully had been checked against a signature it matched.

    Rows are walked in primary key order so that each batch starts where the
    previous one stopped. Filtering on validation_status alone would rescan
    every row already backfilled on each pass.
    """
    with schema_editor.connection.cursor() as cursor:
        last_id = 0
        backfilled_count = 0

        while True:
            cursor.execute(
                """
                UPDATE logger_instance SET validation_status = 'valid'
                WHERE id IN (
                    SELECT id FROM logger_instance
                    WHERE id > %s
                      AND decryption_status = 'success'
                      AND validation_status IS NULL
                    ORDER BY id
                    LIMIT 1000
                )
                RETURNING id
                """,
                [last_id],
            )
            ids = [row[0] for row in cursor.fetchall()]

            if not ids:
                break

            last_id = max(ids)
            backfilled_count += len(ids)

        print(f"Backfilled {backfilled_count} submissions")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("logger", "0046_instance_validation_status"),
    ]

    operations = [
        migrations.RunPython(
            backfill_validation_status,
            migrations.RunPython.noop,
        ),
    ]
