import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q

from core.models import TimestampedModel

from .validation import (
    validate_email_secret_reference,
    validate_google_secret_reference,
    validate_path_prefix,
    validate_storage_endpoint,
    validate_storage_secret_reference,
)


class ConnectionState(models.TextChoices):
    NEVER_TESTED = "never_tested", "Never tested"
    HEALTHY = "healthy", "Healthy"
    FAILED = "failed", "Failed"


class SecretBackend(models.TextChoices):
    ENVIRONMENT = "environment", "Environment reference"
    VAULT = "vault", "HashiCorp Vault"
    AWS_SECRETS_MANAGER = "aws_secrets_manager", "AWS Secrets Manager"


class EmailConnector(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    provider_type = models.CharField(
        max_length=20,
        default="smtp",
        choices=(("smtp", "SMTP"), ("imap", "IMAP receiving")),
    )
    is_active = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    from_name = models.CharField(max_length=120)
    from_email = models.EmailField()
    reply_to_email = models.EmailField(blank=True)
    host = models.CharField(max_length=253)
    port = models.PositiveIntegerField(
        default=587, validators=[MinValueValidator(1), MaxValueValidator(65535)]
    )
    imap_host = models.CharField(max_length=253, blank=True)
    imap_port = models.PositiveIntegerField(
        default=993, validators=[MinValueValidator(1), MaxValueValidator(65535)]
    )
    oauth2_enabled = models.BooleanField(default=False)
    oauth2_refresh_token_reference = models.CharField(
        max_length=220, blank=True, validators=[validate_email_secret_reference]
    )
    mailbox_address = models.EmailField(blank=True)
    use_tls = models.BooleanField(default=True)
    use_ssl = models.BooleanField(default=False)
    username = models.CharField(max_length=253, blank=True)
    secret_backend = models.CharField(
        max_length=24, choices=SecretBackend.choices, default=SecretBackend.ENVIRONMENT
    )
    secret_reference = models.CharField(
        max_length=220, blank=True, validators=[validate_email_secret_reference]
    )
    connection_status = models.CharField(
        max_length=20, choices=ConnectionState.choices, default=ConnectionState.NEVER_TESTED
    )
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_message = models.CharField(max_length=240, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("is_default",),
                condition=Q(is_default=True),
                name="one_default_email_connector",
            )
        ]

    @property
    def secret_configured(self):
        # Gmail SMTP relay can be allowlisted by server IP and intentionally has no password.
        if self.provider_type == "smtp" and not self.secret_reference:
            return True
        return bool(
            self.secret_reference
            and (
                self.secret_backend != SecretBackend.ENVIRONMENT
                or os.environ.get(self.secret_reference)
            )
        )

    def clean(self):
        if self.provider_type == "imap":
            if not self.imap_host:
                raise ValidationError({"imap_host": "IMAP receiving connectors require an IMAP host."})
            if self.oauth2_enabled and not self.oauth2_refresh_token_reference:
                raise ValidationError({"oauth2_refresh_token_reference": "OAuth2 IMAP connectors require an external refresh-token reference."})
            if not self.oauth2_enabled and not self.secret_reference:
                raise ValidationError({"secret_reference": "IMAP app-password connectors require an external secret reference."})
        if any(char in self.from_name for char in "\r\n"):
            raise ValidationError({"from_name": "Email sender name cannot contain newlines."})
        if self.use_tls and self.use_ssl:
            raise ValidationError("TLS and implicit SSL cannot both be enabled.")
        if not self.host or any(char in self.host for char in "/:@[]"):
            raise ValidationError({"host": "Use a valid SMTP hostname."})
        if self.is_default and not self.is_active:
            raise ValidationError("The default connector must be active.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class GoogleWorkspaceConnector(TimestampedModel):
    class Product(models.TextChoices):
        DRIVE = "drive", "Google Drive"
        DOCS = "docs", "Google Docs"
        SHEETS = "sheets", "Google Sheets"
        CALENDAR = "calendar", "Google Calendar"
        GMAIL = "gmail", "Gmail"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    products = models.JSONField(default=list)
    secret_backend = models.CharField(
        max_length=24, choices=SecretBackend.choices, default=SecretBackend.ENVIRONMENT
    )
    client_id_reference = models.CharField(max_length=220, validators=[validate_google_secret_reference])
    client_secret_reference = models.CharField(max_length=220, validators=[validate_google_secret_reference])
    refresh_token_reference = models.CharField(max_length=220, blank=True, validators=[validate_google_secret_reference])
    redirect_uri = models.URLField(max_length=500, blank=True)
    is_active = models.BooleanField(default=False)
    connection_status = models.CharField(
        max_length=20, choices=ConnectionState.choices, default=ConnectionState.NEVER_TESTED
    )
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_message = models.CharField(max_length=240, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ("name",)

    @property
    def credentials_configured(self):
        if self.secret_backend != SecretBackend.ENVIRONMENT:
            return bool(self.client_id_reference and self.client_secret_reference)
        return bool(
            self.client_id_reference and os.environ.get(self.client_id_reference)
            and self.client_secret_reference and os.environ.get(self.client_secret_reference)
        )

    def clean(self):
        allowed = {choice for choice, _ in self.Product.choices}
        if not self.products or any(product not in allowed for product in self.products):
            raise ValidationError({"products": "Select at least one supported Google product."})
        if self.redirect_uri and not self.redirect_uri.startswith("https://"):
            raise ValidationError({"redirect_uri": "Redirect URI must use HTTPS."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class StorageProvider(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    provider_type = models.CharField(
        max_length=24,
        default="s3_compatible",
        choices=(("s3_compatible", "S3 compatible"), ("aws_s3", "AWS S3")),
    )
    is_active = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    endpoint = models.URLField(max_length=500)
    region = models.CharField(max_length=80)
    bucket = models.CharField(
        max_length=63,
        validators=[
            RegexValidator(
                r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", "Use a valid lowercase bucket name."
            )
        ],
    )
    path_prefix = models.CharField(max_length=180, blank=True, validators=[validate_path_prefix])
    public_base_url = models.URLField(max_length=500, blank=True)
    secret_backend = models.CharField(
        max_length=24, choices=SecretBackend.choices, default=SecretBackend.ENVIRONMENT
    )
    access_key_reference = models.CharField(
        max_length=220, validators=[validate_storage_secret_reference]
    )
    secret_key_reference = models.CharField(
        max_length=220, validators=[validate_storage_secret_reference]
    )
    use_ssl = models.BooleanField(default=True)
    connection_status = models.CharField(
        max_length=20, choices=ConnectionState.choices, default=ConnectionState.NEVER_TESTED
    )
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_message = models.CharField(max_length=240, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("is_default",),
                condition=Q(is_default=True),
                name="one_default_storage_provider",
            )
        ]

    @property
    def credentials_configured(self):
        return bool(
            self.secret_backend != SecretBackend.ENVIRONMENT
            or (
                os.environ.get(self.access_key_reference, "")
                and os.environ.get(self.secret_key_reference, "")
            )
        )

    def clean(self):
        validate_storage_endpoint(self.endpoint)
        if self.public_base_url:
            validate_storage_endpoint(self.public_base_url)
        if self.is_default and not self.is_active:
            raise ValidationError("The default storage provider must be active.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class StoragePolicy(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    max_document_size_bytes = models.PositiveBigIntegerField(default=25 * 1024 * 1024)
    max_image_size_bytes = models.PositiveBigIntegerField(default=15 * 1024 * 1024)
    max_audio_size_bytes = models.PositiveBigIntegerField(default=250 * 1024 * 1024)
    max_video_size_bytes = models.PositiveBigIntegerField(default=25 * 1024 * 1024)
    audio_upload_enabled = models.BooleanField(default=False)
    video_upload_enabled = models.BooleanField(default=False)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    def clean(self):
        ceilings = {
            "max_document_size_bytes": 100 * 1024 * 1024,
            "max_image_size_bytes": 50 * 1024 * 1024,
            "max_audio_size_bytes": 1024 * 1024 * 1024,
            "max_video_size_bytes": 2 * 1024 * 1024 * 1024,
        }
        for field, ceiling in ceilings.items():
            value = getattr(self, field)
            if value <= 0 or value > ceiling:
                raise ValidationError(
                    {field: "Value must be positive and within the platform hard ceiling."}
                )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_document_size_bytes__gt=0),
                name="storage_policy_document_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(max_image_size_bytes__gt=0), name="storage_policy_image_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(max_audio_size_bytes__gt=0), name="storage_policy_audio_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(max_video_size_bytes__gt=0), name="storage_policy_video_positive"
            ),
        ]
