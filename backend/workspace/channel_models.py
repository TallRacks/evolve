import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import TimestampedModel


class MessagingConnector(TimestampedModel):
    class Provider(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp Business"
        EMAIL = "email", "Inbound email"

    class Status(models.TextChoices):
        NOT_CONFIGURED = "not_configured", "Not configured"
        HEALTHY = "healthy", "Healthy"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.PROTECT, related_name="messaging_connectors")
    provider_type = models.CharField(max_length=20, choices=Provider.choices)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    display_name = models.CharField(max_length=120, blank=True)
    display_phone = models.CharField(max_length=40, blank=True)
    webhook_status = models.CharField(max_length=24, choices=Status.choices, default=Status.NOT_CONFIGURED)
    access_token_reference = models.CharField(max_length=110, blank=True)
    signing_secret_reference = models.CharField(max_length=110, blank=True)
    verification_token_reference = models.CharField(max_length=110, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("organization", "provider_type", "is_default"), condition=models.Q(is_default=True), name="one_default_messaging_connector")]

    def clean(self):
        if self.provider_type == self.Provider.WHATSAPP and not self.signing_secret_reference:
            raise ValidationError({"signing_secret_reference": "WhatsApp webhooks require an external secret reference."})
        if self.provider_type == self.Provider.EMAIL and not self.signing_secret_reference:
            raise ValidationError({"signing_secret_reference": "Inbound email webhooks require an external secret reference."})
        if self.is_default and not self.is_active:
            raise ValidationError("The default connector must be active.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class MessagingIdentity(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connector = models.ForeignKey(MessagingConnector, on_delete=models.PROTECT, related_name="identities")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="messaging_identities")
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="messaging_identities")
    provider_subject = models.CharField(max_length=180)
    display_address = models.CharField(max_length=180, blank=True)
    is_verified = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    active_context = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.PROTECT, related_name="active_messaging_contexts")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("connector", "provider_subject"), name="unique_provider_identity")]

    @property
    def is_active(self):
        return self.is_verified and self.revoked_at is None and self.user.is_active and self.connector.is_active


class ChannelVerification(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connector = models.ForeignKey(MessagingConnector, on_delete=models.PROTECT, related_name="verifications")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="channel_verifications")
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    channel = models.CharField(max_length=20)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    provider_subject = models.CharField(max_length=180, blank=True)

    @property
    def usable(self):
        return self.used_at is None and self.expires_at > timezone.now() and self.user.is_active


class InboundMessage(TimestampedModel):
    class Channel(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "Email"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connector = models.ForeignKey(MessagingConnector, on_delete=models.PROTECT, related_name="inbound_messages")
    identity = models.ForeignKey(MessagingIdentity, null=True, blank=True, on_delete=models.PROTECT, related_name="messages")
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.PROTECT)
    provider_message_id = models.CharField(max_length=220)
    channel = models.CharField(max_length=20, choices=Channel.choices)
    sender_address = models.CharField(max_length=180)
    subject = models.CharField(max_length=220, blank=True)
    body_text = models.TextField(max_length=10000, blank=True)
    has_attachments = models.BooleanField(default=False)
    event_type = models.CharField(max_length=80)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("connector", "provider_message_id"), name="unique_inbound_provider_message")]
