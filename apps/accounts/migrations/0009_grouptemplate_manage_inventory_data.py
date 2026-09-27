from django.db import migrations


# Preserva el comportamiento actual: cualquier plantilla que ya podia ver el inventario, tambien
# podia crear/editar productos (antes era un solo permiso). El admin de plataforma decide despues,
# a mano, a cuales plantillas (ej. "Bodega") les saca el permiso de administrar y las deja solo-lectura.
def set_manage_inventory(apps, schema_editor):
    GroupTemplate = apps.get_model('accounts', 'GroupTemplate')
    GroupTemplate.objects.filter(can_access_inventory=True).update(can_manage_inventory=True)


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_grouptemplate_manage_inventory'),
    ]

    operations = [
        migrations.RunPython(set_manage_inventory, reverse_noop),
    ]
