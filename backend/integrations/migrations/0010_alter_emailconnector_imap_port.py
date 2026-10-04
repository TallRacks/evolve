from django.db import migrations, models
from django.core.validators import MaxValueValidator, MinValueValidator

class Migration(migrations.Migration):
    dependencies=[("integrations","0009_imap_oauth2_fields")]
    operations=[migrations.AlterField(model_name="emailconnector",name="imap_port",field=models.PositiveIntegerField(default=993,validators=[MinValueValidator(1),MaxValueValidator(65535)]))]
