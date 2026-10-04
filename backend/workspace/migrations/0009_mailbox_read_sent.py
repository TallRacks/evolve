from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    dependencies = [("workspace", "0008_mailboxaccess_mailboxreply"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name="inboundmessage", name="is_read", field=models.BooleanField(default=False)),
        migrations.CreateModel(
            name="MailboxSentMessage",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("sender_address", models.EmailField(max_length=254)), ("recipient_address", models.EmailField(max_length=254)),
                ("subject", models.CharField(blank=True, max_length=220)), ("body_text", models.TextField(max_length=10000)),
                ("status", models.CharField(choices=[("sent", "Sent"), ("failed", "Failed")], default="sent", max_length=16)),
                ("connector", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sent_messages", to="workspace.messagingconnector")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mailbox_sent_messages", to="organizations.organization")),
                ("sent_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",), "indexes": [models.Index(fields=["organization", "created_at"], name="workspace_m_organiz_3efc09_idx")]},
        ),
    ]
