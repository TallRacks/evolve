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
    gmail_topic_name = models.CharField(max_length=300, blank=True)
    gmail_watch_expiration = models.DateTimeField(null=True, blank=True)
    gmail_history_id = models.CharField(max_length=80, blank=True)
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

    class Folder(models.TextChoices):
        INBOX = "inbox", "Inbox"
        ARCHIVED = "archived", "Archived"
        DELETED = "deleted", "Deleted"

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
    is_read = models.BooleanField(default=False)
    folder = models.CharField(max_length=16, choices=Folder.choices, default=Folder.INBOX)
    event_type = models.CharField(max_length=80)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("connector", "provider_message_id"), name="unique_inbound_provider_message")]


class MailboxAccess(TimestampedModel):
    """Organization-scoped access grant for a configured inbound email channel."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connector = models.ForeignKey(MessagingConnector, on_delete=models.PROTECT, related_name="mailbox_access")
    sender_connector = models.ForeignKey("integrations.EmailConnector", null=True, blank=True, on_delete=models.PROTECT, related_name="mailbox_access")
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="mailbox_access")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="mailbox_access")
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="mailbox_access_granted")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("connector", "user"), name="unique_mailbox_access_user_connector")]
        indexes = [models.Index(fields=("organization", "user", "is_active"))]

    def clean(self):
        if self.connector.provider_type != MessagingConnector.Provider.EMAIL:
            raise ValidationError({"connector": "Mailbox access requires an email connector."})
        if self.connector.organization_id not in (None, self.organization_id):
            raise ValidationError({"connector": "Connector and organization must match."})
        if not self.user.memberships.filter(organization=self.organization, is_active=True).exists():
            raise ValidationError({"user": "Mailbox access requires an active organization membership."})


class MailboxReply(TimestampedModel):
    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(InboundMessage, on_delete=models.PROTECT, related_name="replies")
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    sender_address = models.EmailField()
    recipient_address = models.EmailField()
    subject = models.CharField(max_length=220)
    body_text = models.TextField(max_length=10000)
    status = models.CharField(max_length=16, choices=Status.choices)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("message", "created_at"))]


class MailboxSentMessage(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OUTBOX = "outbox", "Outbox"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    class Folder(models.TextChoices):
        DRAFTS = "drafts", "Drafts"
        OUTBOX = "outbox", "Outbox"
        SENT = "sent", "Sent"
        DELETED = "deleted", "Deleted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connector = models.ForeignKey(MessagingConnector, on_delete=models.PROTECT, related_name="sent_messages")
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="mailbox_sent_messages")
    sender_address = models.EmailField()
    recipient_address = models.TextField(max_length=2000, blank=True)
    folder = models.CharField(max_length=16, choices=Folder.choices, default=Folder.SENT)
    cc_addresses = models.JSONField(default=list, blank=True)
    bcc_addresses = models.JSONField(default=list, blank=True)
    attachment_document_ids = models.JSONField(default=list, blank=True)
    tagged_user_ids = models.JSONField(default=list, blank=True)
    subject = models.CharField(max_length=220, blank=True)
    body_text = models.TextField(max_length=10000, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SENT)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("organization", "created_at"))]
