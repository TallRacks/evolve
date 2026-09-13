import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0009_document_workspace"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="OfficeDocumentAttachment",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("is_image", models.BooleanField(default=False)),
                (
                    "attachment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="office_attachment_references",
                        to="documents.document",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="office_attachments_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "office_document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="office_attachments",
                        to="documents.document",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("office_document", "attachment"),
                        name="unique_office_attachment_reference",
                    )
                ]
            },
        ),
    ]
