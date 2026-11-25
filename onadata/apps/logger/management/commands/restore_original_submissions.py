"""Restore submissions to the XML they were first submitted with."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy

from multidb.pinning import use_master

from onadata.apps.logger.models import Instance, XForm
from onadata.apps.logger.models.instance import InstanceHistory
from onadata.apps.logger.xform_instance_parser import is_encrypted_submission
from onadata.apps.viewer.models.parsed_instance import ParsedInstance


def _parse_instance_ids(raw_ids):
    instance_ids = raw_ids.split(",")
    invalid = [value for value in instance_ids if not value.isdecimal()]

    if invalid:
        raise CommandError(f"Invalid instance ids: {invalid}")

    return [int(value) for value in instance_ids]


def _edited_instance_ids(form_id):
    if not XForm.objects.filter(pk=form_id).exists():
        raise CommandError(f"Form {form_id} does not exist")

    return list(
        Instance.objects.filter(
            xform_id=form_id,
            deleted_at__isnull=True,
            submission_history__isnull=False,
        )
        .order_by("pk")
        .values_list("pk", flat=True)
        .distinct()
    )


def _skip_reason(instance, original):
    if instance is None:
        return "not found or deleted"

    if original is None:
        return "no history"

    if not original.uuid or not original.checksum:
        return f"history row {original.pk} lacks uuid or checksum"

    if is_encrypted_submission(original.xml):
        return "first version is encrypted"

    if instance.xml == original.xml:
        return "already the original"

    return None


def _replace_with_original(instance, original):
    InstanceHistory.objects.create(
        xform_instance=instance,
        xml=instance.xml,
        uuid=instance.uuid,
        checksum=instance.checksum,
        geom=instance.geom,
        submission_date=instance.last_edited or instance.date_created,
    )
    instance.xml = original.xml
    instance.uuid = original.uuid
    instance.checksum = original.checksum
    instance.last_edited = timezone.now()
    instance.last_edited_by = None
    instance.save()
    parsed_instance, created = ParsedInstance.objects.get_or_create(instance=instance)

    if not created:
        parsed_instance.save()


def _restore(instance_id, commit):
    with transaction.atomic():
        instance = (
            Instance.objects.select_for_update()
            .filter(pk=instance_id, deleted_at__isnull=True)
            .first()
        )
        original = (
            instance.submission_history.order_by("date_created", "pk").first()
            if instance
            else None
        )
        skip_reason = _skip_reason(instance, original)

        if skip_reason:
            return f"{instance_id}: skipped, {skip_reason}"

        if not commit:
            return f"{instance_id}: would restore uuid {original.uuid}"

        _replace_with_original(instance, original)

    return f"{instance_id}: restored"


class Command(BaseCommand):
    help = gettext_lazy(
        "Restores submissions to the XML they were first submitted with."
    )

    def add_arguments(self, parser):
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument(
            "--instance-ids",
            "-i",
            dest="instance_ids",
            help="A submission id, or several separated by commas.",
        )
        target.add_argument(
            "--form-id",
            "-f",
            dest="form_id",
            type=int,
            help="A form id, to restore every edited submission in the form.",
        )
        parser.add_argument(
            "--commit-changes",
            "-c",
            action="store_true",
            dest="commit",
            default=False,
            help="Save the restored XML.",
        )

    @use_master
    def handle(self, *args, **options):
        instance_ids = (
            _edited_instance_ids(options["form_id"])
            if options["form_id"] is not None
            else _parse_instance_ids(options["instance_ids"])
        )

        for instance_id in instance_ids:
            try:
                outcome = _restore(instance_id, options["commit"])
            except Exception as error:  # noqa: BLE001  # pylint: disable=broad-except
                outcome = f"{instance_id}: failed, {type(error).__name__}: {error}"

            self.stdout.write(outcome)
