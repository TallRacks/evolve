import json
import imaplib
import os
import secrets
import smtplib
import ssl
import urllib.request
import urllib.parse
from email.message import EmailMessage

import base64
import boto3
from botocore.config import Config
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import ConnectionState, GoogleWorkspaceConnector, SecretBackend
from .validation import validate_storage_endpoint


def _reference_parts(reference):
    value, separator, key = reference.partition("#")
    return value, key or "value"


def resolve_secret(backend, reference):
    if not reference:
        return ""
    if backend == SecretBackend.ENVIRONMENT:
        return os.environ.get(reference, "")
    if backend == SecretBackend.AWS_SECRETS_MANAGER:
        secret_id, key = _reference_parts(reference)
        client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION") or None)
        payload = client.get_secret_value(SecretId=secret_id).get("SecretString", "")
        try:
            data = json.loads(payload)
        except (TypeError, ValueError):
            return payload if key == "value" else ""
        return str(data.get(key, "")) if isinstance(data, dict) else ""
    if backend == SecretBackend.VAULT:
        address = os.environ.get("EVOLVE_VAULT_ADDR", "").rstrip("/")
        token = os.environ.get("EVOLVE_VAULT_TOKEN", "")
        if not address or not token:
            return ""
        path, key = _reference_parts(reference)
        request = urllib.request.Request(f"{address}/v1/{path}", headers={"X-Vault-Token": token})
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        data = data.get("data", data) if isinstance(data, dict) else {}
        return str(data.get(key, "")) if isinstance(data, dict) else ""
    raise ValidationError("Unsupported secret backend.")



def store_secret(backend, reference, value):
    """Store a secret externally; never persist the secret in Evolve."""
    if not reference or not value:
        raise ValidationError("A destination secret reference is required.")
    if backend == SecretBackend.ENVIRONMENT:
        raise ValidationError("Environment references must be provisioned on the server; OAuth cannot write the env file.")
    path, key = _reference_parts(reference)
    if backend == SecretBackend.AWS_SECRETS_MANAGER:
        secret_id = path
        client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION") or None)
        current = client.get_secret_value(SecretId=secret_id).get("SecretString", "")
        try:
            payload = json.loads(current) if current else {}
        except (TypeError, ValueError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload[key] = value
        client.put_secret_value(SecretId=secret_id, SecretString=json.dumps(payload))
        return
    if backend == SecretBackend.VAULT:
        address = os.environ.get("EVOLVE_VAULT_ADDR", "").rstrip("/")
        token = os.environ.get("EVOLVE_VAULT_TOKEN", "")
        if not address or not token:
            raise ValidationError("Vault is not configured on the server.")
        kv_version = os.environ.get("EVOLVE_VAULT_KV_VERSION", "1")
        request_path = f"{address}/v1/{path}"
        if kv_version == "2":
            existing_request = urllib.request.Request(request_path, headers={"X-Vault-Token": token})
            try:
                with urllib.request.urlopen(existing_request, timeout=10) as response:
                    existing_payload = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    existing_payload = {}
                else:
                    raise ValidationError("Vault secret could not be read before the OAuth secret write.") from error
            existing_data = existing_payload.get("data", {}) if isinstance(existing_payload, dict) else {}
            existing_data = existing_data.get("data", existing_data) if isinstance(existing_data, dict) else {}
            payload = {"data": {**existing_data, key: value}}
        else:
            payload = {key: value}
        request = urllib.request.Request(
            request_path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"X-Vault-Token": token, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10):
                return
        except urllib.error.HTTPError as error:
            raise ValidationError("Vault rejected the OAuth secret write; check the path, KV version, and token policy.") from error
    raise ValidationError("Unsupported secret backend.")


def google_oauth_url(connector, state):
    client_id = resolve_secret(connector.secret_backend, connector.client_id_reference)
    if not client_id:
        raise ValidationError("The Google client ID reference does not resolve on the server.")
    scopes = {
        GoogleWorkspaceConnector.Product.DRIVE: "https://www.googleapis.com/auth/drive.readonly",
        GoogleWorkspaceConnector.Product.DOCS: "https://www.googleapis.com/auth/documents.readonly",
        GoogleWorkspaceConnector.Product.SHEETS: "https://www.googleapis.com/auth/spreadsheets",
        GoogleWorkspaceConnector.Product.CALENDAR: "https://www.googleapis.com/auth/calendar",
        GoogleWorkspaceConnector.Product.GMAIL: "https://mail.google.com/",
    }
    requested = [scopes[item] for item in connector.products if item in scopes]
    redirect_uri = connector.redirect_uri or "https://evolve.nastycsa.com/api/platform/google-workspace/callback/"
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(requested),
        "access_type": "offline",
        "prompt": "consent select_account",
        "include_granted_scopes": "true",
        "state": state,
    })


