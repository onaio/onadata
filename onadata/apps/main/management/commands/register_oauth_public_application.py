# -*- coding: utf-8 -*-
"""Register a public Authorization Code OAuth application safely."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from oauth2_provider.models import get_application_model

from onadata.libs.authentication import is_pkce_s256_enforced


class Command(BaseCommand):
    """Create or verify a public OAuth application with a disabled owner."""

    help = (
        "Register or verify a public Authorization Code OAuth application "
        "whose effective policy requires PKCE S256."
    )

    def add_arguments(self, parser):
        parser.add_argument("--client-id", required=True)
        parser.add_argument("--owner-username", required=True)
        parser.add_argument("--application-name", required=True)
        parser.add_argument(
            "--redirect-uri",
            action="append",
            required=True,
            dest="redirect_uris",
            help="Approved callback URI. Repeat for every approved URI.",
        )

    def handle(self, *args, **options):
        client_id = self._required_text(options["client_id"], "client ID")
        owner_username = self._required_text(
            options["owner_username"], "owner username"
        )
        application_name = self._required_text(
            options["application_name"], "application name"
        )
        redirect_uris = self._validate_redirect_uris(options["redirect_uris"])

        application_model = get_application_model()
        candidate = application_model(
            client_id=client_id,
            client_type=application_model.CLIENT_PUBLIC,
            authorization_grant_type=application_model.GRANT_AUTHORIZATION_CODE,
        )
        if not is_pkce_s256_enforced(candidate):
            raise CommandError(
                "PKCE S256 is not effective for the requested OAuth application."
            )

        try:
            with transaction.atomic():
                result = self._register_or_verify(
                    client_id=client_id,
                    owner_username=owner_username,
                    application_name=application_name,
                    redirect_uris=redirect_uris,
                )
        except (IntegrityError, ValidationError) as exc:
            raise CommandError(
                "The OAuth application registration is invalid or conflicts "
                "with an existing record."
            ) from exc

        if options["verbosity"] > 0:
            self.stdout.write(self.style.SUCCESS(f"{result} OAuth registration."))

    def _register_or_verify(
        self,
        *,
        client_id,
        owner_username,
        application_name,
        redirect_uris,
    ):
        application_model = get_application_model()
        users = list(
            get_user_model()
            .objects.select_for_update()
            .filter(username=owner_username)[:2]
        )
        if len(users) > 1:
            raise CommandError("The OAuth application owner is ambiguous.")
        owner = users[0] if users else None

        applications = list(
            application_model.objects.select_for_update().filter(client_id=client_id)[
                :2
            ]
        )
        if len(applications) > 1:
            raise CommandError("The OAuth application is ambiguous.")
        application = applications[0] if applications else None

        if application is not None:
            if owner is None or application.user_id != owner.pk:
                raise CommandError("The OAuth client ID belongs to a different owner.")
            self._validate_owner(owner, application_model, application)
            self._validate_application(
                application,
                owner,
                application_name,
                redirect_uris,
            )
            if not is_pkce_s256_enforced(application):
                raise CommandError(
                    "PKCE S256 is not effective for the existing OAuth application."
                )
            return "Verified"

        if owner is None:
            owner = self._create_owner(owner_username)
        else:
            self._validate_owner(owner, application_model)

        application = application_model(
            user=owner,
            name=application_name,
            client_id=client_id,
            client_type=application_model.CLIENT_PUBLIC,
            authorization_grant_type=application_model.GRANT_AUTHORIZATION_CODE,
            redirect_uris=" ".join(redirect_uris),
            skip_authorization=False,
            algorithm=application_model.NO_ALGORITHM,
        )
        application.full_clean()
        application.save()

        if not is_pkce_s256_enforced(application):
            raise CommandError(
                "PKCE S256 is not effective for the created OAuth application."
            )
        return "Created"

    @staticmethod
    def _required_text(value, label):
        if not isinstance(value, str) or not value.strip():
            raise CommandError(f"The {label} must not be empty.")
        return value.strip()

    @classmethod
    def _validate_redirect_uris(cls, values):
        redirect_uris = [cls._required_text(value, "redirect URI") for value in values]
        if len(redirect_uris) != len(set(redirect_uris)):
            raise CommandError("Redirect URIs must not be repeated.")
        if any(any(character.isspace() for character in uri) for uri in redirect_uris):
            raise CommandError("A redirect URI must not contain whitespace.")
        return redirect_uris

    @staticmethod
    def _create_owner(username):
        user_model = get_user_model()
        owner = user_model(username=username, is_active=False)
        owner.set_unusable_password()
        owner.is_staff = False
        owner.is_superuser = False
        owner.full_clean()
        owner.save()
        # User-creation signals in this project assign default permissions.
        # A dedicated OAuth owner must retain none of them.
        owner.groups.clear()
        owner.user_permissions.clear()
        return owner

    @staticmethod
    def _validate_owner(owner, application_model, target_application=None):
        if owner.is_active or owner.has_usable_password():
            raise CommandError("The existing OAuth application owner can sign in.")
        if owner.is_staff or owner.is_superuser:
            raise CommandError(
                "The existing OAuth application owner has elevated privileges."
            )
        if owner.groups.exists() or owner.user_permissions.exists():
            raise CommandError(
                "The existing OAuth application owner has assigned privileges."
            )

        owned_applications = application_model.objects.filter(user=owner)
        if target_application is not None:
            owned_applications = owned_applications.exclude(pk=target_application.pk)
        if owned_applications.exists():
            raise CommandError(
                "The existing owner owns an unrelated OAuth application."
            )

    @staticmethod
    def _validate_application(
        application,
        owner,
        application_name,
        redirect_uris,
    ):
        application_model = type(application)
        if application.user_id != owner.pk:
            raise CommandError("The OAuth client ID belongs to a different owner.")
        if application.client_type != application_model.CLIENT_PUBLIC:
            raise CommandError("The existing OAuth application is not public.")
        if (
            application.authorization_grant_type
            != application_model.GRANT_AUTHORIZATION_CODE
        ):
            raise CommandError(
                "The existing OAuth application is not an Authorization Code client."
            )
        if application.name != application_name:
            raise CommandError("The existing OAuth application name is unexpected.")
        if set(application.redirect_uris.split()) != set(redirect_uris):
            raise CommandError(
                "The existing OAuth application callback URL set is unexpected."
            )
        if application.skip_authorization:
            raise CommandError(
                "The existing OAuth application skips user authorization."
            )
        if application.algorithm != application_model.NO_ALGORITHM:
            raise CommandError(
                "The existing OAuth application has an OIDC signing algorithm."
            )
