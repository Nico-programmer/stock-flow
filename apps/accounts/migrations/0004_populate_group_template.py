from django.db import migrations


# Cada Group existente (name + 4 booleanos propios) se convierte en una GroupTemplate y el Group
# pasa a apuntar a ella. get_or_create por nombre: si dos empresas ya tenían un grupo "Bodega" con
# los mismos accesos, comparten una sola plantilla; si los accesos difieren, la segunda gana el
# nombre tal cual (raro en la práctica, pero no se pierde información: solo compite por el nombre).
def populate_template(apps, schema_editor):
    Group = apps.get_model('accounts', 'Group')
    GroupTemplate = apps.get_model('accounts', 'GroupTemplate')

    for group in Group.objects.all():
        template, _ = GroupTemplate.objects.get_or_create(
            name=group.name,
            defaults={
                'can_access_inventory': group.can_access_inventory,
                'can_access_sales': group.can_access_sales,
                'can_access_purchases': group.can_access_purchases,
                'can_access_users': group.can_access_users,
            },
        )
        group.template = template
        group.save(update_fields=['template'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_group_add_template'),
    ]

    operations = [
        migrations.RunPython(populate_template, migrations.RunPython.noop),
    ]
