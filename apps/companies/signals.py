from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import CustomUser
from .models import EmployeePermission


@receiver(post_save, sender=CustomUser)
def create_employee_permission(sender, instance, created, **kwargs):
    if created and instance.role != 'admin' and instance.company_id:
        EmployeePermission.objects.create(
            user=instance,
            company=instance.company
        )