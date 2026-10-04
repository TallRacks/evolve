import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("bookings", "0001_initial")]
    operations = [
        migrations.AddField(model_name="booking", name="event_type", field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name="booking", name="performance_type", field=models.CharField(blank=True, max_length=80)),
        migrations.CreateModel(name="BookingOption", fields=[
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("category", models.CharField(choices=[("performance", "Performance type"), ("event", "Event type")], max_length=20)),
            ("name", models.CharField(max_length=80)), ("is_active", models.BooleanField(default=True)),
            ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="booking_options", to="organizations.organization")),
        ], options={"ordering": ("category", "name"), "constraints": [models.UniqueConstraint(fields=("organization", "category", "name"), name="unique_booking_option_name")]})
    ]
