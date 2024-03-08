# -*- coding: utf-8 -*-
"""Gravatar utils module"""
import hashlib

from six.moves.urllib.parse import urlencode

import requests


DEFAULT_GRAVATAR = "https://ona.io/static/images/default_avatar.png"
GRAVATAR_ENDPOINT = "https://secure.gravatar.com/avatar/"
GRAVATAR_SIZE = str(60)


def email_sha256(user):
    """Returns the hash of an email for the user"""
    return hashlib.new(
        "sha256", user.email.lower().encode("utf-8"), usedforsecurity=False
    ).hexdigest()


def get_gravatar_img_link(user):
    """Returns the Gravatar image URL"""
    return (
        GRAVATAR_ENDPOINT
        + email_sha256(user)
        + "?"
        + urlencode({"d": DEFAULT_GRAVATAR, "s": str(GRAVATAR_SIZE)})
    )


def gravatar_exists(user):
    """Checks if the Gravatar URL exists"""
    url = GRAVATAR_ENDPOINT + email_sha256(user) + "?" + "d=404"
    return requests.get(url).status_code != 404
