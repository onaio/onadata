# -*- coding: utf-8 -*-
"""Whether an organisation owning what a gated action touches requires
two-factor for it."""

from onadata.libs.stepup.policy import ORG_SCOPED_ACTIONS, requires_two_factor


def _owner_ids(owners) -> set:
    """The primary keys of ``owners``, User accounts or their primary keys."""
    ids = (getattr(owner, "pk", owner) for owner in owners)
    return {owner_id for owner_id in ids if owner_id is not None}


def requiring_organization(owners, actions):
    """The username of an organisation among ``owners`` whose
    ``two_factor_required_actions`` covers any of ``actions``, an action name
    or several, or None.

    ``owners`` is read only for an organisation-scoped action, so a lazy
    iterable costs nothing elsewhere. Owners that are not organisations are
    skipped. One query covers every owner.
    """
    scoped = ORG_SCOPED_ACTIONS.intersection(
        (actions,) if isinstance(actions, str) else actions
    )
    if not scoped:
        return None
    owner_ids = _owner_ids(owners)
    if not owner_ids:
        return None
    # pylint: disable=import-outside-toplevel
    from onadata.apps.api.models.organization_profile import OrganizationProfile

    requirements = OrganizationProfile.objects.filter(
        user_id__in=owner_ids
    ).values_list("user__username", "two_factor_required_actions")
    return next(
        (
            username
            for username, required in requirements
            if any(requires_two_factor(required, action) for action in scoped)
        ),
        None,
    )
