"""URLConf for the two-factor login wizard.

Only login is served. The package's management pages accept ``otp_required``,
which the remember cookie satisfies with no code entered, and SetupView enrols
a confirmed device with no recovery codes whatever ``ENABLE_TWO_FACTOR`` says.
/api/v1/totp/* covers all of it and demands a current code.

Declared rather than filtered from ``two_factor.urls``, so a route the package
adds later is not served until someone decides it should be, and so
/account/login/ does not move if the package moves it.
"""

from django.urls import path

from onadata.apps.main.two_factor_views import LockoutLoginView

urlpatterns = (
    [path("account/login/", LockoutLoginView.as_view(), name="login")],
    "two_factor",
)
