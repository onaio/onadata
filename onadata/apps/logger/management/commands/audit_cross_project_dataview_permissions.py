"""Audit and repair suspected DataView-derived source XForm grants."""

import csv
from collections import defaultdict

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from multidb.pinning import use_master

from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.project import (
    Project,
    ProjectGroupObjectPermission,
    ProjectUserObjectPermission,
)
from onadata.apps.logger.models.xform import (
    XForm,
    XFormGroupObjectPermission,
    XFormUserObjectPermission,
)
from onadata.libs.permissions import ROLES, ROLES_ORDERED
from onadata.libs.utils.xform_utils import clear_permissions_cache

User = get_user_model()

PRINCIPAL_CONFIG = {
    "user": (
        User,
        ProjectUserObjectPermission,
        XFormUserObjectPermission,
        "user_id",
        "username",
    ),
    "group": (
        Group,
        ProjectGroupObjectPermission,
        XFormGroupObjectPermission,
        "group_id",
        "name",
    ),
}

REPORT_FIELDS = (
    "record_type",
    "dataview_id",
    "dataview_ids",
    "dataview_name",
    "dataview_deleted_at",
    "destination_project_id",
    "destination_project_name",
    "xform_id",
    "xform_id_string",
    "xform_project_id",
    "xform_project_name",
    "principal_type",
    "principal_id",
    "principal_name",
    "destination_role",
    "xform_permissions",
)

REVIEW_REQUIRED_FIELDS = {
    "record_type",
    "dataview_ids",
    "destination_project_id",
    "xform_id",
    "xform_project_id",
    "principal_type",
    "principal_id",
    "principal_name",
    "destination_role",
    "xform_permissions",
}


def _permission_map(model, object_ids, principal_type):
    """Return direct permission sets keyed by object and principal."""
    principal_field = "user" if principal_type == "user" else "group"
    rows = model.objects.filter(content_object_id__in=object_ids).values_list(
        "content_object_id",
        f"{principal_field}_id",
        f"{principal_field}__{'username' if principal_type == 'user' else 'name'}",
        "permission__codename",
    )
    permissions = defaultdict(dict)
    for object_id, principal_id, principal_name, codename in rows:
        principal = permissions[object_id].setdefault(
            (principal_type, principal_id),
            {"name": principal_name, "permissions": set()},
        )
        principal["permissions"].add(codename)

    return permissions


def _matching_role(destination_permissions, target_permissions):
    """Return the one role matching both direct permission sets, if any."""
    matches = []
    for role in ROLES_ORDERED:
        project_permissions = set(role.class_to_permissions.get(Project, ()))
        xform_permissions = set(role.class_to_permissions.get(XForm, ()))
        if (
            destination_permissions == project_permissions
            and target_permissions == xform_permissions
        ):
            matches.append(role)

    return matches[0] if len(matches) == 1 else None


def _cross_project_dataviews():
    """Return all cross-project DataViews, including soft-deleted rows."""
    return list(
        DataView.objects.exclude(xform__project_id=F("project_id"))
        .select_related("project", "xform__project")
        .order_by("pk")
    )


def _merge_permission_maps(target, permission_map):
    """Merge one principal type's permission map into ``target``."""
    for object_id, principals in permission_map.items():
        target.setdefault(object_id, {}).update(principals)


def _direct_permission_maps(relationships):
    """Return destination-project and source-XForm direct permission maps."""
    destination_project_ids = {project_id for project_id, _ in relationships}
    target_xform_ids = {xform_id for _, xform_id in relationships}
    destination_permissions = {}
    target_permissions = {}

    for principal_type, config in PRINCIPAL_CONFIG.items():
        project_model, xform_model = config[1:3]
        _merge_permission_maps(
            destination_permissions,
            _permission_map(project_model, destination_project_ids, principal_type),
        )
        _merge_permission_maps(
            target_permissions,
            _permission_map(xform_model, target_xform_ids, principal_type),
        )

    return destination_permissions, target_permissions


def _relationship_candidates(dataviews, destination_principals, target_principals):
    """Return candidates for one destination-project and source-XForm pair."""
    candidates = []
    shared_principals = sorted(
        set(destination_principals) & set(target_principals),
        key=lambda value: (value[0], value[1]),
    )
    for principal_key in shared_principals:
        destination = destination_principals[principal_key]
        target = target_principals[principal_key]
        role = _matching_role(destination["permissions"], target["permissions"])
        if role is None:
            continue

        principal_type, principal_id = principal_key
        candidates.append(
            {
                "dataviews": dataviews,
                "destination_project": dataviews[0].project,
                "xform": dataviews[0].xform,
                "principal_type": principal_type,
                "principal_id": principal_id,
                "principal_name": target["name"],
                "destination_role": role.name,
                "xform_permissions": sorted(target["permissions"]),
            }
        )

    return candidates


