from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_der_public_key
from valigetta.kms import AWSKMSClient as ValigettaAWSClient


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


class BaseKMSClient:
    def __init__(self, **settings):
        default_settings = self.get_default_settings()

        for name, value in default_settings.items():
            if not hasattr(self, name):
                setattr(self, name, value)

        for name, value in settings.items():
            if name not in default_settings:
                raise ImproperlyConfigured(
                    "Invalid setting '{}' for {}".format(
                        name,
                        self.__class__.__name__,
                    )
                )
            setattr(self, name, value)

    def get_default_settings(self):
        return {}


class AWSKMSClient(BaseKMSClient, ValigettaAWSClient):
    def __init__(self, **settings):
        BaseKMSClient.__init__(self, **settings)
        ValigettaAWSClient.__init__(
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

    def create_key(self, description: str) -> dict[str, str]:
        """Creates a KMS key in AWS.

        :param description: Key description
        :type description: str
        :return: Metadata of the key created
        :rtype: dict
        """
        metadata = super().create_key(description)
        key_id = metadata["KeyId"]
        der_encoded_public_key = self.get_public_key(key_id)
        public_key_obj = load_der_public_key(der_encoded_public_key)
        pem_encoded_public_key = public_key_obj.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        return {
            "key_id": key_id,
            "public_key": pem_encoded_public_key.strip(),
        }
