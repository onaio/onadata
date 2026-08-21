# -*- coding: utf-8 -*-
"""Complete a step-up against an external identity provider.

The protocol lives in ona-oidc (``oidc.stepup``), and completing a step-up in
``StepUpViewSet`` via its callback mixin. What remains here is the one thing
that is OnaData's alone: what a step-up is *for*, carried across the redirect
because the provider returns to a URL rather than to the control the user
clicked.
"""

from typing import Tuple

from oidc.stepup import build_step_up_url


def start_step_up(auth_server: str, audience: str, user) -> Tuple[str, str]:
    """Build the authorize URL that will prove a second factor.

    Returns ``(url, state)``. The audience and the user ride along in the
    state because the provider redirects back to a URL, not to the control the
    user clicked.
    """
    return build_step_up_url(
        auth_server, context={"audience": audience, "user_pk": user.pk}
    )
