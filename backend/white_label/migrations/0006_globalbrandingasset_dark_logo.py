from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("white_label", "0005_global_mobile_identity")]
    operations = [migrations.AlterField(model_name="globalbrandingasset", name="asset_type", field=models.CharField(choices=[("logo", "Logo"), ("dark_logo", "Dark-mode logo"), ("favicon", "Favicon"), ("mobile_icon", "Mobile/home-screen icon")], max_length=20))]
