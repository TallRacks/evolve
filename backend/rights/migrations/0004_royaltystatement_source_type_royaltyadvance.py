import uuid
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("rights", "0003_workcontributor_share_percentage")]
    operations = [
        migrations.AddField(model_name="royaltystatement", name="source_type", field=models.CharField(default="distributor", max_length=24)),
        migrations.CreateModel(
            name="RoyaltyAdvance",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source_name", models.CharField(max_length=220)),
                ("source_type", models.CharField(default="label", max_length=24)),
                ("reference", models.CharField(blank=True, max_length=120)),
                ("currency", models.CharField(max_length=3, validators=[RegexValidator("^[A-Z]{3}$", "Use an uppercase three-letter currency code.")])),
                ("amount", models.DecimalField(decimal_places=2, max_digits=16, validators=[MinValueValidator(Decimal("0"))])),
                ("recouped_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=16, validators=[MinValueValidator(Decimal("0"))])),
                ("received_on", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, max_length=2000)),
                ("organization", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="royalty_advances", to="organizations.organization")),
                ("created_by", models.ForeignKey(null=True, on_delete=models.deletion.SET_NULL, related_name="royalty_advances_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-received_on", "-created_at")},
        ),
    ]
