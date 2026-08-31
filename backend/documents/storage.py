from dataclasses import dataclass

from django.core.exceptions import ValidationError

from integrations.models import StorageProvider
from integrations.services import _storage_client


class DocumentStorageUnavailable(Exception):
    pass


@dataclass
class StoredObject:
    body: object
    content_length: int
    content_type: str


class S3DocumentStorage:
    def __init__(self, provider):
        self.provider = provider

    def put(self, key, stream, content_type, metadata):
        try:
            client = _storage_client(self.provider)
            client.upload_fileobj(
                stream,
                self.provider.bucket,
                key,
                ExtraArgs={"ContentType": content_type, "Metadata": metadata},
            )
        except Exception as error:
            raise DocumentStorageUnavailable("Private file storage is unavailable.") from error

    def open_stream(self, key):
        try:
            result = _storage_client(self.provider).get_object(
                Bucket=self.provider.bucket,
                Key=key,
            )
            return StoredObject(
                body=result["Body"],
                content_length=int(result.get("ContentLength", 0)),
                content_type=result.get("ContentType", "application/octet-stream"),
            )
        except Exception as error:
            raise DocumentStorageUnavailable("File is temporarily unavailable.") from error

    def exists(self, key):
        try:
            _storage_client(self.provider).head_object(Bucket=self.provider.bucket, Key=key)
            return True
        except Exception:
            return False

    def delete(self, key):
        try:
            _storage_client(self.provider).delete_object(Bucket=self.provider.bucket, Key=key)
        except Exception as error:
            raise DocumentStorageUnavailable("Storage cleanup failed.") from error


def default_storage_provider():
    provider = StorageProvider.objects.filter(is_active=True, is_default=True).first()
    if not provider or not provider.credentials_configured:
        raise DocumentStorageUnavailable("Private file storage has not been configured.")
    return provider


def get_storage_backend(provider):
    if not provider:
        raise DocumentStorageUnavailable("Private file storage has not been configured.")
    return S3DocumentStorage(provider)


def storage_status():
    provider = StorageProvider.objects.filter(is_active=True, is_default=True).first()
    return {
        "configured": bool(provider and provider.credentials_configured),
        "provider_status": provider.connection_status if provider else "not_configured",
    }


def ensure_storage_key(key):
    if not key or key.startswith(("/", "\\")) or ".." in key.split("/") or "\\" in key:
        raise ValidationError("Invalid server storage key.")
