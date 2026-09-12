import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workspace", "0001_initial"),
        ("organizations", "0002_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AutomationExecution",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event_key", models.CharField(max_length=80)),
                ("correlation_id", models.UUIDField()),
                ("depth", models.PositiveSmallIntegerField(default=0)),
                ("status", models.CharField(choices=[("executed", "Executed"), ("failed", "Failed"), ("skipped", "Skipped")], max_length=16)),
                ("result_summary", models.CharField(blank=True, max_length=500)),
                ("idempotency_key", models.CharField(max_length=180, unique=True)),
                ("automation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="executions", to="workspace.automation")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organizations.organization")),
            ],
        ),
        migrations.CreateModel(
            name="Comment",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("context_type", models.CharField(choices=[("task", "Task"), ("booking", "Booking"), ("campaign", "Campaign"), ("production", "Production")], max_length=20)),
                ("context_id", models.UUIDField()),
                ("body", models.TextField(max_length=5000)),
                ("edited_at", models.DateTimeField(blank=True, null=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="comments", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="comments", to="organizations.organization")),
            ],
        ),
        migrations.CreateModel(
            name="MessagingConnector",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider_type", models.CharField(choices=[("whatsapp", "WhatsApp Business"), ("email", "Inbound email")], max_length=20)),
                ("name", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=False)),
                ("is_default", models.BooleanField(default=False)),
                ("display_name", models.CharField(blank=True, max_length=120)),
                ("display_phone", models.CharField(blank=True, max_length=40)),
                ("webhook_status", models.CharField(choices=[("not_configured", "Not configured"), ("healthy", "Healthy"), ("failed", "Failed")], default="not_configured", max_length=24)),
                ("access_token_reference", models.CharField(blank=True, max_length=110)),
                ("signing_secret_reference", models.CharField(blank=True, max_length=110)),
                ("verification_token_reference", models.CharField(blank=True, max_length=110)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="messaging_connectors", to="organizations.organization")),
            ],
        ),
        migrations.CreateModel(
            name="ChannelVerification",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("channel", models.CharField(max_length=20)), ("code_hash", models.CharField(max_length=64)),
                ("expires_at", models.DateTimeField()), ("used_at", models.DateTimeField(blank=True, null=True)),
                ("provider_subject", models.CharField(blank=True, max_length=180)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organizations.organization")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="channel_verifications", to=settings.AUTH_USER_MODEL)),
                ("connector", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="verifications", to="workspace.messagingconnector")),
            ],
        ),
        migrations.CreateModel(
            name="MessagingIdentity",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider_subject", models.CharField(max_length=180)), ("display_address", models.CharField(blank=True, max_length=180)),
                ("is_verified", models.BooleanField(default=False)), ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("active_context", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="active_messaging_contexts", to="organizations.organization")),
                ("connector", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="identities", to="workspace.messagingconnector")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="messaging_identities", to="organizations.organization")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="messaging_identities", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="InboundMessage",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider_message_id", models.CharField(max_length=220)), ("channel", models.CharField(choices=[("whatsapp", "WhatsApp"), ("email", "Email")], max_length=20)),
                ("sender_address", models.CharField(max_length=180)), ("subject", models.CharField(blank=True, max_length=220)),
                ("body_text", models.TextField(blank=True, max_length=10000)), ("has_attachments", models.BooleanField(default=False)), ("event_type", models.CharField(max_length=80)),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="organizations.organization")),
                ("connector", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inbound_messages", to="workspace.messagingconnector")),
                ("identity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="messages", to="workspace.messagingidentity")),
            ],
        ),
        migrations.CreateModel(
            name="CommentMention",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("comment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mentions", to="workspace.comment")),
                ("membership", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="comment_mentions", to="organizations.membership")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("comment", "membership"), name="unique_comment_mention")]},
        ),
        migrations.AddConstraint(
            model_name="messagingconnector",
            constraint=models.UniqueConstraint(condition=models.Q(is_default=True), fields=("organization", "provider_type", "is_default"), name="one_default_messaging_connector"),
        ),
        migrations.AddConstraint(
            model_name="messagingidentity",
            constraint=models.UniqueConstraint(fields=("connector", "provider_subject"), name="unique_provider_identity"),
        ),
        migrations.AddConstraint(
            model_name="inboundmessage",
            constraint=models.UniqueConstraint(fields=("connector", "provider_message_id"), name="unique_inbound_provider_message"),
        ),
    ]
