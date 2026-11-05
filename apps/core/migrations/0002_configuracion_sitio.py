from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0001_extension_unaccent")]

    operations = [
        migrations.CreateModel(
            name="ConfiguracionSitio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=100)),
                ("eslogan", models.CharField(max_length=200)),
                ("email", models.EmailField(max_length=254)),
                ("telefono", models.CharField(max_length=30)),
                ("whatsapp", models.CharField(blank=True, max_length=20)),
                ("direccion", models.CharField(max_length=150)),
                ("titulo_inicio", models.CharField(max_length=200)),
                ("texto_inicio", models.TextField()),
            ],
            options={
                "verbose_name": "configuración del sitio",
                "verbose_name_plural": "configuración del sitio",
            },
        ),
    ]
