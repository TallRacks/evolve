from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("rights", "0002_work_source_document")]

    operations = [
        migrations.AddField(
            model_name="workcontributor",
            name="share_percentage",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("0"),
                max_digits=7,
                validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
            ),
        ),
    ]
