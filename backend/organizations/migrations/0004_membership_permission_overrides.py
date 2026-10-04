from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("organizations", "0003_role_choices")]
    operations = [migrations.AddField(model_name="membership", name="permission_overrides", field=models.JSONField(blank=True, default=dict))]
