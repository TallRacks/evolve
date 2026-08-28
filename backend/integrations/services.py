import os
import secrets
import smtplib
import ssl
from email.message import EmailMessage

import boto3
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import ConnectionState
from .validation import validate_storage_endpoint


def _safe_error(error):
    return f"Connection failed ({error.__class__.__name__})."


def _smtp(connector):
    password = os.environ.get(connector.secret_reference)
    if not password:
        raise ValidationError("Connector credentials are not configured on the server.")
    client = (
        smtplib.SMTP_SSL(
            connector.host, connector.port, timeout=10, context=ssl.create_default_context()
        )
        if connector.use_ssl
        else smtplib.SMTP(connector.host, connector.port, timeout=10)
    )
    if connector.use_tls:
        client.starttls(context=ssl.create_default_context())
    if connector.username:
        client.login(connector.username, password)
    return client


def test_email_connector(connector):
    try:
        with _smtp(connector) as client:
            client.noop()
    except Exception as error:
        connector.connection_status = ConnectionState.FAILED
        connector.last_test_message = _safe_error(error)
        connector.last_tested_at = timezone.now()
        connector.save(
            update_fields=("connection_status", "last_test_message", "last_tested_at", "updated_at")
        )
        raise ValidationError("Email connection test failed.") from error
    connector.connection_status = ConnectionState.HEALTHY
    connector.last_test_message = "SMTP authentication and connection succeeded."
    connector.last_tested_at = timezone.now()
    connector.save(
        update_fields=("connection_status", "last_test_message", "last_tested_at", "updated_at")
    )


def send_test_email(connector, recipient):
    message = EmailMessage()
    message["From"] = f"{connector.from_name} <{connector.from_email}>"
    message["To"] = recipient
    message["Subject"] = "Evolve email connector test"
    if connector.reply_to_email:
        message["Reply-To"] = connector.reply_to_email
    message.set_content("This message confirms an explicit Evolve email connector test.")
    try:
        with _smtp(connector) as client:
            client.send_message(message)
    except ValidationError:
        raise
    except Exception as error:
        raise ValidationError("Test email delivery failed.") from error


def _storage_client(provider):
    validate_storage_endpoint(provider.endpoint, resolve=True)
    access = os.environ.get(provider.access_key_reference)
    secret = os.environ.get(provider.secret_key_reference)
    if not access or not secret:
        raise ValidationError("Storage credentials are not configured on the server.")
    return boto3.client(
        "s3",
        endpoint_url=provider.endpoint,
        region_name=provider.region,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        use_ssl=provider.use_ssl,
    )


def test_storage_provider(provider):
    prefix = provider.path_prefix.strip("/")
    key = "/".join(filter(None, (prefix, "evolve-connectivity-tests", secrets.token_hex(16))))
    body = b"evolve-storage-test"
    client = None
    written = False
    try:
        client = _storage_client(provider)
        client.put_object(Bucket=provider.bucket, Key=key, Body=body, ContentType="text/plain")
        written = True
        result = client.get_object(Bucket=provider.bucket, Key=key)["Body"].read()
        if result != body:
            raise ValidationError("Storage read verification failed.")
        client.delete_object(Bucket=provider.bucket, Key=key)
        written = False
    except Exception as error:
        if written and client:
            try:
                client.delete_object(Bucket=provider.bucket, Key=key)
            except Exception:
                pass
        provider.connection_status = ConnectionState.FAILED
        provider.last_test_message = _safe_error(error)
        provider.last_tested_at = timezone.now()
        provider.save(
            update_fields=("connection_status", "last_test_message", "last_tested_at", "updated_at")
        )
        raise ValidationError("Storage configuration test failed.") from error
    provider.connection_status = ConnectionState.HEALTHY
    provider.last_test_message = "Write, read, and delete probe succeeded."
    provider.last_tested_at = timezone.now()
    provider.save(
        update_fields=("connection_status", "last_test_message", "last_tested_at", "updated_at")
    )
