import hashlib
import hmac
import json
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from organizations.models import Membership, Organization
from users.models import User

from workspace.channel_models import InboundMessage, MessagingConnector, MessagingIdentity
from workspace.channel_services import verification_code
from workspace.models import ActionRequest
from workspace.services import execute_action, propose_action

pytestmark = pytest.mark.django_db


def setup_member():
    organization = Organization.objects.create(name="Channel Org", slug="channel-org")
    actor = User.objects.create_user(email="actor@channel.invalid", password="Correct-Horse-123")
    Membership.objects.create(user=actor, organization=organization, role=Membership.Role.MANAGER)
    return organization, actor


def connector(organization):
    return MessagingConnector.objects.create(organization=organization, provider_type="whatsapp", name="Test", signing_secret_reference="TEST_CHANNEL_SECRET", verification_token_reference="TEST_VERIFY", is_active=True)


def test_high_risk_is_blocked_and_confirmation_is_bound(monkeypatch):
    organization, actor = setup_member()
    action = propose_action(actor=actor, organization=organization, channel="whatsapp", action_key="finance.record_payment", payload={"amount": "99"}, idempotency_key="high-risk-1")
    assert action.status == ActionRequest.Status.BLOCKED
    safe = propose_action(actor=actor, organization=organization, channel="whatsapp", action_key="tasks.create", payload={"title": "Confirm venue"}, idempotency_key="safe-1")
    with pytest.raises(PermissionError):
        execute_action(action_request_id=safe.id, actor=actor, confirmation_hash=safe.confirmation_hash, channel="email")
    with pytest.raises(PermissionError):
        execute_action(action_request_id=safe.id, actor=User.objects.create_user(email="wrong@channel.invalid", password="Correct-Horse-123"), confirmation_hash=safe.confirmation_hash, channel="whatsapp")


def test_signature_duplicate_and_unknown_identity_are_safe(client, monkeypatch):
    organization, actor = setup_member()
    item = connector(organization)
    monkeypatch.setenv("TEST_CHANNEL_SECRET", "fixture-secret")
    payload = {"provider_message_id": "wamid-1", "sender_subject": "provider-unknown", "text": "MY TASKS"}
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(b"fixture-secret", body, hashlib.sha256).hexdigest()
    url = f"/api/messaging/webhooks/whatsapp/{item.id}/"
    assert client.post(url, data=body, content_type="application/json", HTTP_X_EVOLVE_SIGNATURE="bad").status_code == 403
    response = client.post(url, data=body, content_type="application/json", HTTP_X_EVOLVE_SIGNATURE=signature)
    assert response.status_code == 200
    assert response.json()["message"] == "Identity not linked."
    assert client.post(url, data=body, content_type="application/json", HTTP_X_EVOLVE_SIGNATURE=signature).json()["status"] == "duplicate"
    assert InboundMessage.objects.count() == 1
    assert not MessagingIdentity.objects.exists()


def test_link_code_is_single_use_and_hashed(monkeypatch):
    organization, actor = setup_member()
    item = connector(organization)
    code = verification_code(user=actor, organization=organization, connector=item, channel="whatsapp")
    verification = item.verifications.get()
    assert verification.code_hash == hashlib.sha256(code.encode()).hexdigest()
    assert verification.code_hash != code
