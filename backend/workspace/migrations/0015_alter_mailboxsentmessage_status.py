from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("workspace", "0014_mailbox_folders")]
    operations = [
        migrations.AlterField(
            model_name="mailboxsentmessage",
            name="status",
            field=models.CharField(choices=[("draft", "Draft"), ("outbox", "Outbox"), ("sent", "Sent"), ("failed", "Failed")], default="sent", max_length=16),
        ),
    ]
