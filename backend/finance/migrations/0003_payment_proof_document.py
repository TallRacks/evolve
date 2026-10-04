from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("finance", "0002_employeeinvoicesubmission_financeprofile_quote_and_more")]
    operations = [
        migrations.AddField(
            model_name="payment",
            name="proof_document",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payment_proofs",
                to="documents.document",
            ),
        ),
    ]
