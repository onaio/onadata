from django.conf import settings
from django.template.loader import render_to_string
from future.moves.urllib.parse import urlencode
from rest_framework.reverse import reverse


def get_verification_url(redirect_url, request, verification_key):
    verification_url = getattr(settings, "VERIFICATION_URL", None)
    url = verification_url or reverse(
        'userprofile-verify-email', request=request
    )
    query_params_dict = {'verification_key': verification_key}
    redirect_url and query_params_dict.update({
        'redirect_url': redirect_url
    })
    query_params_string = urlencode(query_params_dict)
    verification_url = '{}?{}'.format(url, query_params_string)

    return verification_url


def get_verification_email_data(email, username, verification_url, request):
    email_data = {'email': email}

    ctx_dict = {
        'username': username,
        'expiration_days': getattr(settings, "ACCOUNT_ACTIVATION_DAYS", 1),
        'verification_url': verification_url
    }

    key_template_path_dict = {
        'subject': 'registration/verification_email_subject.txt',
        'message_txt': 'registration/verification_email.txt'
    }
    for key, template_path in key_template_path_dict.items():
        email_data.update({
            key: render_to_string(
                template_path,
                ctx_dict,
                request=request
            )
        })

    return email_data


def get_account_lockout_email_data(username, end=False):
    """Generates both the email upon start and end of account lockout"""
    message_path = 'account_lockout/lockout_start.txt'
    subject_path = 'account_lockout/lockout_email_subject.txt'
    if end:
        message_path = 'account_lockout/lockout_end.txt'
    ctx_dict = {
        'username': username,
        'lockout_time': getattr(settings, 'LOCKOUT_TIME', 1800) / 60,
        'support_email': getattr(
            settings, 'SUPPORT_EMAIL', 'support@example.com')
    }

    email_data = {
        'subject': render_to_string(subject_path),
        'message_txt': render_to_string(message_path, ctx_dict)
    }

    return email_data
