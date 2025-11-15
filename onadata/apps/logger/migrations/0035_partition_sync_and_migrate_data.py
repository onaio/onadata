"""
Migration to sync data from logger_instance to partitioned table.
This is step 2 of 4 in the partitioning process.
"""

import logging
from datetime import datetime

from django.conf import settings
from django.db import migrations

logger = logging.getLogger(__name__)


def create_sync_mechanism(apps, schema_editor):
    """
    Create triggers to keep the partitioned table in sync with the original
    during the migration process.
    """

    if not getattr(settings, "ENABLE_TABLE_PARTITIONING", True):
        logger.info("Table partitioning is disabled. Skipping.")
        return

    with schema_editor.connection.cursor() as cursor:
        # Check if partitioned table exists
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename = 'logger_instance_partitioned'
            )
        """
        )
        if not cursor.fetchone()[0]:
            logger.info("Partitioned table doesn't exist. Skipping sync setup.")
            return

        logger.info("Creating sync trigger function...")

        # Create sync function
        cursor.execute(
            """
            CREATE OR REPLACE FUNCTION sync_instance_to_partition()
            RETURNS TRIGGER AS $$
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    -- Insert into partitioned table
                    INSERT INTO logger_instance_partitioned (
                        id, xml, user_id, xform_id, survey_type_id, date_created,
                        date_modified, status, uuid, deleted_at, json, geom, version,
                        last_edited, media_all_received, media_count, total_media,
                        checksum, deleted_by_id, has_a_review, is_encrypted, decryption_status
                    )
                    VALUES (
                        NEW.id, NEW.xml, NEW.user_id, NEW.xform_id, NEW.survey_type_id,
                        NEW.date_created, NEW.date_modified, NEW.status, NEW.uuid,
                        NEW.deleted_at, NEW.json, NEW.geom, NEW.version, NEW.last_edited,
                        NEW.media_all_received, NEW.media_count, NEW.total_media,
                        NEW.checksum, NEW.deleted_by_id, NEW.has_a_review, NEW.is_encrypted,
                        NEW.decryption_status
                    )
                    ON CONFLICT (id, xform_id) DO UPDATE SET
                        xml = EXCLUDED.xml,
                        user_id = EXCLUDED.user_id,
                        survey_type_id = EXCLUDED.survey_type_id,
                        date_created = EXCLUDED.date_created,
                        date_modified = EXCLUDED.date_modified,
                        status = EXCLUDED.status,
                        uuid = EXCLUDED.uuid,
                        deleted_at = EXCLUDED.deleted_at,
                        json = EXCLUDED.json,
                        geom = EXCLUDED.geom,
                        version = EXCLUDED.version,
                        last_edited = EXCLUDED.last_edited,
                        media_all_received = EXCLUDED.media_all_received,
                        media_count = EXCLUDED.media_count,
                        total_media = EXCLUDED.total_media,
                        checksum = EXCLUDED.checksum,
                        deleted_by_id = EXCLUDED.deleted_by_id,
                        has_a_review = EXCLUDED.has_a_review,
                        is_encrypted = EXCLUDED.is_encrypted,
                        decryption_status = EXCLUDED.decryption_status;
                    RETURN NEW;

                ELSIF TG_OP = 'UPDATE' THEN
                    -- Check if partition key (xform_id) changed
                    IF OLD.xform_id != NEW.xform_id THEN
                        -- Partition key changed: need to move row to different partition
                        -- Delete from old partition and insert into new partition
                        DELETE FROM logger_instance_partitioned WHERE id = OLD.id;
                        INSERT INTO logger_instance_partitioned (
                            id, xml, user_id, xform_id, survey_type_id, date_created,
                            date_modified, status, uuid, deleted_at, json, geom, version,
                            last_edited, media_all_received, media_count, total_media,
                            checksum, deleted_by_id, has_a_review, is_encrypted, decryption_status
                        )
                        VALUES (
                            NEW.id, NEW.xml, NEW.user_id, NEW.xform_id, NEW.survey_type_id,
                            NEW.date_created, NEW.date_modified, NEW.status, NEW.uuid,
                            NEW.deleted_at, NEW.json, NEW.geom, NEW.version, NEW.last_edited,
                            NEW.media_all_received, NEW.media_count, NEW.total_media,
                            NEW.checksum, NEW.deleted_by_id, NEW.has_a_review, NEW.is_encrypted,
                            NEW.decryption_status
                        );
                    ELSE
                        -- Normal update: partition key unchanged
                        UPDATE logger_instance_partitioned SET
                            xml = NEW.xml,
                            user_id = NEW.user_id,
                            survey_type_id = NEW.survey_type_id,
                            date_created = NEW.date_created,
                            date_modified = NEW.date_modified,
                            status = NEW.status,
                            uuid = NEW.uuid,
                            deleted_at = NEW.deleted_at,
                            json = NEW.json,
                            geom = NEW.geom,
                            version = NEW.version,
                            last_edited = NEW.last_edited,
                            media_all_received = NEW.media_all_received,
                            media_count = NEW.media_count,
                            total_media = NEW.total_media,
                            checksum = NEW.checksum,
                            deleted_by_id = NEW.deleted_by_id,
                            has_a_review = NEW.has_a_review,
                            is_encrypted = NEW.is_encrypted,
                            decryption_status = NEW.decryption_status
                        WHERE id = NEW.id;
                    END IF;
                    RETURN NEW;

                ELSIF TG_OP = 'DELETE' THEN
                    -- Delete from partitioned table
                    DELETE FROM logger_instance_partitioned
                    WHERE id = OLD.id;
                    RETURN OLD;
                END IF;
            END;
            $$ LANGUAGE plpgsql;
        """
        )

        # Create trigger
        cursor.execute(
            """
            DROP TRIGGER IF EXISTS sync_instance_trigger ON logger_instance;
            CREATE TRIGGER sync_instance_trigger
            AFTER INSERT OR UPDATE OR DELETE ON logger_instance
            FOR EACH ROW
            EXECUTE FUNCTION sync_instance_to_partition();
        """
        )

        logger.info("Sync trigger created successfully")


def migrate_existing_data(apps, schema_editor):
    """
    Migrate existing data from logger_instance to the partitioned table.
    This is done in batches to avoid locking the table for too long.
    """

    if not getattr(settings, "ENABLE_TABLE_PARTITIONING", True):
        return

    batch_size = getattr(settings, "PARTITION_MIGRATION_BATCH_SIZE", 10000)
    max_batches = getattr(
        settings, "PARTITION_MIGRATION_MAX_BATCHES", None
    )  # None = no limit

    logger.info(f"Starting data migration with batch size {batch_size}")

    with schema_editor.connection.cursor() as cursor:
        # Check if partitioned table exists
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename = 'logger_instance_partitioned'
            )
        """
        )
        if not cursor.fetchone()[0]:
            logger.info("Partitioned table doesn't exist. Skipping data migration.")
            return

        # Get total count and ID range
        cursor.execute(
            """
            SELECT
                COUNT(*) as total_count,
                MIN(id) as min_id,
                MAX(id) as max_id
            FROM logger_instance
        """
        )
        total_count, min_id, max_id = cursor.fetchone()

        if not min_id:
            logger.info("No data to migrate")
            return

        logger.info(
            f"Total to migrate: {total_count:,} (ID range: {min_id} to {max_id})"
        )

        # Check how many records are already migrated
        cursor.execute("SELECT COUNT(*) FROM logger_instance_partitioned")
        already_migrated = cursor.fetchone()[0]

        if already_migrated >= total_count:
            logger.info(f"All {total_count:,} records already migrated")
            return

        logger.info(f"Already migrated: {already_migrated:,} records")

        # Migrate in batches
        batch_number = 1
        current_id = min_id
        total_migrated = 0

        while current_id <= max_id:
            if max_batches and batch_number > max_batches:
                logger.info(
                    f"Reached max batch limit ({max_batches}). Stopping migration."
                )
                break

            batch_end_id = min(current_id + batch_size - 1, max_id)

            # Record batch start
            cursor.execute(
                """
                INSERT INTO logger_instance_partition_migration
                (batch_number, start_id, end_id, status, started_at)
                VALUES (%s, %s, %s, 'running', %s)
                RETURNING id
            """,
                [batch_number, current_id, batch_end_id, datetime.now()],
            )
            batch_record_id = cursor.fetchone()[0]

            try:
                # Migrate batch
                cursor.execute(
                    """
                    INSERT INTO logger_instance_partitioned (
                        id, xml, user_id, xform_id, survey_type_id, date_created,
                        date_modified, status, uuid, deleted_at, json, geom, version,
                        last_edited, media_all_received, media_count, total_media,
                        checksum, deleted_by_id, has_a_review, is_encrypted, decryption_status
                    )
                    SELECT
                        id, xml, user_id, xform_id, survey_type_id, date_created,
                        date_modified, status, uuid, deleted_at, json, geom, version,
                        last_edited, media_all_received, media_count, total_media,
                        checksum, deleted_by_id, has_a_review, is_encrypted, decryption_status
                    FROM logger_instance
                    WHERE id BETWEEN %s AND %s
                    ON CONFLICT (id, xform_id) DO NOTHING
                """,
                    [current_id, batch_end_id],
                )

                rows_affected = cursor.rowcount
                total_migrated += rows_affected

                # Update batch record
                cursor.execute(
                    """
                    UPDATE logger_instance_partition_migration
                    SET status = 'completed',
                        completed_at = %s,
                        row_count = %s
                    WHERE id = %s
                """,
                    [datetime.now(), rows_affected, batch_record_id],
                )

                logger.info(
                    f"Batch {batch_number}: Migrated {rows_affected:,} records "
                    f"(IDs {current_id:,} to {batch_end_id:,}). "
                    f"Total: {total_migrated:,}/{total_count:,} "
                    f"({(total_migrated * 100 / total_count):.1f}%)"
                )

            except Exception as e:
                # Record error
                cursor.execute(
                    """
                    UPDATE logger_instance_partition_migration
                    SET status = 'failed',
                        completed_at = %s,
                        error_message = %s
                    WHERE id = %s
                """,
                    [datetime.now(), str(e), batch_record_id],
                )
                logger.error(f"Failed to migrate batch {batch_number}: {e}")
                raise

            current_id = batch_end_id + 1
            batch_number += 1

        # Final verification
        cursor.execute("SELECT COUNT(*) FROM logger_instance_partitioned")
        final_count = cursor.fetchone()[0]
        logger.info(
            f"Migration completed. Total records in partitioned table: {final_count:,}"
        )

        if final_count != total_count:
            logger.warning(
                f"Count mismatch: Original has {total_count:,} records, "
                f"partitioned has {final_count:,} records"
            )


