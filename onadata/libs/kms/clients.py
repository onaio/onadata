from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from valigetta.exceptions import InvalidAPIURLException
from valigetta.kms import APIKMSClient as BaseAPIClient
from valigetta.kms import AWSKMSClient as BaseAWSClient


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


# pylint: disable=too-few-public-methods
class BaseClient:
    def __init__(self, **custom_settings):
        default_settings = self.get_default_settings()

        for name, value in default_settings.items():
            if not hasattr(self, name):
                setattr(self, name, value)

        for name, value in custom_settings.items():
            if name not in default_settings:
                raise ImproperlyConfigured(
                    f"Invalid setting '{name}' for {self.__class__.__name__}"
                )
            setattr(self, name, value)

    def get_default_settings(self):
        return {}


class AWSKMSClient(BaseClient, BaseAWSClient):
    def __init__(self, **custom_settings):
        BaseClient.__init__(self, **custom_settings)
        BaseAWSClient.__init__(
            self,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name,
        )

    def get_default_settings(self):
        return {
            "aws_access_key_id": setting(
                "AWS_KMS_ACCESS_KEY_ID", setting("AWS_ACCESS_KEY_ID")
            ),
            "aws_secret_access_key": setting(
                "AWS_KMS_SECRET_ACCESS_KEY", setting("AWS_SECRET_ACCESS_KEY")
            ),
            "region_name": setting("AWS_KMS_REGION_NAME"),
        }


class APIKMSClient(BaseClient, BaseAPIClient):
    def __init__(self, **custom_settings):
        BaseClient.__init__(self, **custom_settings)

        try:
            BaseAPIClient.__init__(
                self,
                client_id=self.client_id,
                client_secret=self.client_secret,
                urls=self.urls,
            )
        except InvalidAPIURLException as exc:
            raise ImproperlyConfigured(
                f"Invalid setting 'KMS_API_URLS' for {self.__class__.__name__}", exc
            ) from exc

    def get_default_settings(self):
        return {
            "client_id": setting("KMS_API_CLIENT_ID"),
            "client_secret": setting("KMS_API_CLIENT_SECRET"),
            "urls": setting("KMS_API_URLS"),
        }
