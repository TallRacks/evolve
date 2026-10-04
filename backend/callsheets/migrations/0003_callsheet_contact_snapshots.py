from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("callsheets", "0002_callsheet_operational_details")]

    operations = [
        migrations.AddField(
            model_name="callsheetversion",
            name="point_of_contact",
            field=models.CharField(blank=True, max_length=220),
        ),
        migrations.AddField(
            model_name="callsheetversion",
            name="point_of_contact_details",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="callsheetversion",
            name="onsite_contact",
            field=models.CharField(blank=True, max_length=220),
        ),
        migrations.AddField(
            model_name="callsheetversion",
            name="onsite_contact_details",
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
