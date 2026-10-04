from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("bookings", "0002_booking_event_type_booking_performance_type_and_more")]
    operations = [
        migrations.AddField(
            model_name="booking",
            name="custom_fields",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
