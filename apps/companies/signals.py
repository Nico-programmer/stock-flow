# NOTA: este signal quedó OBSOLETO y no está conectado.
# Se decidió crear/actualizar EmployeePermission de forma explícita en las vistas
# create_user / update_user (con update_or_create), para no depender de un post_save.
# Además referencia campos que ya no existen (EmployeePermission usa `branch`, no `company`),
# así que si se reactivara tal cual, rompería.
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.accounts.models import CustomUser
from ..accounts.models import EmployeePermission


@receiver(post_save, sender=CustomUser)
def create_employee_permission(sender, instance, created, **kwargs):
    if created and instance.role != 'admin' and instance.company_id:
        EmployeePermission.objects.create(
            user=instance,
            company=instance.company
        )