def verify_data_integrity(apps, schema_editor):
    """
    Verify that data in the partitioned table matches the original.
    """

    if not getattr(settings, "ENABLE_TABLE_PARTITIONING", True):
        return

    logger.info("Verifying data integrity...")

    with schema_editor.connection.cursor() as cursor:
        # Check if partitioned table exists
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename = 'logger_instance_partitioned'
            )
        """
        )
        if not cursor.fetchone()[0]:
            logger.info("Partitioned table doesn't exist. Skipping verification.")
            return

        # Compare counts
        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM logger_instance) as original_count,
                (SELECT COUNT(*) FROM logger_instance_partitioned) as partitioned_count
        """
        )
        original_count, partitioned_count = cursor.fetchone()

        if original_count != partitioned_count:
            logger.warning(
                f"Row count mismatch: original={original_count:,}, "
                f"partitioned={partitioned_count:,}"
            )
        else:
            logger.info(f"Row counts match: {original_count:,} records")

        # Check for missing records
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM logger_instance l
            LEFT JOIN logger_instance_partitioned p ON l.id = p.id
            WHERE p.id IS NULL
        """
        )
        missing_count = cursor.fetchone()[0]

        if missing_count > 0:
            logger.error(
                f"Found {missing_count:,} missing records in partitioned table"
            )
            # Get sample of missing records
            cursor.execute(
                """
                SELECT l.id, l.xform_id, l.date_created
                FROM logger_instance l
                LEFT JOIN logger_instance_partitioned p ON l.id = p.id
                WHERE p.id IS NULL
                LIMIT 10
            """
            )
            for row in cursor.fetchall():
                logger.error(
                    f"  Missing: id={row[0]}, xform_id={row[1]}, date_created={row[2]}"
                )
        else:
            logger.info("All records successfully migrated")

        # Check partition distribution
        cursor.execute(
            """
            SELECT
                tableoid::regclass as partition_name,
                COUNT(*) as row_count
            FROM logger_instance_partitioned
            GROUP BY tableoid
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """
        )
        logger.info("Top 10 partitions by row count:")
        for partition, count in cursor.fetchall():
            logger.info(f"  {partition}: {count:,} records")


def drop_sync_mechanism(apps, schema_editor):
    """
    Reverse migration: Remove sync trigger and function.
    """

    logger.info("Dropping sync mechanism...")

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "DROP TRIGGER IF EXISTS sync_instance_trigger ON logger_instance"
        )
        cursor.execute("DROP FUNCTION IF EXISTS sync_instance_to_partition()")

    logger.info("Sync mechanism dropped")


class Migration(migrations.Migration):
    atomic = False  # Large data operations shouldn't be atomic

    dependencies = [
        ("logger", "0034_partition_instance_table_structure"),
    ]

    operations = [
        migrations.RunPython(
            create_sync_mechanism,
            drop_sync_mechanism,
            elidable=False,
        ),
        migrations.RunPython(
            migrate_existing_data,
            migrations.RunPython.noop,  # Data migration doesn't need reversal
            elidable=False,
        ),
        migrations.RunPython(
            verify_data_integrity,
            migrations.RunPython.noop,  # Verification doesn't need reversal
            elidable=False,
        ),
    ]