def exchange_google_oauth_code(connector, code):
    client_id = resolve_secret(connector.secret_backend, connector.client_id_reference)
    client_secret = resolve_secret(connector.secret_backend, connector.client_secret_reference)
    redirect_uri = connector.redirect_uri or "https://evolve.nastycsa.com/api/platform/google-workspace/callback/"
    payload = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode()
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise ValidationError("Google account authorization could not be completed.") from error
    if not data.get("refresh_token"):
        raise ValidationError("Google did not return a refresh token. Reconnect with account consent enabled.")
    return data

def google_drive_access_token():
    connector = (
        GoogleWorkspaceConnector.objects.filter(
            is_active=True, connection_status="healthy", products__contains=[GoogleWorkspaceConnector.Product.DRIVE]
        ).order_by("-updated_at").first()
    )
    if connector is None:
        raise ValidationError("Activate a healthy Google Workspace connector with Drive enabled first.")
    client_id = resolve_secret(connector.secret_backend, connector.client_id_reference)
    client_secret = resolve_secret(connector.secret_backend, connector.client_secret_reference)
    refresh_token = resolve_secret(connector.secret_backend, connector.refresh_token_reference)
    if not client_id or not client_secret or not refresh_token:
        raise ValidationError("Google Drive OAuth references must resolve on the server.")
    payload = urllib.parse.urlencode({
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh_token, "grant_type": "refresh_token",
    }).encode()
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise ValidationError("Google Drive token exchange failed.") from error
    if not data.get("access_token"):
        raise ValidationError("Google Drive token exchange did not return an access token.")
    return data["access_token"]


def google_drive_request(path, access_token, params=None):
    query = urllib.parse.urlencode(params or {})
    url = "https://www.googleapis.com/drive/v3/" + path + (("?" + query) if query else "")
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    try:
        return urllib.request.urlopen(request, timeout=20)
    except (urllib.error.HTTPError, urllib.error.URLError) as error:
        raise ValidationError("Google Drive could not complete the request.") from error


def google_gmail_profile(access_token):
    request = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise ValidationError("Google did not return a usable Gmail profile for this account.") from error
    email_address = str(payload.get("emailAddress", "")).strip().lower()
    if not email_address or "@" not in email_address:
        raise ValidationError("Google Gmail profile did not include a valid mailbox address.")
    return email_address


