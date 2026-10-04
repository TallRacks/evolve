from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tasks", "0002_task_source_document"), ("organizations", "0003_role_choices")]
    operations = [
        migrations.AddField(
            model_name="task",
            name="additional_assignees",
            field=models.ManyToManyField(blank=True, related_name="shared_tasks", to="organizations.membership"),
        ),
    ]
