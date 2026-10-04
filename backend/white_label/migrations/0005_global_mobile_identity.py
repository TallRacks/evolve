from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("white_label", "0004_globalbrandingasset")]
    operations = [
        migrations.AddField(model_name="globalbranding", name="application_title", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="globalbranding", name="mobile_icon_url", field=models.URLField(blank=True, max_length=500)),
        migrations.AlterField(model_name="globalbrandingasset", name="asset_type", field=models.CharField(choices=[("logo", "Logo"), ("favicon", "Favicon"), ("mobile_icon", "Mobile/home-screen icon")], max_length=20)),
    ]
