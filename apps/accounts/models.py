from django.db import models

# AbstractBaseUser: da solo password/last_login, sin campos de nombre ni el manager.
# PermissionsMixin: agrega is_superuser, groups y user_permissions (sistema de permisos de Django).
# Se usan estos en vez de AbstractUser para tener control total de los campos.
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone

# ValidationError se lanza desde clean() y lo capturan las vistas al llamar full_clean().
from django.core.exceptions import ValidationError

# Manager propio: al no usar AbstractUser, Django no sabe cómo crear usuarios/superusuarios.
# Este manager reemplaza esa lógica (lo usa `CustomUser.objects` y el comando createsuperuser).
class CustomUserManager(BaseUserManager):
    # Crea y guarda un usuario normal. `password=None` permite usuarios sin contraseña utilizable.
    def create_user(self, email, username, password=None, **extra_fields):
        # email y username son obligatorios: sin ellos el login y la identidad no funcionan.
        if not email:
            raise ValueError('The Email field must be set')
        if not username:
            raise ValueError('The username field must be set')

        # normalize_email pasa el dominio a minúsculas (Foo@GMAIL.com -> Foo@gmail.com).
        email = self.normalize_email(email)
        # Se instancia el modelo, se hashea la contraseña y se guarda.
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    # Crea el superusuario de la plataforma (dueño del sistema). Lo llama `manage.py createsuperuser`.
    def create_superuser(self, email, username, password, **extra_fields):
        # Valores por defecto que definen a un superusuario.
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        # El superusuario también arranca con rol 'admin' por coherencia.
        extra_fields.setdefault('role', 'admin')

        # Si alguien pasó estos flags en False explícitamente, se aborta: no sería un superusuario real.
        if extra_fields.get('is_staff') is not True:
            raise ValueError('The user must have "is_staff" set to true')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('The user must have "is_superuser" set to true')
        if extra_fields.get('is_active') is not True:
            raise ValueError('The user must have "is_active" set to true')

        # Reutiliza create_user para el alta real.
        return self.create_user(email, username, password, **extra_fields)

# Modelo de usuario del sistema. Cubre tres perfiles vía el campo `role`.
class CustomUser(AbstractBaseUser, PermissionsMixin):
    # Roles posibles. TextChoices = enum de texto: Role.ADMIN vale 'admin' y se muestra 'Administrador'.
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Administrador'        # Dueño del negocio: ve toda su empresa
        MANAGER = 'manager', 'Gerente'          # Encargado de una sucursal
        EMPLOYEE = 'employee', 'Empleado'       # Empleado de una sucursal

    # Campos de identidad y login (ambos únicos). El login es por username (ver USERNAME_FIELD).
    email = models.EmailField(unique=True, verbose_name="Correo electronico")
    username = models.CharField(unique=True, max_length=25, verbose_name="Nombre de usuario")

    # Datos personales, todos opcionales.
    first_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="Nombre")
    last_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="Apellidos")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")

    # REGLA DE NEGOCIO (ver clean()): un usuario se vincula a la organización por UN solo camino.
    #   - role == 'admin'            -> usa `company` (acceso a todas las sucursales de esa empresa), branch queda None
    #   - role in (manager, employee) -> usa `branch` (una sucursal puntual), company queda None
    # SET_NULL: si se borra la empresa/sucursal el usuario no se borra, solo pierde el vínculo.
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='admins',
        verbose_name="Empresa (solo administrador)"
    )

    # Sucursal concreta. Solo se usa para manager/employee (ver regla arriba).
    branch = models.ForeignKey(
        'companies.Branch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='employees',
        verbose_name="Sucursal (gerente/empleado)"
    )

    # Rol del usuario. Si no se indica, se asume el de menor privilegio (empleado).
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE, verbose_name="Rol de usuario")

    # Estado y metadatos de la cuenta.
    is_active = models.BooleanField(default=True, verbose_name="Estado de usuario")   # False = baja lógica (soft delete)
    is_staff = models.BooleanField(default=False, verbose_name="Equipo técnico")      # True = puede entrar al /admin de Django
    date_joined = models.DateTimeField(default=timezone.now, verbose_name="Fecha de union")
    last_login = models.DateTimeField(null=True, blank=True, verbose_name="Última sesión")

    # Conecta el manager custom: habilita CustomUser.objects.create_user(...) / create_superuser(...).
    objects = CustomUserManager()

    USERNAME_FIELD = 'username'      # Campo con el que se autentica (authenticate(username=...))
    REQUIRED_FIELDS = ['email']      # Campos extra que pide createsuperuser además de username y password

    # Nombre completo para mostrar; cae a username si no hay nombre/apellido cargados.
    def get_full_name(self):
        full_name = f'{self.first_name or ""} {self.last_name or ""}'.strip()
        return full_name or self.username

    # Nombre corto para saludos ("¡Bienvenido, Juan!"); cae a username.
    def get_short_name(self):
        return self.first_name or self.username

    # Valida la regla company/branch antes de guardar. Las vistas la disparan con full_clean().
    # Nota: no se ejecuta sola en .save(); hay que llamar full_clean() explícitamente.
    def clean(self):
        if self.role == self.Role.ADMIN and self.branch_id:
            raise ValidationError("Un administrador no debe tener una sucursal asignada, solo una empresa.")
        if self.role != self.Role.ADMIN and self.company_id:
            raise ValidationError("Solo el administrador puede estar asignado directamente a una empresa.")

    # Texto que representa al usuario en el /admin y en cualquier print/log.
    def __str__(self):
        return f'{self.email} - {self.username}'

    class Meta:
        verbose_name = "Usuario personalizado"
        verbose_name_plural = "Usuarios personalizados"

# Permisos finos por usuario. SOLO existe para manager/employee.
# Los admin NO tienen fila acá: su acceso total se resuelve por rol (if user.role == 'admin').
# No se crea por signal: las vistas create_user/update_user lo hacen con update_or_create().
class EmployeePermission(models.Model):
    # OneToOne: como máximo una fila de permisos por usuario. CASCADE: si se borra el usuario, se borran sus permisos.
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="permissions",
        verbose_name="Usuario"
    )
    # Sucursal sobre la que aplican estos permisos (redundante con user.branch, pero explícito).
    branch = models.ForeignKey(
        'companies.Branch',
        on_delete=models.CASCADE,
        related_name='employee_permissions',
        verbose_name="Sucursal"
    )

    # Interruptores de acceso por módulo. Se consultan en las vistas de inventario/ventas/etc.
    can_manage_inventory = models.BooleanField(default=False, verbose_name="Gestionar inventario")
    can_manage_sales = models.BooleanField(default=False, verbose_name="Gestionar ventas")
    can_manage_employees = models.BooleanField(default=False, verbose_name="Gestionar empleados")
    can_view_reports = models.BooleanField(default=False, verbose_name="Ver reportes")

    # Auditoría: quién otorgó estos permisos y cuándo se tocaron por última vez.
    granted_by = models.ForeignKey(
        CustomUser,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='permissions_granted',
        verbose_name="Otorgado por"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última actualización")   # auto_now: se actualiza en cada save()

    def __str__(self):
        return f'Permisos de {self.user.username} en {self.branch.name}'

    class Meta:
        verbose_name = "Permiso de empleado"
        verbose_name_plural = "Permisos de empleados"