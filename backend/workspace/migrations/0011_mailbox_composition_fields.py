from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("workspace", "0010_mailbox_sender_profile")]
    operations = [
        migrations.AddField(model_name="mailboxsentmessage", name="cc_addresses", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="mailboxsentmessage", name="bcc_addresses", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="mailboxsentmessage", name="attachment_document_ids", field=models.JSONField(blank=True, default=list)),
    ]
