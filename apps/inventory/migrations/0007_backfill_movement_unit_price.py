from django.db import migrations


# Los movimientos creados ANTES de agregar unit_price no tienen precio propio guardado: se
# rellenan con el precio ACTUAL del producto (costo si es Entrada, venta si es Salida) como
# mejor aproximación posible. De acá en adelante, cada movimiento nuevo congela su propio precio.
def backfill_unit_price(apps, schema_editor):
    Movement = apps.get_model('inventory', 'Movement')
    for movement in Movement.objects.select_related('product').filter(unit_price=0):
        product = movement.product
        movement.unit_price = product.cost_price if movement.movement_type == 'IN' else product.sale_price
        movement.save(update_fields=['unit_price'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0006_movement_unit_price'),
    ]

    operations = [
        migrations.RunPython(backfill_unit_price, noop),
    ]
