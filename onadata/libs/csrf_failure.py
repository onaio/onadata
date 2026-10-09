"""
Graceful CSRF-failure handler.

A CSRF failure on the login page is almost always a stale or rotated token
(an old tab, the back button, or the cookie rotating between page render and
submit) rather than a genuine attack. Django's default response is a dead-end
403 page, which strands the user. This handler instead sends a failed *login*
POST back to a fresh login page so a new CSRF token is issued and the user can
simply try again — preserving a safe ``next`` so a brokered OIDC login flow
continues to its destination. CSRF failures on any other path keep Django's
default behavior, so genuine cross-site POSTs to the API are not masked.
"""
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.csrf import CSRF_FAILURE_TEMPLATE_NAME
from django.views.csrf import csrf_failure as default_csrf_failure


def _login_path() -> str:
    return getattr(settings, "LOGIN_URL", "/accounts/login/")


def csrf_failure(
    request, reason: str = "", template_name: str = CSRF_FAILURE_TEMPLATE_NAME
) -> HttpResponse:
    """Redirect a failed login POST back to a fresh login; else default 403."""
    login_path = _login_path()
    if request.path == login_path:
        next_url = request.POST.get(REDIRECT_FIELD_NAME) or request.GET.get(
            REDIRECT_FIELD_NAME
        )
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return HttpResponseRedirect(
                f"{login_path}?{urlencode({REDIRECT_FIELD_NAME: next_url})}"
            )
        return HttpResponseRedirect(login_path)
    return default_csrf_failure(request, reason=reason, template_name=template_name)
