import uuid

from django.db import migrations

POLICY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def seed_policy(apps, schema_editor):
    StoragePolicy = apps.get_model("integrations", "StoragePolicy")
    StoragePolicy.objects.get_or_create(id=POLICY_ID)


def unseed_policy(apps, schema_editor):
    StoragePolicy = apps.get_model("integrations", "StoragePolicy")
    StoragePolicy.objects.filter(id=POLICY_ID).delete()


class Migration(migrations.Migration):
    dependencies = [("integrations", "0003_storagepolicy")]

    operations = [migrations.RunPython(seed_policy, unseed_policy)]
