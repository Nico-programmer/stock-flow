import getpass

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

from apps.accounts.models import User


class Command(BaseCommand):
    """
    Equivalente a `createsuperuser`, pero para is_platform_admin en vez de is_staff/is_superuser.
    Uso: python manage.py createplatformadmin
    """
    help = "Crea un administrador de plataforma (el único que gestiona Company)."

    def handle(self, *args, **options):
        username = input("Nombre de usuario: ").strip()
        full_name = input("Nombre completo: ").strip()

        password = getpass.getpass("Contraseña: ")
        password_confirm = getpass.getpass("Confirmar contraseña: ")

        if password != password_confirm:
            raise CommandError("Las contraseñas no coinciden.")

        try:
            User.objects.create_platform_admin(
                username=username,
                password=password,
                full_name=full_name,
            )
        except ValidationError as e:
            raise CommandError(" ".join(e.messages))

        self.stdout.write(self.style.SUCCESS(f"Administrador de plataforma '{username}' creado."))
