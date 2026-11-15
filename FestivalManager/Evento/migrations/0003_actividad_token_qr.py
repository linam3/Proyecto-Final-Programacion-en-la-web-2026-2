import uuid

from django.db import migrations, models


def generar_tokens(apps, schema_editor):
    Actividad = apps.get_model("Evento", "Actividad")
    for actividad in Actividad.objects.all():
        actividad.token_qr = uuid.uuid4()
        actividad.save(update_fields=["token_qr"])


class Migration(migrations.Migration):

    dependencies = [
        ("Evento", "0002_evento_color_acento_evento_color_primario"),
    ]

    operations = [
        migrations.AddField(
            model_name="actividad",
            name="token_qr",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(generar_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="actividad",
            name="token_qr",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]