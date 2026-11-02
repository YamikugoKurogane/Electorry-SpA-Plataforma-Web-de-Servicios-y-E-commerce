from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="rut",
            field=models.CharField(blank=True, default="", max_length=12, verbose_name="RUT"),
        ),
    ]
