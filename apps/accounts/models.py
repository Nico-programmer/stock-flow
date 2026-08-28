from django.db import models

# Imports for the Custom User
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone

# Import Exceptions
from django.core.exceptions import ValidationError

""" Custom User Management Tool """
class CustomUserManager(BaseUserManager):
    # Function to create a user
    def create_user(self, email, username, password=None, **extra_fields):
        # We verify the email address and username
        if not email:
            raise ValueError('The Email field must be set')
        if not username:
            raise ValueError('The username field must be set')

        # We normalize the email
        email = self.normalize_email(email)
        # The user is created and saved in the database
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    # Function to create the superuser
    def create_superuser(self, email, username, password, **extra_fields):
        # Permits are granted
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        # New field
        extra_fields.setdefault('role', 'admin')

        # Permit Validation
        if extra_fields.get('is_staff') is not True:
            raise ValueError('The user must have "is_staff" set to true')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('The user must have "is_superuser" set to true')
        if extra_fields.get('is_active') is not True:
            raise ValueError('The user must have "is_active" set to true')

        # The user is created
        return self.create_user(email, username, password, **extra_fields)

""" Custom User Model """
class CustomUser(AbstractBaseUser, PermissionsMixin):
    # Roles
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Administrador'
        MANAGER = 'manager', 'Gerente'
        EMPLOYEE = 'employee', 'Empleado'

    # Required fields
    email = models.EmailField(unique=True, verbose_name="Correo electronico")
    username = models.CharField(unique=True, max_length=25, verbose_name="Nombre de usuario")

    # Optional fields
    first_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="Nombre")
    last_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="Apellidos")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")

    # Company-wide: only applies if role == 'admin'
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='admins',
        verbose_name="Empresa (solo administrador)"
    )

    # Specific branch: only applies if role in ('manager', 'employee')
    branch = models.ForeignKey(
        'companies.Branch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='employees',
        verbose_name="Sucursal (gerente/empleado)"
    )

    # Role
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE, verbose_name="Rol de usuario")

    # Status fields
    is_active = models.BooleanField(default=True, verbose_name="Estado de usuario")
    is_staff = models.BooleanField(default=False, verbose_name="Equipo técnico")
    date_joined = models.DateTimeField(default=timezone.now, verbose_name="Fecha de union")
    last_login = models.DateTimeField(null=True, blank=True, verbose_name="Última sesión")

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    # Greeting Features in the Admin Panel
    def get_full_name(self):
        full_name = f'{self.first_name or ""} {self.last_name or ""}'.strip()
        return full_name or self.username

    def get_short_name(self):
        return self.first_name or self.username

    def clean(self):
        if self.role == self.Role.ADMIN and self.branch_id:
            raise ValidationError("Un administrador no debe tener una sucursal asignada, solo una empresa.")
        if self.role != self.Role.ADMIN and self.company_id:
            raise ValidationError("Solo el administrador puede estar asignado directamente a una empresa.")

    """ Function to display the field name and information in the Django admin """
    def __str__(self):
        return f'{self.email} - {self.username}'

    class Meta:
        verbose_name = "Usuario personalizado"
        verbose_name_plural = "Usuarios personalizados"

""" Employee Permissions Model """
class EmployeePermission(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="permissions",
        verbose_name="Usuario"
    )
    branch = models.ForeignKey(
        'companies.Branch',
        on_delete=models.CASCADE,
        related_name='employee_permissions',
        verbose_name="Sucursal"
    )

    can_manage_inventory = models.BooleanField(default=False, verbose_name="Gestionar inventario")
    can_manage_sales = models.BooleanField(default=False, verbose_name="Gestionar ventas")
    can_manage_employees = models.BooleanField(default=False, verbose_name="Gestionar empleados")
    can_view_reports = models.BooleanField(default=False, verbose_name="Ver reportes")

    granted_by = models.ForeignKey(
        CustomUser,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='permissions_granted',
        verbose_name="Otorgado por"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última actualización")

    def __str__(self):
        return f'Permisos de {self.user.username} en {self.company.name}'

    class Meta:
        verbose_name = "Permiso de empleado"
        verbose_name_plural = "Permisos de empleados"