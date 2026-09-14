import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("documents", "0010_officedocumentattachment")]
    operations = [
        migrations.AlterField(
            model_name="document",
            name="visibility",
            field=models.CharField(
                choices=[
                    ("private", "Private"),
                    ("workspace", "Workspace"),
                    ("organization", "Organization"),
                    ("restricted", "Restricted"),
                    ("artist", "Artist"),
                ],
                default="organization",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="DocumentCollaborator",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("view", "View"),
                            ("comment", "Comment"),
                            ("edit", "Edit"),
                            ("manage", "Manage"),
                        ],
                        default="view",
                        max_length=12,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="document_collaborators_added",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="collaborators",
                        to="documents.document",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="document_collaborations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("document", "user"), name="unique_document_collaborator"
                    )
                ]
            },
        ),
        migrations.CreateModel(
            name="DocumentFavorite",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="favorites",
                        to="documents.document",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_favorites",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "document"), name="unique_document_favorite"
                    )
                ]
            },
        ),
        migrations.CreateModel(
            name="DocumentRecentAccess",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("last_viewed_at", models.DateTimeField()),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="recent_accesses",
                        to="documents.document",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_recent_accesses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "document"), name="unique_document_recent_access"
                    )
                ],
                "indexes": [
                    models.Index(
                        fields=("user", "last_viewed_at"), name="documents_d_user_id_87754e_idx"
                    )
                ],
            },
        ),
    ]
