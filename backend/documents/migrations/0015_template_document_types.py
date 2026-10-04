from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies = [("documents", "0014_template_defaults_and_booking_types")]
    operations = [migrations.AlterField(model_name="documenttemplate", name="document_type", field=models.CharField(choices=[("booking_confirmation","Booking confirmation"),("contract_summary","Contract summary"),("invoice_cover","Invoice cover"),("travel_itinerary","Travel itinerary"),("production_advance","Production advance"),("booking_brief","Booking brief"),("call_sheet","Call sheet"),("invoice","Invoice"),("performance_agreement","Performance agreement"),("general","General")], max_length=32))]
