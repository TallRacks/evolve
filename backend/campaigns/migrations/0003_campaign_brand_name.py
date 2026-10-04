from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("campaigns", "0002_campaignresponsibility")]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="brand_name",
            field=models.CharField(blank=True, max_length=220),
        ),
    ]
