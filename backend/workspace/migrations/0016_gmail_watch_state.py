from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("workspace", "0015_alter_mailboxsentmessage_status")]

    operations = [
        migrations.AddField(
            model_name="messagingconnector",
            name="gmail_topic_name",
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name="messagingconnector",
            name="gmail_watch_expiration",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="messagingconnector",
            name="gmail_history_id",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
