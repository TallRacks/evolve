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
    validate_path_prefix,
    validate_storage_endpoint,
    validate_storage_secret_reference,
)


class ConnectionState(models.TextChoices):
    NEVER_TESTED = "never_tested", "Never tested"
    HEALTHY = "healthy", "Healthy"
    FAILED = "failed", "Failed"


class EmailConnector(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    provider_type = models.CharField(max_length=20, default="smtp", choices=(("smtp", "SMTP"),))
    is_active = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    from_name = models.CharField(max_length=120)
    from_email = models.EmailField()
    reply_to_email = models.EmailField(blank=True)
    host = models.CharField(max_length=253)
    port = models.PositiveIntegerField(
        default=587, validators=[MinValueValidator(1), MaxValueValidator(65535)]
    )
    use_tls = models.BooleanField(default=True)
    use_ssl = models.BooleanField(default=False)
    username = models.CharField(max_length=253, blank=True)
    secret_reference = models.CharField(
        max_length=110, validators=[validate_email_secret_reference]
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
        return bool(self.secret_reference and os.environ.get(self.secret_reference))

    def clean(self):
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
    access_key_reference = models.CharField(
        max_length=110, validators=[validate_storage_secret_reference]
    )
    secret_key_reference = models.CharField(
        max_length=110, validators=[validate_storage_secret_reference]
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
            os.environ.get(self.access_key_reference, "")
            and os.environ.get(self.secret_key_reference, "")
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
