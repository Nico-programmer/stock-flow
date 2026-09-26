from django.db import migrations, models


# Ventas + Compras se combinan en un solo permiso "Movimientos" (una mipyme chica no suele
# separar quién despacha de quién recibe). Se prende si cualquiera de los dos estaba prendido.
def merge_into_movements(apps, schema_editor):
    GroupTemplate = apps.get_model('accounts', 'GroupTemplate')
    for template in GroupTemplate.objects.all():
        template.can_access_movements = template.can_access_sales or template.can_access_purchases
        template.save(update_fields=['can_access_movements'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_group_drop_own_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='grouptemplate',
            name='can_access_movements',
            field=models.BooleanField(default=False, verbose_name='Movimientos (entradas y salidas)'),
        ),
        migrations.AddField(
            model_name='grouptemplate',
            name='can_access_reports',
            field=models.BooleanField(default=False, verbose_name='Reportes'),
        ),
        migrations.RunPython(merge_into_movements, migrations.RunPython.noop),
        migrations.RemoveField(model_name='grouptemplate', name='can_access_sales'),
        migrations.RemoveField(model_name='grouptemplate', name='can_access_purchases'),
    ]
