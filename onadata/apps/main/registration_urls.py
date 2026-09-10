"""
URLConf for Django user registration and authentication.

Recommended usage is a call to ``include()`` in your project's root
URLConf to include this URLConf for any URL beginning with
``/accounts/``.

"""

from django.contrib.auth.views import PasswordResetView
from django.urls import include, path, re_path, reverse_lazy
from django.views.generic import RedirectView, TemplateView

from registration.backends.default.views import ActivationView

from onadata.apps.main.forms import (
    AccountPasswordResetForm,
    RegistrationFormUserProfile,
)
from onadata.apps.main.registration_views import (
    FHRegistrationView,
    TokenRotatingPasswordResetConfirmView,
)

urlpatterns = [
    path(
        "activate/complete/",
        TemplateView.as_view(template_name="registration/activation_complete.html"),
        name="registration_activation_complete",
    ),
    # Activation keys get matched by \w+ instead of the more specific
    # [a-fA-F0-9]{40} because a bad activation key should still get to the view
    # that way it can return a sensible "invalid key" message instead of a
    # confusing 404.
    re_path(
        r"^activate/(?P<activation_key>\w+)/$",
        ActivationView.as_view(),
        name="registration_activate",
    ),
    path(
        "register/",
        FHRegistrationView.as_view(form_class=RegistrationFormUserProfile),
        name="registration_register",
    ),
    path(
        "register/complete/",
        TemplateView.as_view(template_name="registration/registration_complete.html"),
        name="registration_complete",
    ),
    # Redirect only, never a session: rendering a login form here would be a
    # password-only bypass of the second factor. The name is kept so existing
    # reverse("auth_login") call sites still resolve. Declared first so it
    # takes precedence over the ``login/`` route in ``registration.auth_urls``.
    path(
        "login/",
        RedirectView.as_view(pattern_name="two_factor:login", query_string=True),
        name="auth_login",
    ),
    # Override the reset-request view (also defined in registration.auth_urls
    # below) with a form that rate-limits reset emails per address and skips
    # organization accounts. Declared first so it takes precedence over the
    # include's route.
    path(
        "password/reset/",
        PasswordResetView.as_view(
            form_class=AccountPasswordResetForm,
            success_url=reverse_lazy("auth_password_reset_done"),
        ),
        name="auth_password_reset",
    ),
    # Override the reset-confirm view (also defined in registration.auth_urls
    # below) so a successful password reset also rotates the user's API/temp
    # tokens. Declared first so it takes precedence over the include's route.
    path(
        "password/reset/confirm/<uidb64>/<token>/",
        TokenRotatingPasswordResetConfirmView.as_view(
            success_url=reverse_lazy("auth_password_reset_complete")
        ),
        name="auth_password_reset_confirm",
    ),
    re_path(r"", include("registration.auth_urls")),
]
