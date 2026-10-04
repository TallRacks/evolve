from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("documents", "0013_presentation_format")]
    operations = [
        migrations.AddField(
            model_name="documenttemplate",
            name="is_default",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="documenttemplate",
            name="document_type",
            field=models.CharField(
                choices=[
                    ("booking_confirmation", "Booking confirmation"),
                    ("contract_summary", "Contract summary"),
                    ("invoice_cover", "Invoice cover"),
                    ("travel_itinerary", "Travel itinerary"),
                    ("production_advance", "Production advance"),
                    ("booking_brief", "Booking brief"),
                    ("call_sheet", "Call sheet"),
                    ("general", "General"),
                ],
                max_length=32,
            ),
        ),
    ]
