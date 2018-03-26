from functools import wraps
from future.moves.urllib.parse import urlparse

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.utils.decorators import available_attrs
from django.conf import settings
from django.http import HttpResponseRedirect


def check_obj(f):
    @wraps(f)
    def with_check_obj(*args, **kwargs):
        if args[0]:
            return f(*args, **kwargs)

    return with_check_obj


def is_owner(view_func):
    @wraps(view_func, assigned=available_attrs(view_func))
    def _wrapped_view(request, *args, **kwargs):
        # assume username is first arg
        if request.user.is_authenticated():
            if request.user.username == kwargs['username']:
                return view_func(request, *args, **kwargs)
            protocol = "https" if request.is_secure() else "http"
            return HttpResponseRedirect("%s://%s" % (protocol,
                                                     request.get_host()))
        path = request.build_absolute_uri()
        login_url = request.build_absolute_uri(settings.LOGIN_URL)
        # If the login url is the same scheme and net location then just
        # use the path as the "next" url.
        login_scheme, login_netloc = urlparse(login_url)[:2]
        current_scheme, current_netloc = urlparse(path)[:2]
        if ((not login_scheme or login_scheme == current_scheme) and
                (not login_netloc or login_netloc == current_netloc)):
            path = request.get_full_path()
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(path, None, REDIRECT_FIELD_NAME)
    return _wrapped_view
