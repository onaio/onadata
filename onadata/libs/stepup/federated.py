# -*- coding: utf-8 -*-
"""Start a step-up against an external identity provider.

ona-oidc owns the protocol in ``oidc.stepup``. This module sets what OnaData
carries across the redirect.
"""

from oidc.stepup import build_step_up_url


def start_step_up(auth_server: str, audience: str, user) -> tuple[str, str]:
    """Build the authorize URL that will prove a second factor.

    Returns ``(url, state)``. The state carries the audience and the user,
    because the callback has no other way to learn them.
    """
    return build_step_up_url(
        auth_server, context={"audience": audience, "user_pk": user.pk}
    )
