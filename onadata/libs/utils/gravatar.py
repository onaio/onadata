import hashlib
from future.moves.urllib.parse import urlencode
from future.moves.urllib.request import urlopen

DEFAULT_GRAVATAR = "https://ona.io/static/images/default_avatar.png"
GRAVATAR_ENDPOINT = "https://secure.gravatar.com/avatar/"
GRAVATAR_SIZE = str(60)


def email_md5(user):
    return hashlib.md5(user.email.lower().encode('utf-8')).hexdigest()


def get_gravatar_img_link(user):
    return GRAVATAR_ENDPOINT + email_md5(user) + "?" + urlencode({
        'd': DEFAULT_GRAVATAR, 's': str(GRAVATAR_SIZE)})


def gravatar_exists(user):
    url = GRAVATAR_ENDPOINT + email_md5(user) + "?" + "d=404"
    return urlopen(url).getcode() != 404
