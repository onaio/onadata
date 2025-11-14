"""
Migration to clean up after successful partitioning.
This is step 4 of 4 in the partitioning process.

This migration:
- Optionally drops the original table (if configured)
- Cleans up temporary tracking tables
- Creates maintenance functions for ongoing partition management
"""

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.db import migrations

logger = logging.getLogger(__name__)


def cleanup_old_table(apps, schema_editor):
    """
    Clean up the original table and migration tracking data.
    Only drops the original table if explicitly configured to do so.
    """

    if not getattr(settings, "ENABLE_TABLE_PARTITIONING", True):
        logger.info("Table partitioning is disabled. Skipping cleanup.")
        return

    logger.info("Starting post-partitioning cleanup...")

    with schema_editor.connection.cursor() as cursor:
        # Check if the original table exists
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename = 'logger_instance_original'
            )
        """
        )
        original_exists = cursor.fetchone()[0]

        if original_exists:
            # Get the age and size of the original table
            cursor.execute(
                """
                SELECT
                    pg_size_pretty(pg_total_relation_size('logger_instance_original')) as size,
                    COUNT(*) as row_count
                FROM logger_instance_original
            """
            )
            size, row_count = cursor.fetchone() or ("0 bytes", 0)

            logger.info(f"Original table exists: {row_count:,} rows, size: {size}")

            # Check if we should drop it
            days_to_keep = getattr(settings, "PARTITION_KEEP_ORIGINAL_DAYS", 7)
            drop_original = getattr(settings, "PARTITION_DROP_ORIGINAL_TABLE", False)

            if drop_original:
                logger.warning("DROPPING ORIGINAL TABLE AS CONFIGURED")
                cursor.execute("DROP TABLE logger_instance_original CASCADE")
                logger.info("Original table dropped")
            else:
                logger.info(
                    f"Original table retained. Set PARTITION_DROP_ORIGINAL_TABLE=True "
                    f"to drop it after {days_to_keep} days"
                )

                # Create a scheduled cleanup comment
                drop_after_date = datetime.now() + timedelta(days=days_to_keep)
                cursor.execute(
                    f"""
                    COMMENT ON TABLE logger_instance_original IS
                    'Original non-partitioned table. Retained for rollback. '
                    'Can be dropped after {drop_after_date.strftime('%Y-%m-%d')} if partitioning is stable.'
                """
                )

        # Clean up migration tracking table if configured
        if getattr(settings, "PARTITION_CLEANUP_TRACKING_TABLE", True):
            cursor.execute(
                """
                DROP TABLE IF EXISTS logger_instance_partition_migration CASCADE
            """
            )
            logger.info("Migration tracking table cleaned up")


def create_partition_maintenance_functions(apps, schema_editor):
    """
    Create functions for ongoing partition maintenance.
    """

    if not getattr(settings, "ENABLE_TABLE_PARTITIONING", True):
        return

    logger.info("Creating partition maintenance functions...")

    with schema_editor.connection.cursor() as cursor:
        # Function to analyze partition distribution
        cursor.execute(
            """
            CREATE OR REPLACE FUNCTION analyze_partition_distribution()
            RETURNS TABLE(
                partition_name text,
                row_count bigint,
                total_size text,
                table_size text,
                index_size text,
                xform_ids text
            ) AS $$
            BEGIN
                RETURN QUERY
                SELECT
                    c.relname::text as partition_name,
                    c.reltuples::bigint as row_count,
                    pg_size_pretty(pg_total_relation_size(c.oid)) as total_size,
                    pg_size_pretty(pg_relation_size(c.oid)) as table_size,
                    pg_size_pretty(pg_indexes_size(c.oid)) as index_size,
                    CASE
                        WHEN c.relname LIKE 'logger_instance_p_%' THEN
                            SUBSTRING(c.relname FROM 'logger_instance_p_(.+)')
                        ELSE 'multiple'
                    END as xform_ids
                FROM pg_inherits i
                JOIN pg_class parent ON i.inhparent = parent.oid
                JOIN pg_class c ON i.inhrelid = c.oid
                WHERE parent.relname = 'logger_instance'
                ORDER BY c.reltuples DESC;
            END;
            $$ LANGUAGE plpgsql;
        """
        )

        # Function to identify candidates for new partitions
        cursor.execute(
            """
            CREATE OR REPLACE FUNCTION identify_partition_candidates(
                threshold integer DEFAULT 1000000
            )
            RETURNS TABLE(
                xform_id integer,
                instance_count bigint,
                recommendation text
            ) AS $$
            BEGIN
                RETURN QUERY
                WITH form_counts AS (
                    SELECT
                        li.xform_id,
                        COUNT(*) as cnt
                    FROM logger_instance li
                    WHERE li.tableoid = 'logger_instance_p_default'::regclass
                    GROUP BY li.xform_id
                    HAVING COUNT(*) >= threshold
                )
                SELECT
                    fc.xform_id,
                    fc.cnt as instance_count,
                    'CREATE TABLE logger_instance_p_' || fc.xform_id ||
                    ' PARTITION OF logger_instance FOR VALUES IN (' || fc.xform_id || ');' as recommendation
                FROM form_counts fc
                ORDER BY fc.cnt DESC;
            END;
            $$ LANGUAGE plpgsql;
        """
        )

        # Function to check partition health
        cursor.execute(
            """
            CREATE OR REPLACE FUNCTION check_partition_health()
            RETURNS TABLE(
                check_name text,
                status text,
                details text
            ) AS $$
            DECLARE
                part_count integer;
                total_rows bigint;
                default_rows bigint;
                default_percent numeric;
            BEGIN
                -- Count partitions
                SELECT COUNT(*) INTO part_count
                FROM pg_inherits
                WHERE inhparent = 'logger_instance'::regclass;

                RETURN QUERY
                SELECT
                    'Partition Count'::text,
                    'INFO'::text,
                    'Total partitions: ' || part_count::text;

                -- Check total rows
                SELECT COUNT(*) INTO total_rows FROM logger_instance;

                RETURN QUERY
                SELECT
                    'Total Rows'::text,
                    'INFO'::text,
                    'Total rows across all partitions: ' || TO_CHAR(total_rows, 'FM999,999,999,999');

                -- Check default partition size
                BEGIN
                    SELECT COUNT(*) INTO default_rows
                    FROM logger_instance_p_default;

                    default_percent := CASE
                        WHEN total_rows > 0 THEN
                            ROUND(100.0 * default_rows / total_rows, 2)
                        ELSE 0
                    END;

                    RETURN QUERY
                    SELECT
                        'Default Partition Size'::text,
                        CASE
                            WHEN default_percent > 50 THEN 'WARNING'::text
                            ELSE 'OK'::text
                        END,
                        'Default partition has ' || TO_CHAR(default_rows, 'FM999,999,999,999') ||
                        ' rows (' || default_percent || '% of total)';
                EXCEPTION
                    WHEN OTHERS THEN
                        RETURN QUERY
                        SELECT
                            'Default Partition'::text,
                            'ERROR'::text,
                            'Could not check default partition: ' || SQLERRM;
                END;

                -- Check for constraint exclusion
                RETURN QUERY
                SELECT
                    'Constraint Exclusion'::text,
                    CASE
                        WHEN current_setting('constraint_exclusion') IN ('on', 'partition') THEN 'OK'::text
                        ELSE 'WARNING'::text
                    END,
                    'constraint_exclusion = ' || current_setting('constraint_exclusion');

                -- Check for partition-wise joins
                RETURN QUERY
                SELECT
                    'Partition-wise Joins'::text,
                    CASE
                        WHEN current_setting('enable_partitionwise_join') = 'on' THEN 'OK'::text
                        ELSE 'INFO'::text
                    END,
                    'enable_partitionwise_join = ' || current_setting('enable_partitionwise_join');

                RETURN;
            END;
            $$ LANGUAGE plpgsql;
        """
        )

        logger.info("Partition maintenance functions created")


def create_partition_monitoring_views(apps, schema_editor):
    """
    Create views for easy partition monitoring.
    """

    if not getattr(settings, "ENABLE_TABLE_PARTITIONING", True):
        return

    logger.info("Creating partition monitoring views...")

    with schema_editor.connection.cursor() as cursor:
        # View for partition statistics
        cursor.execute(
            """
            CREATE OR REPLACE VIEW v_partition_stats AS
            SELECT
                schemaname,
                relname AS tablename,
                CASE
                    WHEN relname = 'logger_instance' THEN 'PARENT'
                    WHEN relname LIKE 'logger_instance_p_%' THEN 'PARTITION'
                    ELSE 'UNKNOWN'
                END as table_type,
                CASE
                    WHEN relname LIKE 'logger_instance_p_%' THEN
                        SUBSTRING(relname FROM 'logger_instance_p_(.+)')
                    ELSE NULL
                END as partition_key,
                n_live_tup as row_count,
                n_dead_tup as dead_rows,
                ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) as bloat_percent,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze,
                vacuum_count,
                autovacuum_count,
                analyze_count,
                autoanalyze_count
            FROM pg_stat_user_tables
            WHERE relname LIKE 'logger_instance%'
            ORDER BY
                CASE
                    WHEN relname = 'logger_instance' THEN 0
                    ELSE 1
                END,
                n_live_tup DESC;
        """
        )

        # View for partition sizes
        cursor.execute(
            """
            CREATE OR REPLACE VIEW v_partition_sizes AS
            WITH base_tables AS (
                SELECT
                    schemaname,
                    tablename,
                    (schemaname||'.'||tablename)::regclass as relation
                FROM pg_tables
                WHERE tablename LIKE 'logger_instance%'
            )
            SELECT
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(relation)) as total_size,
                pg_size_pretty(pg_relation_size(relation)) as table_size,
                pg_size_pretty(pg_indexes_size(relation)) as index_size,
                pg_total_relation_size(relation) as total_bytes
            FROM base_tables
            ORDER BY pg_total_relation_size(relation) DESC;
        """
        )

        logger.info("Monitoring views created")


def drop_maintenance_objects(apps, schema_editor):
    """
    Reverse migration: Drop maintenance functions and views.
    """

    logger.info("Dropping maintenance objects...")

    with schema_editor.connection.cursor() as cursor:
        # Drop views
        cursor.execute("DROP VIEW IF EXISTS v_partition_stats CASCADE")
        cursor.execute("DROP VIEW IF EXISTS v_partition_sizes CASCADE")

        # Drop functions
        cursor.execute(
            "DROP FUNCTION IF EXISTS analyze_partition_distribution() CASCADE"
        )
        cursor.execute(
            "DROP FUNCTION IF EXISTS identify_partition_candidates(integer) CASCADE"
        )
        cursor.execute("DROP FUNCTION IF EXISTS check_partition_health() CASCADE")

    logger.info("Maintenance objects dropped")


class Migration(migrations.Migration):
    atomic = False  # Allows for partial completion

    dependencies = [
        ("logger", "0036_partition_table_cutover"),
    ]

    operations = [
        migrations.RunPython(
            cleanup_old_table,
            migrations.RunPython.noop,  # No reversal for cleanup
            elidable=False,
        ),
        migrations.RunPython(
            create_partition_maintenance_functions,
            drop_maintenance_objects,
            elidable=False,
        ),
        migrations.RunPython(
            create_partition_monitoring_views,
            migrations.RunPython.noop,  # Views can be recreated
            elidable=False,
        ),
    ]
