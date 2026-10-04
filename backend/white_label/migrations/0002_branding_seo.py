from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("white_label", "0001_initial")]
    operations = [
        migrations.AddField(model_name="organizationbranding", name="seo_title", field=models.CharField(blank=True, max_length=160)),
        migrations.AddField(model_name="organizationbranding", name="seo_description", field=models.CharField(blank=True, max_length=320)),
        migrations.AddField(model_name="organizationbranding", name="og_image_url", field=models.URLField(blank=True, max_length=500)),
    ]
