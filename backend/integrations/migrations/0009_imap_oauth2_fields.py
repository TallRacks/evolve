from django.db import migrations, models
import integrations.validation

class Migration(migrations.Migration):
    dependencies = [("integrations", "0008_googleworkspaceconnector_refresh_token_reference")]
    operations = [
        migrations.AlterField(
            model_name="emailconnector",
            name="provider_type",
            field=models.CharField(default="smtp", max_length=20, choices=[("smtp", "SMTP"), ("imap", "IMAP receiving")]),
        ),
        migrations.AddField(model_name="emailconnector", name="imap_host", field=models.CharField(blank=True, max_length=253)),
        migrations.AddField(model_name="emailconnector", name="imap_port", field=models.PositiveIntegerField(default=993)),
        migrations.AddField(model_name="emailconnector", name="oauth2_enabled", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="emailconnector", name="oauth2_refresh_token_reference", field=models.CharField(blank=True, max_length=220, validators=[integrations.validation.validate_email_secret_reference])),
        migrations.AddField(model_name="emailconnector", name="mailbox_address", field=models.EmailField(blank=True, max_length=254)),
    ]
