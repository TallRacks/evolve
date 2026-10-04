from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0003_booking_custom_fields"),
        ("signing", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="signingrequest",
            name="booking",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="signing_requests",
                to="bookings.booking",
            ),
        ),
    ]
