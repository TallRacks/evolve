from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("documents", "0015_template_document_types")]
    operations = [migrations.AlterField(model_name="document", name="document_type", field=models.CharField(choices=[("contract","Contract"),("call_sheet","Call sheet"),("invoice","Invoice"),("performance_agreement","Performance agreement"),("rider","Rider"),("press","Press"),("artwork","Artwork"),("music","Music"),("receipt","Receipt"),("travel","Travel"),("other","Other")], max_length=24))]