def _candidate_grants(dataviews):
    """Find conservative, deduplicated guardian grant candidates."""
    relationships = defaultdict(list)
    for dataview in dataviews:
        relationships[(dataview.project_id, dataview.xform_id)].append(dataview)

    destination_permissions, target_permissions = _direct_permission_maps(relationships)

    candidates = []
    for project_id, xform_id in sorted(relationships):
        dataviews = relationships[(project_id, xform_id)]
        candidates.extend(
            _relationship_candidates(
                dataviews,
                destination_permissions.get(project_id, {}),
                target_permissions.get(xform_id, {}),
            )
        )

    return candidates


def _dataview_report_row(dataview):
    deleted_at = dataview.deleted_at.isoformat() if dataview.deleted_at else ""
    return {
        "record_type": "dataview",
        "dataview_id": dataview.pk,
        "dataview_ids": dataview.pk,
        "dataview_name": dataview.name,
        "dataview_deleted_at": deleted_at,
        "destination_project_id": dataview.project_id,
        "destination_project_name": dataview.project.name,
        "xform_id": dataview.xform_id,
        "xform_id_string": dataview.xform.id_string,
        "xform_project_id": dataview.xform.project_id,
        "xform_project_name": dataview.xform.project.name,
        "principal_type": "",
        "principal_id": "",
        "principal_name": "",
        "destination_role": "",
        "xform_permissions": "",
    }


def _candidate_report_row(candidate):
    dataviews = candidate["dataviews"]
    destination_project = candidate["destination_project"]
    xform = candidate["xform"]
    return {
        "record_type": "candidate",
        "dataview_id": "",
        "dataview_ids": ";".join(str(item.pk) for item in dataviews),
        "dataview_name": "",
        "dataview_deleted_at": "",
        "destination_project_id": destination_project.pk,
        "destination_project_name": destination_project.name,
        "xform_id": xform.pk,
        "xform_id_string": xform.id_string,
        "xform_project_id": xform.project_id,
        "xform_project_name": xform.project.name,
        "principal_type": candidate["principal_type"],
        "principal_id": candidate["principal_id"],
        "principal_name": candidate["principal_name"],
        "destination_role": candidate["destination_role"],
        "xform_permissions": ";".join(candidate["xform_permissions"]),
    }


