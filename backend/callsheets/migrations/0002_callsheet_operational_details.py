from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies = [("callsheets", "0001_initial")]
    operations = [migrations.AddField(model_name="callsheetversion", name="promoter_contact_details", field=models.CharField(blank=True, max_length=500)),
        migrations.AddField(model_name="callsheetversion", name="performance_length_minutes", field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="callsheetversion", name="transportation_mode", field=models.CharField(blank=True, choices=[("flight","Flight"),("ground","Ground")], max_length=16)),
        migrations.AddField(model_name="callsheetversion", name="meet_up_point", field=models.CharField(blank=True, max_length=220)),
        migrations.AddField(model_name="callsheetversion", name="meet_up_address", field=models.CharField(blank=True, max_length=520)),
        migrations.AddField(model_name="callsheetversion", name="meet_up_url", field=models.URLField(blank=True, max_length=1000)),
        migrations.AddField(model_name="callsheetversion", name="call_time", field=models.TimeField(blank=True, null=True)),
        migrations.AddField(model_name="callsheetversion", name="emergency_contact", field=models.CharField(blank=True, max_length=500)),
        migrations.AddField(model_name="callsheetversion", name="nearest_police_station", field=models.CharField(blank=True, max_length=500)),
        migrations.AddField(model_name="callsheetversion", name="nearest_hospital", field=models.CharField(blank=True, max_length=500)),
        migrations.AddField(model_name="callsheetversion", name="nearest_fueling_station", field=models.CharField(blank=True, max_length=500))]
