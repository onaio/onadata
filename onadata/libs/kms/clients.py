from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from valigetta.exceptions import InvalidAPIURLException
from valigetta.kms import APIKMSClient as BaseAPIClient
from valigetta.kms import AWSKMSClient as BaseAWSClient

from onadata.libs.utils.cache_tools import (
    KMS_TOKEN_CACHE_KEY,
    KMS_TOKEN_CACHE_TTL,
    safe_cache_get,
    safe_cache_set,
)

# pylint: disable=too-few-public-methods


def setting(name, default=None):
    """
    Helper function to get a Django setting by name. If setting doesn't exists
    it will return a default.

    :param name: Name of setting
    :type name: str
    :param default: Value if setting is unfound
    :returns: Setting's value
    """
    return getattr(settings, name, default)


class AWSKMSClient(BaseAWSClient):
    def __init__(self):
        super().__init__(
            aws_access_key_id=setting(
                "AWS_KMS_ACCESS_KEY_ID", setting("AWS_ACCESS_KEY_ID")
            ),
            aws_secret_access_key=setting(
                "AWS_KMS_SECRET_ACCESS_KEY", setting("AWS_SECRET_ACCESS_KEY")
            ),
            region_name=setting("AWS_KMS_REGION_NAME"),
        )


class APIKMSClient(BaseAPIClient):
    def __init__(self):
        try:
            super().__init__(
                client_id=setting("KMS_API_CLIENT_ID"),
                client_secret=setting("KMS_API_CLIENT_SECRET"),
                urls=setting("KMS_API_URLS"),
                token=self.get_token_from_cache(),
                on_token_refresh=self.save_token_to_cache,
            )
        except InvalidAPIURLException as exc:
            raise ImproperlyConfigured(
                f"Invalid setting 'KMS_API_URLS' for {self.__class__.__name__}", exc
            ) from exc

    @classmethod
    def save_token_to_cache(cls, token: dict[str, str]) -> None:
        safe_cache_set(KMS_TOKEN_CACHE_KEY, token, KMS_TOKEN_CACHE_TTL)

    @classmethod
    def get_token_from_cache(cls) -> dict[str, str] | None:
        return safe_cache_get(KMS_TOKEN_CACHE_KEY)
