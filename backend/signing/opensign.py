import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from documents.storage import get_storage_backend


class OpenSignUnavailable(Exception):
    pass


@dataclass(frozen=True)
class OpenSignCreatedDocument:
    provider_document_id: str
    signing_url: str


def _base_url():
    return os.environ.get("EVOLVE_OPENSIGN_BASE_URL", "http://opensign-server:8080/api/app").rstrip("/")


def _headers(session_token=None, content_type=True):
    headers = {"X-Parse-Application-Id": os.environ.get("EVOLVE_OPENSIGN_APP_ID", "opensign")}
    if session_token:
        headers["X-Parse-Session-Token"] = session_token
    if content_type:
        headers["Content-Type"] = "application/json"
    return headers


def _json_request(path, payload, *, session_token=None):
    request = urllib.request.Request(
        f"{_base_url()}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(session_token=session_token),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as error:
        raise OpenSignUnavailable("The local OpenSign service could not complete the request.") from error


def _login():
    email = os.environ.get("EVOLVE_OPENSIGN_SERVICE_EMAIL", "").strip()
    password = os.environ.get("EVOLVE_OPENSIGN_SERVICE_PASSWORD", "")
    if not email or not password:
        raise OpenSignUnavailable("Configure EVOLVE_OPENSIGN_SERVICE_EMAIL and EVOLVE_OPENSIGN_SERVICE_PASSWORD for local OpenSign sending.")
    result = _json_request("/login", {"username": email, "password": password})
    token = result.get("sessionToken")
    object_id = result.get("objectId")
    if not token or not object_id:
        raise OpenSignUnavailable("The local OpenSign service account could not be authenticated.")
    return token, object_id


def _upload_private_document(document, session_token):
    backend = get_storage_backend(document.storage_provider)
    stored = backend.open_stream(document.storage_key)
    filename = document.original_filename or f"{document.pk}.pdf"
    boundary = "----EvolveOpenSignUploadBoundary"
    body = stored.body.read()
    prefix = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
        f"Content-Type: {document.detected_content_type or 'application/pdf'}\r\n\r\n"
    ).encode("utf-8")
    payload = prefix + body + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = urllib.request.Request(
        f"{_base_url()}/files/{filename}",
        data=payload,
        headers={
            **_headers(session_token=session_token, content_type=False),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as error:
        raise OpenSignUnavailable("OpenSign could not receive the private document.") from error
    url = result.get("url")
    if not url:
        raise OpenSignUnavailable("OpenSign did not return a document URL.")
    return url


def create_signing_document(request):
    document = request.source_document
    if not document:
        raise OpenSignUnavailable("Attach or generate a document before sending it to OpenSign.")
    session_token, user_id = _login()
    if document.source_type == document.SourceType.STORED:
        source_url = _upload_private_document(document, session_token)
    elif document.source_type == document.SourceType.EXTERNAL:
        source_url = document.external_url
    else:
        raise OpenSignUnavailable("Generated text documents need a PDF export before OpenSign can sign them.")
    signers = [
        {"Name": signer.get("name", ""), "Email": signer["email"]}
        for signer in request.signers
        if signer.get("email")
    ]
    if not signers:
        raise OpenSignUnavailable("Add at least one signer before sending.")
    payload = {
        "document": {
            "Name": request.title,
            "URL": source_url,
            "SentToOthers": True,
            "AutomaticReminders": True,
            "NotifyOnSignatures": True,
            "Signers": signers,
            "ExtUserPtr": {"__type": "Pointer", "className": "_User", "objectId": user_id},
            "CreatedBy": {"__type": "Pointer", "className": "_User", "objectId": user_id},
        }
    }
    result = _json_request("/functions/createdocumentfromapp", payload, session_token=session_token)
    provider_id = result.get("result", {}).get("objectId") or result.get("objectId")
    if not provider_id:
        raise OpenSignUnavailable("OpenSign did not return a document identifier.")
    first_email = signers[0]["Email"]
    token = base64.b64encode(f"{provider_id}/{first_email}".encode()).decode()
    public_url = os.environ.get("EVOLVE_OPENSIGN_PUBLIC_URL", "https://sign.evolve.nastycsa.com").rstrip("/")
    return OpenSignCreatedDocument(provider_document_id=provider_id, signing_url=f"{public_url}/login/{token}")
