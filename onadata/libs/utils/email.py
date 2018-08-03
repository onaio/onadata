from django.conf import settings
from django.template.loader import render_to_string
from rest_framework.reverse import reverse


def get_verification_email_data(
        email, username, verification_key, verification_url, request
    ):
    email_data = {'email': email}

    url = verification_url or reverse('userprofile-verify-email',
                                      request=request)
    verification_url = '{}?verification_key={}'.format(
        url, verification_key
    )
    ctx_dict = {
        'username': username,
        'expiration_days': settings.ACCOUNT_ACTIVATION_DAYS,
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
