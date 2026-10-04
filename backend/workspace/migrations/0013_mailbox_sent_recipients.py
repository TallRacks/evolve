from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("workspace", "0012_mailboxsentmessage_tagged_user_ids")]
    operations = [migrations.AlterField(model_name="mailboxsentmessage", name="recipient_address", field=models.TextField(max_length=2000))]
