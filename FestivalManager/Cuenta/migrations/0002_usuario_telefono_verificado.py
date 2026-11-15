from django.db import migrations, models


def verificar_existentes(apps, schema_editor):
    # Las cuentas que ya existían se consideran verificadas
    apps.get_model("Cuenta", "Usuario").objects.update(verificado=True)


class Migration(migrations.Migration):

    dependencies = [
        ("Cuenta", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="telefono",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="usuario",
            name="verificado",
            field=models.BooleanField(
                default=False,
                help_text="Márcalo cuando hayas comprobado que el código y el nombre son reales. "
                          "Un participante sin verificar no puede inscribirse.",
            ),
        ),
        migrations.RunPython(verificar_existentes, migrations.RunPython.noop),
    ]