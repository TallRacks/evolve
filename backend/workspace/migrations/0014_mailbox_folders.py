from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("workspace", "0013_mailbox_sent_recipients")]
    operations = [
        migrations.AddField(model_name="inboundmessage", name="folder", field=models.CharField(choices=[("inbox", "Inbox"), ("archived", "Archived"), ("deleted", "Deleted")], default="inbox", max_length=16)),
        migrations.AddField(model_name="mailboxsentmessage", name="folder", field=models.CharField(choices=[("drafts", "Drafts"), ("outbox", "Outbox"), ("sent", "Sent"), ("deleted", "Deleted")], default="sent", max_length=16)),
        migrations.AlterField(model_name="mailboxsentmessage", name="body_text", field=models.TextField(blank=True, max_length=10000)),
        migrations.AlterField(model_name="mailboxsentmessage", name="recipient_address", field=models.TextField(blank=True, max_length=2000)),
    ]