class Command(BaseCommand):
    """Audit cross-project DataViews and repair reviewed source grants."""

    help = gettext_lazy(
        "Report cross-project DataViews and conservative guardian grant candidates; "
        "optionally revoke only operator-reviewed direct source-XForm grants."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            help=gettext_lazy(
                "Write the deterministic CSV report to PATH instead of stdout."
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help=gettext_lazy(
                "Apply an operator-reviewed direct grant revocation file."
            ),
        )
        parser.add_argument(
            "--reviewed-revocations",
            metavar="PATH",
            help=gettext_lazy(
                "CSV candidate rows approved for direct XForm grant revocation."
            ),
        )

    @use_master
    def handle(self, *args, **options):
        apply_changes = options["apply"]
        reviewed_path = options.get("reviewed_revocations")
        if reviewed_path and not apply_changes:
            raise CommandError(_("--reviewed-revocations requires --apply"))

        reviewed_rows = self._read_reviewed_rows(reviewed_path) if reviewed_path else []
        dataviews = _cross_project_dataviews()
        candidates = _candidate_grants(dataviews)
        report_rows = [_dataview_report_row(item) for item in dataviews]
        report_rows.extend(_candidate_report_row(item) for item in candidates)
        self._write_report(report_rows, options.get("output"))

        if apply_changes:
            grants_revoked, rows_skipped = self._apply_changes(reviewed_rows)
        else:
            grants_revoked = rows_skipped = 0

        counts = (
            f"cross_project_dataviews_found={len(dataviews)} "
            f"candidates_reported={len(candidates)} "
            f"grants_revoked={grants_revoked} "
            f"rows_skipped={rows_skipped}"
        )
        output = options.get("output")
        summary_stream = self.stdout if output and output != "-" else self.stderr
        summary_stream.write(counts)

    def _apply_changes(self, reviewed_rows):
        """Atomically validate and revoke reviewed grants."""
        with transaction.atomic():
            validated_revocations = self._validate_revocations(reviewed_rows)
            grants_revoked, rows_skipped, xform_ids = self._revoke(
                validated_revocations
            )

        for xform in XForm.objects.filter(pk__in=xform_ids):
            clear_permissions_cache(xform)

        return grants_revoked, rows_skipped

    @staticmethod
    def _revoke(revocations):
        """Delete validated direct permission rows and return affected XForms."""
        grants_revoked = 0
        rows_skipped = 0
        xform_ids = set()
        for revocation in revocations:
            if revocation["already_revoked"]:
                rows_skipped += 1
                continue
            deleted, _ = (
                revocation["permission_model"]
                .objects.filter(
                    content_object_id=revocation["xform_id"],
                    permission__codename__in=revocation["permissions"],
                    **{revocation["principal_field"]: revocation["principal_id"]},
                )
                .delete()
            )
            if deleted:
                grants_revoked += 1
                xform_ids.add(revocation["xform_id"])

        return grants_revoked, rows_skipped, xform_ids

    def _write_report(self, rows, output_path):
        if output_path and output_path != "-":
            try:
                with open(output_path, "w", encoding="utf-8", newline="") as output:
                    self._write_csv(output, rows)
            except OSError as error:
                raise CommandError(
                    _("Unable to write report: %(error)s") % {"error": error}
                ) from error
            return

        self._write_csv(self.stdout, rows)

    @staticmethod
    def _write_csv(output, rows):
        writer = csv.DictWriter(output, fieldnames=REPORT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    def _read_reviewed_rows(self, path):
        try:
            with open(path, encoding="utf-8-sig", newline="") as reviewed_file:
                reader = csv.DictReader(reviewed_file)
                if reader.fieldnames is None:
                    raise CommandError(_("Reviewed revocations CSV has no header"))
                if len(reader.fieldnames) != len(set(reader.fieldnames)):
                    raise CommandError(
                        _("Reviewed revocations CSV has duplicate header fields")
                    )
                missing_fields = REVIEW_REQUIRED_FIELDS - set(reader.fieldnames)
                if missing_fields:
                    missing = ", ".join(sorted(missing_fields))
                    raise CommandError(
                        _("Reviewed revocations CSV is missing field(s): %(fields)s")
                        % {"fields": missing}
                    )

                reviewed_rows = []
                seen = set()
                for line_number, row in enumerate(reader, start=2):
                    if None in row or any(
                        value is not None and not isinstance(value, str)
                        for value in row.values()
                    ):
                        raise CommandError(
                            _(
                                "Reviewed revocations CSV is malformed on line "
                                "%(line_number)s"
                            )
                            % {"line_number": line_number}
                        )
                    if not any((value or "").strip() for value in row.values()):
                        continue
                    record_type = (row.get("record_type") or "").strip()
                    if record_type == "dataview":
                        continue
                    if record_type != "candidate":
                        raise CommandError(
                            _(
                                "Reviewed revocations CSV has invalid record_type on "
                                "line %(line_number)s"
                            )
                            % {"line_number": line_number}
                        )
                    parsed = self._parse_reviewed_row(row, line_number)
                    key = (
                        parsed["destination_project_id"],
                        parsed["xform_id"],
                        parsed["principal_type"],
                        parsed["principal_id"],
                        parsed["destination_role"],
                    )
                    if key in seen:
                        raise CommandError(
                            _(
                                "Reviewed revocations CSV has a duplicate candidate "
                                "on line %(line_number)s"
                            )
                            % {"line_number": line_number}
                        )
                    reviewed_rows.append(parsed)
                    seen.add(key)
        except OSError as error:
            raise CommandError(
                _("Unable to read reviewed revocations: %(error)s") % {"error": error}
            ) from error

        return reviewed_rows

    def _parse_reviewed_row(self, row, line_number):
        def positive_integer(field):
            try:
                value = int((row.get(field) or "").strip())
            except ValueError as error:
                raise CommandError(
                    _(
                        "Reviewed revocations CSV has invalid %(field)s on line "
                        "%(line_number)s"
                    )
                    % {"field": field, "line_number": line_number}
                ) from error
            if value <= 0:
                raise CommandError(
                    _(
                        "Reviewed revocations CSV has invalid %(field)s on line "
                        "%(line_number)s"
                    )
                    % {"field": field, "line_number": line_number}
                )
            return value

        dataview_values = (row.get("dataview_ids") or "").split(";")
        try:
            dataview_ids = tuple(int(value.strip()) for value in dataview_values)
        except ValueError as error:
            raise CommandError(
                _(
                    "Reviewed revocations CSV has invalid dataview_ids on line "
                    "%(line_number)s"
                )
                % {"line_number": line_number}
            ) from error
        if (
            not dataview_ids
            or any(value <= 0 for value in dataview_ids)
            or len(set(dataview_ids)) != len(dataview_ids)
        ):
            raise CommandError(
                _(
                    "Reviewed revocations CSV has invalid dataview_ids on line "
                    "%(line_number)s"
                )
                % {"line_number": line_number}
            )

        principal_type = (row.get("principal_type") or "").strip()
        if principal_type not in {"user", "group"}:
            raise CommandError(
                _(
                    "Reviewed revocations CSV has invalid principal_type on line "
                    "%(line_number)s"
                )
                % {"line_number": line_number}
            )

        destination_role = (row.get("destination_role") or "").strip()
        if destination_role not in ROLES:
            raise CommandError(
                _(
                    "Reviewed revocations CSV has invalid destination_role on line "
                    "%(line_number)s"
                )
                % {"line_number": line_number}
            )

        permissions = tuple(
            item.strip()
            for item in (row.get("xform_permissions") or "").split(";")
            if item.strip()
        )
        if not permissions or len(set(permissions)) != len(permissions):
            raise CommandError(
                _(
                    "Reviewed revocations CSV has invalid xform_permissions on line "
                    "%(line_number)s"
                )
                % {"line_number": line_number}
            )

        principal_name = (row.get("principal_name") or "").strip()
        if not principal_name:
            raise CommandError(
                _(
                    "Reviewed revocations CSV has no principal_name on line "
                    "%(line_number)s"
                )
                % {"line_number": line_number}
            )

        return {
            "line_number": line_number,
            "dataview_ids": dataview_ids,
            "destination_project_id": positive_integer("destination_project_id"),
            "xform_id": positive_integer("xform_id"),
            "xform_project_id": positive_integer("xform_project_id"),
            "principal_type": principal_type,
            "principal_id": positive_integer("principal_id"),
            "principal_name": principal_name,
            "destination_role": destination_role,
            "xform_permissions": permissions,
        }

    def _validate_revocations(self, reviewed_rows):
        return [self._validate_revocation(row) for row in reviewed_rows]

    def _validate_revocation(self, row):
        """Revalidate one operator-approved candidate under database locks."""
        role = ROLES[row["destination_role"]]
        project_permissions = set(role.class_to_permissions.get(Project, ()))
        xform_permissions = set(role.class_to_permissions.get(XForm, ()))
        if set(row["xform_permissions"]) != xform_permissions:
            self._raise_stale(
                row["line_number"], _("reported XForm permissions changed")
            )

        self._validate_xform(row)
        self._validate_dataviews(row)
        config = PRINCIPAL_CONFIG[row["principal_type"]]
        self._validate_principal(row, config)
        self._validate_permission_set(
            row,
            (config[1], row["destination_project_id"], config[3]),
            project_permissions,
            _("destination-project role changed"),
        )
        target_permissions = self._validate_permission_set(
            row,
            (config[2], row["xform_id"], config[3]),
            xform_permissions,
            _("target-XForm permissions changed"),
            allow_empty=True,
        )

        return {
            "permission_model": config[2],
            "principal_field": config[3],
            "principal_id": row["principal_id"],
            "xform_id": row["xform_id"],
            "permissions": xform_permissions,
            "already_revoked": not target_permissions,
        }

    def _validate_xform(self, row):
        try:
            xform = XForm.objects.select_for_update().get(pk=row["xform_id"])
        except XForm.DoesNotExist:
            self._raise_stale(row["line_number"], _("XForm no longer exists"))
        if xform.project_id != row["xform_project_id"]:
            self._raise_stale(row["line_number"], _("XForm project changed"))
        if xform.project_id == row["destination_project_id"]:
            self._raise_stale(row["line_number"], _("XForm is no longer cross-project"))

    def _validate_dataviews(self, row):
        dataviews = list(
            DataView.objects.select_for_update()
            .filter(pk__in=row["dataview_ids"])
            .select_related("xform")
        )
        if len(dataviews) != len(row["dataview_ids"]):
            self._raise_stale(row["line_number"], _("DataView no longer exists"))
        for dataview in dataviews:
            if (
                dataview.project_id != row["destination_project_id"]
                or dataview.xform_id != row["xform_id"]
                or dataview.xform.project_id == dataview.project_id
            ):
                self._raise_stale(
                    row["line_number"], _("DataView relationship changed")
                )

    def _validate_principal(self, row, config):
        principal_model, _, _, _, name_field = config
        try:
            principal = principal_model.objects.get(pk=row["principal_id"])
        except principal_model.DoesNotExist:
            self._raise_stale(row["line_number"], _("principal no longer exists"))
        if getattr(principal, name_field) != row["principal_name"]:
            self._raise_stale(row["line_number"], _("principal name changed"))

    def _validate_permission_set(
        self, row, permission_spec, expected, reason, allow_empty=False
    ):
        permission_model, object_id, principal_field = permission_spec
        permissions = set(
            permission_model.objects.select_for_update()
            .filter(
                content_object_id=object_id,
                **{principal_field: row["principal_id"]},
            )
            .values_list("permission__codename", flat=True)
        )
        if permissions != expected and not (allow_empty and not permissions):
            self._raise_stale(row["line_number"], reason)
        return permissions

    @staticmethod
    def _raise_stale(line_number, reason):
        raise CommandError(
            _(
                "Reviewed revocations CSV is stale on line %(line_number)s: "
                "%(reason)s"
            )
            % {"line_number": line_number, "reason": reason}
        )