def validate_google_oauth(connector):
    if not connector.refresh_token_reference:
        raise ValidationError("A refresh token reference is required for live Sheets access.")
    client_id = resolve_secret(connector.secret_backend, connector.client_id_reference)
    client_secret = resolve_secret(connector.secret_backend, connector.client_secret_reference)
    refresh_token = resolve_secret(connector.secret_backend, connector.refresh_token_reference)
    if not client_id or not client_secret or not refresh_token:
        raise ValidationError("Google OAuth references must resolve on the server.")
    payload = urllib.parse.urlencode({"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"}).encode()
    request = urllib.request.Request("https://oauth2.googleapis.com/token", data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = {}
        error_code = detail.get("error", "")
        reason = detail.get("error_description") or error_code or "Google rejected the refresh token"
        guidance = {
            "invalid_grant": "refresh token is invalid or revoked; generate a new refresh token for this exact OAuth client",
            "unauthorized_client": "OAuth client is not allowed to use this grant; check the client type and Google API consent configuration",
            "invalid_client": "client ID or client secret does not match the client that issued the refresh token",
        }.get(error_code)
        if guidance:
            reason = f"{reason} ({guidance})"
        raise ValidationError(f"Google OAuth token exchange failed: {reason}.") from error
    except (urllib.error.URLError, json.JSONDecodeError) as error:
        raise ValidationError("Google OAuth token exchange failed: Google was unreachable or returned invalid JSON.") from error
    if not data.get("access_token"):
        raise ValidationError("Google OAuth token exchange did not return an access token.")
    return data


def _google_oauth_access_token_for_email(connector):
    """Exchange the configured Gmail refresh token for a short-lived IMAP token."""
    google = (
        GoogleWorkspaceConnector.objects.filter(
            is_active=True,
            products__contains=[GoogleWorkspaceConnector.Product.GMAIL],
        )
        .order_by("-updated_at")
        .first()
    )
    if google is None:
        raise ValidationError("Activate a Google Workspace connector with Gmail enabled first.")
    client_id = resolve_secret(google.secret_backend, google.client_id_reference)
    client_secret = resolve_secret(google.secret_backend, google.client_secret_reference)
    refresh_reference = connector.oauth2_refresh_token_reference or google.refresh_token_reference
    refresh_backend = connector.secret_backend if connector.oauth2_refresh_token_reference else google.secret_backend
    refresh_token = resolve_secret(refresh_backend, refresh_reference)
    if not client_id or not client_secret or not refresh_token:
        raise ValidationError("Google OAuth client and Gmail refresh-token references must resolve on the server.")
    payload = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode()
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = {}
        reason = detail.get("error_description") or detail.get("error") or "Google rejected the refresh token"
        raise ValidationError(f"Google OAuth IMAP token exchange failed: {reason}.") from error
    except (urllib.error.URLError, json.JSONDecodeError) as error:
        raise ValidationError("Google OAuth IMAP token exchange failed: Google was unreachable or returned invalid JSON.") from error
    if not data.get("access_token"):
        raise ValidationError("Google OAuth IMAP token exchange did not return an access token.")
    return data["access_token"]


def _safe_error(error):
    return f"Connection failed ({error.__class__.__name__})."


def _smtp(connector):
    client = (
        smtplib.SMTP_SSL(
            connector.host, connector.port, timeout=10, context=ssl.create_default_context()
        )
        if connector.use_ssl
        else smtplib.SMTP(connector.host, connector.port, timeout=10)
    )
    if connector.use_tls:
        client.starttls(context=ssl.create_default_context())
    if connector.oauth2_enabled:
        if not connector.mailbox_address:
            raise ValidationError("OAuth2 SMTP connectors require the mailbox address.")
        access_token = _google_oauth_access_token_for_email(connector)
        auth = base64.b64encode(
            f"user={connector.mailbox_address}\x01auth=Bearer {access_token}\x01\x01".encode()
        ).decode()
        code, _ = client.docmd("AUTH", "XOAUTH2 " + auth)
        if code != 235:
            raise ValidationError("Google OAuth2 SMTP authentication failed.")
        return client
    password = resolve_secret(connector.secret_backend, connector.secret_reference)
    if connector.secret_reference and not password:
        raise ValidationError("Connector credentials are not configured on the server.")
    if connector.secret_reference and connector.username:
        client.login(connector.username, password)
    # No secret reference means an IP-allowlisted SMTP relay; do not attempt AUTH.
    return client


def _imap(connector):
    if connector.oauth2_enabled:
        if not connector.mailbox_address:
            raise ValidationError("OAuth2 IMAP connectors require the mailbox address.")
        access_token = _google_oauth_access_token_for_email(connector)
        client = imaplib.IMAP4_SSL(connector.imap_host, connector.imap_port)
        auth_string = f"user={connector.mailbox_address}\x01auth=Bearer {access_token}\x01\x01"
        client.authenticate("XOAUTH2", lambda _: auth_string.encode())
        return client
    password = resolve_secret(connector.secret_backend, connector.secret_reference)
    if not connector.username or not password:
        raise ValidationError("IMAP username and external app-password reference are required.")
    client = imaplib.IMAP4_SSL(connector.imap_host, connector.imap_port)
    client.authenticate("PLAIN", lambda _: f"\0{connector.username}\0{password}".encode())
    return client


def test_email_connector(connector):
    try:
        if connector.provider_type == "imap":
            with _imap(connector) as client:
                client.noop()
        else:
            with _smtp(connector) as client:
                client.noop()
    except ValidationError:
        raise
    except Exception as error:
        connector.connection_status = ConnectionState.FAILED
        connector.last_test_message = _safe_error(error)
        connector.last_tested_at = timezone.now()
        connector.save(
            update_fields=("connection_status", "last_test_message", "last_tested_at", "updated_at")
        )
        raise ValidationError("Email connection test failed.") from error
    connector.connection_status = ConnectionState.HEALTHY
    connector.last_test_message = ("IMAP authentication and connection succeeded." if connector.provider_type == "imap" else "SMTP authentication and connection succeeded.")
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
    access = resolve_secret(provider.secret_backend, provider.access_key_reference)
    secret = resolve_secret(provider.secret_backend, provider.secret_key_reference)
    if not access or not secret:
        raise ValidationError("Storage credentials are not configured on the server.")
    return boto3.client(
        "s3",
        endpoint_url=provider.endpoint,
        region_name=provider.region,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        use_ssl=provider.use_ssl,
        config=Config(connect_timeout=5, read_timeout=30, retries={"max_attempts": 2}),
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


def send_application_email(connector, recipient, subject, text_body, html_body, *, cc=None, bcc=None, attachments=None):
    connector.full_clean()
    if not connector.is_active:
        raise ValidationError("Email connector is inactive.")
    if any(char in subject for char in "\r\n") or len(subject) > 220:
        raise ValidationError("Invalid email subject.")
    message = EmailMessage()
    message["From"] = f"{connector.from_name} <{connector.from_email}>"
    message["To"] = recipient
    if cc:
        message["Cc"] = ", ".join(cc)
    if bcc:
        message["Bcc"] = ", ".join(bcc)
    message["Subject"] = subject
    if connector.reply_to_email:
        message["Reply-To"] = connector.reply_to_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    for attachment in attachments or []:
        message.add_attachment(
            attachment["content"],
            maintype=attachment["content_type"].split("/", 1)[0],
            subtype=attachment["content_type"].split("/", 1)[-1],
            filename=attachment["filename"],
        )
    try:
        with _smtp(connector) as client:
            client.send_message(message)
    except ValidationError:
        raise
    except Exception as error:
        raise ValidationError("Email delivery failed.") from error
