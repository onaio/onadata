"""
Migration to create partitioned structure for logger_instance table.
This is step 1 of 4 in the partitioning process.
"""

import logging

from django.conf import settings
from django.db import migrations

logger = logging.getLogger(__name__)


def is_already_partitioned(schema_editor):
    """Check if the table is already partitioned"""
    with schema_editor.connection.cursor() as cursor:
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
        return result and result[0] == "p"


def get_top_xforms(schema_editor, limit=10, threshold=500000, exclude_ids=None):
    """Get the top N xform_ids by instance count"""
    exclude_ids = exclude_ids or []
    exclude_clause = ""
    params = [threshold, limit]

    if exclude_ids:
        placeholders = ",".join(["%s"] * len(exclude_ids))
        exclude_clause = f"AND xform_id NOT IN ({placeholders})"
        params = [threshold] + exclude_ids + [limit]

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT xform_id, COUNT(*) as instance_count
            FROM logger_instance
            GROUP BY xform_id
            HAVING COUNT(*) >= %s
            {exclude_clause}
            ORDER BY COUNT(*) DESC
            LIMIT %s
        """,
            params,
        )
        return cursor.fetchall()


def create_partitioned_structure(apps, schema_editor):
    """
    Create the partitioned table structure alongside the existing table.
    This migration creates the structure but does NOT move data yet.
    """

    # Skip if partitioning is disabled
    if not getattr(settings, "ENABLE_TABLE_PARTITIONING", True):
        logger.info("Table partitioning is disabled in settings. Skipping.")
        return

    # Check if already partitioned
    if is_already_partitioned(schema_editor):
        logger.info("Table logger_instance is already partitioned. Skipping.")
        return

    # Check PostgreSQL version
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SHOW server_version_num")
        version = int(cursor.fetchone()[0])
        if version < 100000:  # PostgreSQL 10.0
            logger.error("PostgreSQL 10+ required for native partitioning")
            return

    # Get partition configuration from settings
    form_threshold = getattr(settings, "PARTITION_FORM_THRESHOLD", 500000)
    max_individual = getattr(settings, "PARTITION_MAX_INDIVIDUAL", 20)
    auto_detect_top_forms = getattr(settings, "PARTITION_AUTO_DETECT_TOP_FORMS", True)
    explicit_form_ids = getattr(settings, "PARTITION_EXPLICIT_FORM_IDS", [])

    # Shared partition settings
    enable_shared = getattr(settings, "PARTITION_ENABLE_SHARED", False)
    shared_count = getattr(settings, "PARTITION_SHARED_COUNT", 5)

    # Validate shared partition settings
    if enable_shared and shared_count < 1:
        logger.warning(f"Invalid PARTITION_SHARED_COUNT: {shared_count}. Must be >= 1. Disabling shared partitions.")
        enable_shared = False

    logger.info("Starting creation of partitioned table structure...")
    logger.info("Partition configuration:")
    logger.info(f"  - Threshold: {form_threshold:,} instances")
    logger.info(f"  - Max individual partitions: {max_individual}")
    logger.info(f"  - Auto-detect top forms: {auto_detect_top_forms}")
    logger.info(f"  - Explicit form IDs: {explicit_form_ids}")
    logger.info(f"  - Enable shared partitions: {enable_shared}")
    if enable_shared:
        logger.info(f"  - Shared partition count: {shared_count}")

    try:
        # Get forms for partitioning
        forms_to_partition = []

        # Add explicitly configured forms first
        if explicit_form_ids:
            with schema_editor.connection.cursor() as cursor:
                for form_id in explicit_form_ids:
                    cursor.execute(
                        """
                        SELECT
                            COUNT(*)
                        FROM logger_instance
                        WHERE xform_id = %s
                        """,
                        [form_id],
                    )
                    count = cursor.fetchone()[0]
                    if count > 0:
                        forms_to_partition.append((form_id, count))
                        logger.info(f"Explicit form {form_id}: {count:,} instances")
                    else:
                        logger.warning(f"Explicit form {form_id} has no instances")

        # Auto-detect high-volume forms if enabled
        if auto_detect_top_forms:
            remaining_slots = max_individual - len(forms_to_partition)
            if remaining_slots > 0:
                logger.info(f"Auto-detecting top {remaining_slots} forms...")
                auto_detected = get_top_xforms(
                    schema_editor,
                    limit=remaining_slots,
                    threshold=form_threshold,
                    exclude_ids=[f[0] for f in forms_to_partition],
                )
                forms_to_partition.extend(auto_detected)
                logger.info(
                    f"Auto-detected {len(auto_detected)} forms for partitioning"
                )
            else:
                logger.info("No remaining slots for auto-detection")

        # Limit to max_individual partitions
        forms_to_partition = forms_to_partition[:max_individual]

        logger.info(f"Creating {len(forms_to_partition)} individual partitions")

        # Get remaining forms for shared partitions (if enabled)
        shared_distribution = {}
        if enable_shared:
            individual_form_ids = [f[0] for f in forms_to_partition]
            logger.info("Querying remaining forms for shared partition distribution...")

            with schema_editor.connection.cursor() as cursor:
                # Get all forms that are NOT getting individual partitions
                exclude_clause = ""
                params = []
                if individual_form_ids:
                    placeholders = ",".join(["%s"] * len(individual_form_ids))
                    exclude_clause = f"WHERE xform_id NOT IN ({placeholders})"
                    params = individual_form_ids

                cursor.execute(
                    f"""
                    SELECT xform_id, COUNT(*) as instance_count
                    FROM logger_instance
                    {exclude_clause}
                    GROUP BY xform_id
                    ORDER BY xform_id
                    """,
                    params,
                )
                remaining_forms = cursor.fetchall()

            # Distribute remaining forms via hash across shared partitions
            shared_distribution = {i: [] for i in range(shared_count)}
            for xform_id, count in remaining_forms:
                partition_id = xform_id % shared_count
                shared_distribution[partition_id].append((xform_id, count))

            # Log distribution statistics
            total_shared_forms = len(remaining_forms)
            total_shared_instances = sum(count for _, count in remaining_forms)
            logger.info(f"Distributing {total_shared_forms} remaining forms to {shared_count} shared partitions")
            logger.info(f"  Total instances in shared partitions: {total_shared_instances:,}")

            for partition_id in range(shared_count):
                forms_in_partition = shared_distribution[partition_id]
                if forms_in_partition:
                    form_count = len(forms_in_partition)
                    instance_count = sum(count for _, count in forms_in_partition)
                    logger.info(f"  Shared partition {partition_id}: {form_count} forms, {instance_count:,} instances")

        with schema_editor.connection.cursor() as cursor:
            # 1. Create the new partitioned table structure
            logger.info("Creating partitioned table logger_instance_partitioned...")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS logger_instance_partitioned (
                    id integer NOT NULL DEFAULT nextval('logger_instance_id_seq'::regclass),
                    xml text NOT NULL,
                    user_id integer,
                    xform_id integer NOT NULL,
                    survey_type_id integer NOT NULL,
                    date_created timestamp with time zone NOT NULL,
                    date_modified timestamp with time zone NOT NULL,
                    status character varying(20) NOT NULL,
                    uuid character varying(249) NOT NULL,
                    deleted_at timestamp with time zone,
                    json jsonb NOT NULL,
                    geom geometry(GeometryCollection,4326),
                    version character varying(255),
                    last_edited timestamp with time zone,
                    media_all_received boolean,
                    media_count integer,
                    total_media integer,
                    checksum character varying(64),
                    deleted_by_id integer,
                    has_a_review boolean,
                    is_encrypted boolean NOT NULL,
                    decryption_status character varying(20) NOT NULL
                ) PARTITION BY LIST (xform_id)
            """
            )

            # 2. Create individual partitions for selected forms
            for xform_id, count in forms_to_partition:
                partition_name = f"logger_instance_p_{xform_id}"
                logger.info(
                    f"""Creating partition {partition_name}
                        for xform_id {xform_id} ({count:,} instances)"""
                )
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {partition_name}
                    PARTITION OF logger_instance_partitioned
                    FOR VALUES IN ({xform_id})
                """
                )

            # 3. Create shared partitions (if enabled)
            if enable_shared:
                logger.info(f"Creating {shared_count} shared partitions...")
                for partition_id in range(shared_count):
                    forms_in_partition = shared_distribution[partition_id]
                    if forms_in_partition:
                        partition_name = f"logger_instance_p_shared_{partition_id}"
                        xform_ids = [str(xform_id) for xform_id, _ in forms_in_partition]
                        form_count = len(xform_ids)
                        instance_count = sum(count for _, count in forms_in_partition)

                        logger.info(
                            f"Creating partition {partition_name} "
                            f"with {form_count} forms ({instance_count:,} instances)"
                        )

                        # Create partition with all xform_ids for this hash bucket
                        values_list = ", ".join(xform_ids)
                        cursor.execute(
                            f"""
                            CREATE TABLE IF NOT EXISTS {partition_name}
                            PARTITION OF logger_instance_partitioned
                            FOR VALUES IN ({values_list})
                        """
                        )
                    else:
                        # Create empty shared partition (for future forms)
                        # Note: Cannot create empty LIST partition, skip for now
                        # Future forms will be added via ALTER TABLE or go to default
                        logger.info(
                            f"Skipping shared partition {partition_id} (no forms assigned)"
                        )

            # 4. Create default partition for all other forms
            if enable_shared:
                logger.info("Creating default partition (catch-all for future new forms)...")
            else:
                logger.info("Creating default partition for remaining forms...")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS logger_instance_p_default
                PARTITION OF logger_instance_partitioned
                DEFAULT
            """
            )

            # 5. Create constraints on partitioned table
            logger.info("Adding constraints to partitioned table...")

            # Primary key (must include partition key xform_id)
            cursor.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'logger_instance_partitioned_pkey'
                    ) THEN
                        ALTER TABLE logger_instance_partitioned
                        ADD CONSTRAINT logger_instance_partitioned_pkey
                        PRIMARY KEY (id, xform_id);
                    END IF;
                END $$;
            """
            )

            # Check constraints
            cursor.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'logger_instance_partitioned_media_count_check'
                    ) THEN
                        ALTER TABLE logger_instance_partitioned
                        ADD CONSTRAINT logger_instance_partitioned_media_count_check
                        CHECK (media_count >= 0);
                    END IF;
                END $$;
            """
            )

            cursor.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'logger_instance_partitioned_total_media_check'
                    ) THEN
                        ALTER TABLE logger_instance_partitioned
                        ADD CONSTRAINT logger_instance_partitioned_total_media_check
                        CHECK (total_media >= 0);
                    END IF;
                END $$;
            """
            )

            # 6. Create indexes (will be created on each partition)
            logger.info("Creating indexes on partitioned table...")

            # Critical performance indexes
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_xform_id
                ON logger_instance_partitioned (xform_id)
            """
            )

            cursor.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                    idx_logger_instance_part_xform_uuid
                ON logger_instance_partitioned (xform_id, uuid)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_xform_date_created
                ON logger_instance_partitioned (xform_id, date_created)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_xform_date_modified
                ON logger_instance_partitioned (xform_id, date_modified)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_xform_deleted_at
                ON logger_instance_partitioned (xform_id, deleted_at)
            """
            )

            # Other important indexes
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_uuid
                ON logger_instance_partitioned (uuid)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_date_created
                ON logger_instance_partitioned (date_created)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_date_modified
                ON logger_instance_partitioned (date_modified)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_deleted_at
                ON logger_instance_partitioned (deleted_at)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_survey_type
                ON logger_instance_partitioned (survey_type_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_user
                ON logger_instance_partitioned (user_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_deleted_by
                ON logger_instance_partitioned (deleted_by_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_checksum
                ON logger_instance_partitioned (checksum)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_decryption_status
                ON logger_instance_partitioned (decryption_status)
            """
            )

            # Geometry index
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_geom
                ON logger_instance_partitioned USING gist(geom)
            """
            )

            # JSON field indexes
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_json_date_created
                ON logger_instance_partitioned ((json->>'_date_created'))
                WHERE (json->>'_date_created') IS NOT NULL
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_json_date_modified
                ON logger_instance_partitioned ((json->>'_date_modified'))
                WHERE (json->>'_date_modified') IS NOT NULL
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_logger_instance_part_json_deleted_at
                ON logger_instance_partitioned ((json->>'_deleted_at'))
                WHERE (json->>'_deleted_at') IS NOT NULL
            """
            )

            # 6. Create tracking table for migration progress
            logger.info("Creating migration progress tracking table...")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS logger_instance_partition_migration (
                    id SERIAL PRIMARY KEY,
                    batch_number INTEGER NOT NULL,
                    start_id BIGINT,
                    end_id BIGINT,
                    row_count BIGINT,
                    status VARCHAR(20) DEFAULT 'pending',
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_partition_migration_status
                ON logger_instance_partition_migration(status)
            """
            )

            # 7. Verify partition structure
            cursor.execute(
                """
                SELECT
                    nmsp_parent.nspname AS parent_schema,
                    parent.relname AS parent_table,
                    COUNT(*) as partition_count
                FROM pg_inherits
                JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
                JOIN pg_class child ON pg_inherits.inhrelid = child.oid
                JOIN pg_namespace nmsp_parent
                    ON parent.relnamespace = nmsp_parent.oid
                WHERE parent.relname = 'logger_instance_partitioned'
                GROUP BY parent_schema, parent_table
            """
            )

            result = cursor.fetchone()
            if result:
                partition_count = result[2]
                logger.info(
                    f"Success - created partitioned table with {partition_count} partitions"
                )
                logger.info("Partition breakdown:")
                logger.info(f"  - Individual partitions: {len(forms_to_partition)}")
                if enable_shared:
                    shared_with_forms = sum(1 for forms in shared_distribution.values() if forms)
                    logger.info(f"  - Shared partitions: {shared_with_forms}")
                logger.info("  - Default partition: 1")

    except Exception as e:
        logger.error(f"Error creating partitioned structure: {e}")
        # Re-raise to fail the migration
        raise


def drop_partitioned_structure(apps, schema_editor):
    """
    Reverse migration: Remove the partitioned table structure.
    This is safe as we haven't moved any data yet.
    """
    logger.info("Dropping partitioned table structure...")

    with schema_editor.connection.cursor() as cursor:
        # Drop tracking table
        cursor.execute(
            "DROP TABLE IF EXISTS logger_instance_partition_migration CASCADE"
        )

        # Drop partitioned table and all partitions
        cursor.execute("DROP TABLE IF EXISTS logger_instance_partitioned CASCADE")

    logger.info("Partitioned structure dropped successfully")


class Migration(migrations.Migration):
    atomic = False  # Required for CREATE INDEX CONCURRENTLY

    dependencies = [
        ("logger", "0033_populate_entityhistory_mutation_type"),
    ]

    operations = [
        migrations.RunPython(
            create_partitioned_structure,
            drop_partitioned_structure,
            elidable=False,  # Never skip this migration
        ),
    ]
