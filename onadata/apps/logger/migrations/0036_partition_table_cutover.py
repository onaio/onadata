"""
Migration to perform final cutover to partitioned table.
This is step 3 of 4 in the partitioning process.

IMPORTANT: This migration requires brief downtime during cutover.
Ensure application is stopped or in maintenance mode before running.
"""

import logging

from django.conf import settings
from django.db import migrations, transaction

logger = logging.getLogger(__name__)


def perform_cutover(apps, schema_editor):
    """
    Perform the final cutover to the partitioned table.
    This will:
    1. Perform final data sync
    2. Drop the sync trigger
    3. Rename tables
    4. Update foreign key constraints
    """

    if not getattr(settings, "ENABLE_TABLE_PARTITIONING", False):
        logger.info("Table partitioning is disabled. Skipping cutover.")
        return

    logger.info("=" * 60)
    logger.info("STARTING PARTITIONED TABLE CUTOVER")
    logger.info("=" * 60)

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
            logger.info("Partitioned table doesn't exist. Skipping cutover.")
            return

        # Check if we've already done the cutover
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename = 'logger_instance_original'
            )
        """
        )
        if cursor.fetchone()[0]:
            logger.info(
                "Cutover appears to have been done already (logger_instance_original exists)"
            )
            return

        try:
            # Start a savepoint for rollback capability
            sid = transaction.savepoint()

            # 1. Final data verification
            logger.info("Performing final data verification...")
            cursor.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM logger_instance) as orig_count,
                    (SELECT COUNT(*) FROM logger_instance_partitioned) as part_count
            """
            )
            orig_count, part_count = cursor.fetchone()

            if orig_count != part_count:
                # Try final catch-up
                logger.info(
                    f"Count mismatch: {orig_count} vs {part_count}. Final sync..."
                )
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
                    FROM logger_instance l
                    WHERE NOT EXISTS (
                        SELECT 1 FROM logger_instance_partitioned p
                        WHERE p.id = l.id
                    )
                """
                )
                sync_count = cursor.rowcount
                logger.info(f"Synced {sync_count} additional records")

                # Re-verify
                cursor.execute("SELECT COUNT(*) FROM logger_instance_partitioned")
                part_count = cursor.fetchone()[0]

                if orig_count != part_count:
                    logger.error(
                        f"Still mismatch after sync: {orig_count} vs {part_count}"
                    )
                    if not getattr(
                        settings, "PARTITION_MIGRATION_FORCE_CUTOVER", False
                    ):
                        transaction.savepoint_rollback(sid)
                        raise Exception(
                            "Data verification failed. Set PARTITION_MIGRATION_FORCE_CUTOVER=True to proceed anyway."
                        )

            logger.info(
                f"Data verification passed: {orig_count} records in both tables"
            )

            # 2. Drop sync trigger
            logger.info("Dropping sync trigger...")
            cursor.execute(
                "DROP TRIGGER IF EXISTS sync_instance_trigger ON logger_instance"
            )
            cursor.execute("DROP FUNCTION IF EXISTS sync_instance_to_partition()")

            # 3. Get list of dependent objects before rename
            logger.info("Identifying dependent objects...")
            cursor.execute(
                """
                SELECT
                    con.conname,
                    con.conrelid::regclass::text as table_name,
                    att.attname as column_name
                FROM pg_constraint con
                JOIN pg_attribute att ON att.attrelid = con.conrelid
                    AND att.attnum = ANY(con.conkey)
                WHERE con.confrelid = 'logger_instance'::regclass
                AND con.contype = 'f'
            """
            )
            foreign_keys = cursor.fetchall()
            logger.info(f"Found {len(foreign_keys)} foreign key constraints to update")

            # 3.5. Get list of indexes on original table (before rename)
            logger.info("Identifying indexes on original table...")
            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename = 'logger_instance'
                AND indexname NOT LIKE '%_pkey'
                AND indexname NOT LIKE '%_original'
            """
            )
            original_indexes = [row[0] for row in cursor.fetchall()]
            logger.info(f"Found {len(original_indexes)} indexes on original table")

            # 4. Rename tables
            logger.info("Renaming tables...")
            cursor.execute(
                "ALTER TABLE logger_instance RENAME TO logger_instance_original"
            )
            cursor.execute(
                "ALTER TABLE logger_instance_partitioned RENAME TO logger_instance"
            )
            logger.info("Tables renamed successfully")

            # 4.5. Rename indexes on original table to avoid conflicts
            logger.info("Renaming indexes on original table...")
            for index_name in original_indexes:
                new_name = f"{index_name}_original"
                try:
                    sid_idx = transaction.savepoint()
                    cursor.execute(f"ALTER INDEX {index_name} RENAME TO {new_name}")
                    transaction.savepoint_commit(sid_idx)
                    logger.info(f"Renamed {index_name} -> {new_name}")
                except Exception as e:
                    transaction.savepoint_rollback(sid_idx)
                    logger.warning(f"Could not rename index {index_name}: {e}")

            # 4.6. Create unique indexes on id for each partition (for foreign key support)
            logger.info("Creating unique indexes on id for each partition...")
            cursor.execute(
                """
                SELECT t.tablename
                FROM pg_tables t
                JOIN pg_class c ON c.relname = t.tablename
                WHERE t.schemaname = 'public'
                AND t.tablename LIKE 'logger_instance_p_%'
                AND c.relkind = 'r'
            """
            )

            partitions = [row[0] for row in cursor.fetchall()]
            logger.info(f"Found {len(partitions)} leaf partitions to index")

            for partition_name in partitions:
                index_name = f"{partition_name}_id_unique"
                try:
                    sid_part = transaction.savepoint()
                    cursor.execute(
                        f"""
                        CREATE UNIQUE INDEX IF NOT EXISTS {index_name}
                        ON {partition_name} (id)
                    """
                    )
                    transaction.savepoint_commit(sid_part)
                    logger.info(f"Created unique index on {partition_name}.id")
                except Exception as e:
                    transaction.savepoint_rollback(sid_part)
                    logger.warning(
                        f"Could not create unique index on {partition_name}: {e}"
                    )

            # 5. Rename constraints to match original names (idempotent)
            logger.info("Renaming constraints...")

            # Define constraint renames (old_name, new_name)
            constraint_renames = [
                ("logger_instance_partitioned_pkey", "odk_logger_instance_pkey"),
                (
                    "logger_instance_partitioned_media_count_check",
                    "logger_instance_media_count_check",
                ),
                (
                    "logger_instance_partitioned_total_media_check",
                    "logger_instance_total_media_check",
                ),
            ]

            for old_name, new_name in constraint_renames:
                # Check if constraint exists
                cursor.execute(
                    """
                    SELECT constraint_name
                    FROM information_schema.table_constraints
                    WHERE table_schema = 'public'
                    AND table_name = 'logger_instance'
                    AND constraint_name IN (%s, %s)
                    """,
                    [old_name, new_name],
                )
                existing = [row[0] for row in cursor.fetchall()]

                if old_name in existing and new_name not in existing:
                    # Source exists, target doesn't - do the rename
                    try:
                        sid_con = transaction.savepoint()
                        cursor.execute(
                            f"ALTER TABLE logger_instance RENAME CONSTRAINT {old_name} TO {new_name}"
                        )
                        transaction.savepoint_commit(sid_con)
                        logger.info(f"Renamed constraint: {old_name} → {new_name}")
                    except Exception as e:
                        transaction.savepoint_rollback(sid_con)
                        logger.warning(
                            f"Could not rename constraint {old_name} to {new_name}: {e}"
                        )
                elif new_name in existing:
                    # Target already exists - already renamed
                    logger.info(
                        f"Constraint {new_name} already exists, skipping rename"
                    )
                else:
                    # Neither exists - unexpected but continue
                    logger.warning(f"Constraint {old_name} not found, skipping rename")

            # 6. Rename indexes to match original pattern
            logger.info("Renaming indexes...")
            index_renames = [
                ("idx_logger_instance_part_xform_id", "odk_logger_instance_xform_id"),
                (
                    "idx_logger_instance_part_xform_uuid",
                    "logger_instance_xform_id_7f6c29725befa0b0_uniq",
                ),
                (
                    "idx_logger_instance_part_xform_date_created",
                    "logger_instance_xform_id_date_created_idx",
                ),
                (
                    "idx_logger_instance_part_xform_date_modified",
                    "logger_instance_xform_id_date_modified_idx",
                ),
                (
                    "idx_logger_instance_part_xform_deleted_at",
                    "logger_instance_xform_id_deleted_at_idx",
                ),
                ("idx_logger_instance_part_uuid", "logger_instance_uuid_9b502899"),
                (
                    "idx_logger_instance_part_date_created",
                    "logger_inst_date_cr_42899d_idx",
                ),
                (
                    "idx_logger_instance_part_date_modified",
                    "logger_inst_date_mo_5a1bd3_idx",
                ),
                (
                    "idx_logger_instance_part_deleted_at",
                    "logger_inst_deleted_at_da31a3_idx",
                ),
                (
                    "idx_logger_instance_part_survey_type",
                    "odk_logger_instance_survey_type_id",
                ),
                ("idx_logger_instance_part_user", "odk_logger_instance_user_id"),
                (
                    "idx_logger_instance_part_deleted_by",
                    "logger_instance_deleted_by_id_8bd3fe97",
                ),
                (
                    "idx_logger_instance_part_checksum",
                    "logger_instance_checksum_1aae3299",
                ),
                (
                    "idx_logger_instance_part_decryption_status",
                    "logger_inst_decrypt_1b32ab_idx",
                ),
                ("idx_logger_instance_part_geom", "odk_logger_instance_geom_id"),
                (
                    "idx_logger_instance_part_json_date_created",
                    "logger_inst_date_cr_json_42899d_idx",
                ),
                (
                    "idx_logger_instance_part_json_date_modified",
                    "logger_inst_date_mo_json_5a1bd3_idx",
                ),
                (
                    "idx_logger_instance_part_json_deleted_at",
                    "logger_inst_deleted_at_json_da31a3_idx",
                ),
            ]

            for old_name, new_name in index_renames:
                try:
                    sid_idx = transaction.savepoint()
                    cursor.execute(f"ALTER INDEX {old_name} RENAME TO {new_name}")
                    transaction.savepoint_commit(sid_idx)
                except Exception as e:
                    transaction.savepoint_rollback(sid_idx)
                    logger.warning(f"Could not rename index {old_name}: {e}")

            # 7. Recreate foreign key constraints
            logger.info("Recreating foreign key constraints...")

            # Add foreign keys FROM logger_instance to other tables
            instance_fk_constraints = [
                (
                    "logger_instance_xform_id_ebcfcca3_fk_logger_xform_id",
                    "xform_id",
                    "logger_xform(id)",
                ),
                (
                    "survey_type_id_refs_id_921d431d",
                    "survey_type_id",
                    "logger_surveytype(id)",
                ),
                (
                    "user_id_refs_id_872f51db",
                    "user_id",
                    "auth_user(id)",
                ),
                (
                    "logger_instance_deleted_by_id_8bd3fe97_fk_auth_user_id",
                    "deleted_by_id",
                    "auth_user(id)",
                ),
            ]

            for constraint_name, column, reference in instance_fk_constraints:
                try:
                    sid_fk = transaction.savepoint()
                    cursor.execute(
                        f"""
                        ALTER TABLE logger_instance
                        ADD CONSTRAINT {constraint_name}
                        FOREIGN KEY ({column}) REFERENCES {reference} DEFERRABLE INITIALLY DEFERRED
                    """
                    )
                    transaction.savepoint_commit(sid_fk)
                    logger.info(f"Created FK: {constraint_name}")
                except Exception as e:
                    transaction.savepoint_rollback(sid_fk)
                    logger.warning(f"Could not create FK {constraint_name}: {e}")

            # Update foreign keys TO logger_instance from other tables
            fk_created_count = 0
            fk_skipped_count = 0

            for conname, table_name, column_name in foreign_keys:
                logger.info(
                    f"Updating foreign key {conname} on {table_name}.{column_name}"
                )

                # Check if table has xform_id column
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = %s
                        AND column_name = 'xform_id'
                    )
                """,
                    [table_name.replace("public.", "")],
                )
                has_xform_id = cursor.fetchone()[0]

                try:
                    sid_fk = transaction.savepoint()
                    # Drop old constraint
                    cursor.execute(
                        f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {conname}"
                    )

                    if has_xform_id:
                        # Create composite FK for tables with xform_id
                        logger.info(
                            f"  → {table_name} has xform_id, creating composite FK"
                        )
                        cursor.execute(
                            f"""
                            ALTER TABLE {table_name}
                            ADD CONSTRAINT {conname}
                            FOREIGN KEY ({column_name}, xform_id)
                            REFERENCES logger_instance(id, xform_id)
                            DEFERRABLE INITIALLY DEFERRED
                        """
                        )

                        # Create composite index for better performance
                        index_name = f"{table_name.replace('public.', '')}"
                        index_name += f"_{column_name}_xform_idx"
                        cursor.execute(
                            f"""
                            CREATE INDEX IF NOT EXISTS {index_name}
                            ON {table_name} ({column_name}, xform_id)
                        """
                        )
                        logger.info("  ✓ Created composite FK and index")
                        fk_created_count += 1
                    else:
                        # Skip tables without xform_id - cannot create working FK
                        logger.warning(
                            f"  ⚠ {table_name} doesn't have xform_id - can't create FK"
                        )
                        logger.warning(
                            f"  ⚠ Ref integrity NOT enforced {table_name}.{column_name}"
                        )
                        logger.warning(
                            "  ⚠ Consider adding xform_id column in future migration"
                        )
                        fk_skipped_count += 1

                    transaction.savepoint_commit(sid_fk)
                except Exception as e:
                    transaction.savepoint_rollback(sid_fk)
                    logger.error(
                        f"  ✗ Failed to update FK {conname} on {table_name}: {e}"
                    )
                    fk_skipped_count += 1

            logger.info("Foreign key recreation summary:")
            logger.info(f"  ✓ Created composite FKs: {fk_created_count}")
            logger.info(f"  ⚠ Skipped (no xform_id): {fk_skipped_count}")

            # 8. Update table statistics
            logger.info("Updating table statistics...")
            cursor.execute("ANALYZE logger_instance")

            # Set higher statistics for xform_id column
            cursor.execute(
                "ALTER TABLE logger_instance ALTER COLUMN xform_id SET STATISTICS 1000"
            )

            # 9. Configure autovacuum for high-traffic partitions
            logger.info("Configuring autovacuum settings...")
            cursor.execute(
                """
                SELECT t.tablename
                FROM pg_tables t
                JOIN pg_class c ON c.relname = t.tablename
                WHERE t.schemaname = 'public'
                AND t.tablename LIKE 'logger_instance_p_%'
                AND c.relkind = 'r'
                ORDER BY t.tablename
            """
            )

            leaf_partitions = cursor.fetchall()
            logger.info(f"Found {len(leaf_partitions)} leaf partitions to configure")

            for (partition_name,) in leaf_partitions:
                try:
                    sid_autovac = transaction.savepoint()
                    cursor.execute(
                        f"""
                        ALTER TABLE {partition_name} SET (
                            autovacuum_vacuum_scale_factor = 0.05,
                            autovacuum_analyze_scale_factor = 0.02
                        )
                    """
                    )
                    transaction.savepoint_commit(sid_autovac)
                    logger.info(f"Configured autovacuum for {partition_name}")
                except Exception as e:
                    transaction.savepoint_rollback(sid_autovac)
                    logger.warning(
                        f"Could not configure autovacuum for {partition_name}: {e}"
                    )

            # 10. Verify the cutover
            logger.info("Verifying cutover...")
            cursor.execute(
                """
                SELECT c.relkind
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                AND c.relname = 'logger_instance'
            """
            )
            result = cursor.fetchone()
            if result and result[0] == "p":
                logger.info("✓ Successfully switched to partitioned table")
            else:
                logger.error("✗ Table is not partitioned after cutover")
                transaction.savepoint_rollback(sid)
                raise Exception("Cutover verification failed")

            # Commit the savepoint
            transaction.savepoint_commit(sid)

            logger.info("=" * 60)
            logger.info("CUTOVER COMPLETED SUCCESSFULLY!")
            logger.info("The partitioned table is now active.")
            logger.info("Original table has been renamed to: logger_instance_original")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Cutover failed: {e}")
            if sid:
                transaction.savepoint_rollback(sid)
            raise


def reverse_cutover(apps, schema_editor):
    """
    Reverse the cutover - switch back to the original non-partitioned table.
    """

    logger.info("Reversing cutover to original table...")

    with schema_editor.connection.cursor() as cursor:
        # Check if original table exists
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename = 'logger_instance_original'
            )
        """
        )
        if not cursor.fetchone()[0]:
            logger.info("Original table doesn't exist. Nothing to reverse.")
            return

        try:
            # Get foreign keys again
            cursor.execute(
                """
                SELECT
                    con.conname,
                    con.conrelid::regclass::text as table_name,
                    att.attname as column_name
                FROM pg_constraint con
                JOIN pg_attribute att ON att.attrelid = con.conrelid
                    AND att.attnum = ANY(con.conkey)
                WHERE con.confrelid = 'logger_instance'::regclass
                AND con.contype = 'f'
            """
            )
            foreign_keys = cursor.fetchall()

            # Drop foreign keys from partitioned table
            for conname, table_name, column_name in foreign_keys:
                cursor.execute(
                    f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {conname}"
                )

            # Rename tables back
            cursor.execute(
                "ALTER TABLE logger_instance RENAME TO logger_instance_partitioned"
            )
            cursor.execute(
                "ALTER TABLE logger_instance_original RENAME TO logger_instance"
            )

            # Restore foreign keys
            fk_restored = 0
            fk_skipped = 0
            for conname, table_name, column_name in foreign_keys:
                try:
                    sid_fk = transaction.savepoint()
                    cursor.execute(
                        f"""
                        ALTER TABLE {table_name}
                        ADD CONSTRAINT {conname}
                        FOREIGN KEY ({column_name}) REFERENCES logger_instance(id) DEFERRABLE INITIALLY DEFERRED
                    """
                    )
                    transaction.savepoint_commit(sid_fk)
                    fk_restored += 1
                    logger.info(f"Restored FK: {conname} on {table_name}")
                except Exception as e:
                    transaction.savepoint_rollback(sid_fk)
                    fk_skipped += 1
                    logger.warning(
                        f"Could not restore FK {conname} on {table_name}: {e}"
                    )

            logger.info(f"FK restoration: {fk_restored} restored, {fk_skipped} skipped")
            logger.info("Successfully reversed cutover")

        except Exception as e:
            logger.error(f"Failed to reverse cutover: {e}")
            raise


class Migration(migrations.Migration):
    atomic = True  # This migration should be atomic

    dependencies = [
        ("logger", "0035_partition_sync_and_migrate_data"),
    ]

    operations = [
        migrations.RunPython(
            perform_cutover,
            reverse_cutover,
            elidable=False,
        ),
    ]
