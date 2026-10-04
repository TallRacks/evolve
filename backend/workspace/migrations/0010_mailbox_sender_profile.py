from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("workspace", "0009_mailbox_read_sent"), ("integrations", "0001_initial")]
    operations = [migrations.AddField(model_name="mailboxaccess", name="sender_connector", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mailbox_access", to="integrations.emailconnector"))]
