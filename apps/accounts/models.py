from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError


class UserManager(BaseUserManager):
    """
    Manager propio: AbstractBaseUser no trae ninguno. Se usa en User.objects.create_user(...)
    y en el shell/scripts para dar de alta usuarios (no hay createsuperuser: ver create_platform_admin).
    """

    # Alta de un usuario cualquiera. `password=None` permite usuarios sin login habilitado todavía.
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('El nombre de usuario es obligatorio.')

        user = self.model(username=username, **extra_fields)
        user.set_password(password)   # hashea la contraseña, nunca se guarda en texto plano

        # Corre clean() (la regla de negocio de más abajo) antes de tocar la base de datos,
        # así un alta inválida (ej: usuario sin empresa) nunca llega a guardarse.
        user.full_clean()
        user.save(using=self._db)

        return user

    # Alta del administrador de plataforma (el único que gestiona Company). Atajo sobre create_user
    # que fija is_platform_admin=True; no existe equivalente a `manage.py createsuperuser` a propósito,
    # este manager no expone is_staff/is_superuser porque no se usa el panel /admin de Django.
    def create_platform_admin(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_platform_admin', True)
        return self.create_user(username, password, **extra_fields)


class Group(models.Model):
    """
    Grupo de permisos, pero PROPIO de cada empresa (no es el Group de django.contrib.auth ni un rol
    global): cada empresa crea los grupos que necesite ("Bodega", "Cajero", etc.) y les marca a qué
    módulos da acceso. Reemplaza a role + EmployeePermission del modelo anterior.
    """

    # CASCADE: si se borra la empresa, sus grupos ya no tienen sentido y se borran con ella.
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='groups', verbose_name="Empresa")
    name = models.CharField(max_length=100, verbose_name="Nombre del grupo")

    # Un flag por módulo de la app. Se consultan desde las vistas (ej: if user.group.can_access_sales).
    can_access_inventory = models.BooleanField(default=False, verbose_name="Inventario")
    can_access_sales = models.BooleanField(default=False, verbose_name="Ventas (salida)")
    can_access_purchases = models.BooleanField(default=False, verbose_name="Compras (entrada)")
    can_access_users = models.BooleanField(default=False, verbose_name="Usuarios")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    # Texto para el admin y cualquier print/log: nombre del grupo + empresa, para no confundir
    # dos grupos con el mismo nombre en empresas distintas (ej. "Cajero" en Acme vs "Cajero" en Beta).
    def __str__(self):
        return f'{self.name} · {self.company.name}'

    class Meta:
        verbose_name = "Grupo"
        verbose_name_plural = "Grupos"
        # El nombre del grupo es único DENTRO de una empresa, no globalmente (mismo criterio que
        # Branch en companies/models.py).
        constraints = [models.UniqueConstraint(fields=['company', 'name'], name='unique_group_name_per_company')]


class User(AbstractBaseUser):
    """
    Modelo de usuario del sistema. Reemplaza a CustomUser + EmployeePermission + role.

    AbstractBaseUser da password/last_login pero, a propósito, SIN PermissionsMixin: eso deja fuera
    is_staff, is_superuser, groups y user_permissions. Sin esos campos, ninguna cuenta de esta app
    puede loguearse en /admin, aunque alguien conozca bien Django y lo intente a mano.
    """

    # REGLA DE NEGOCIO (ver clean()): un usuario pertenece a UNA empresa y (opcionalmente) UN grupo
    # de esa empresa. El admin de plataforma es la única excepción: no tiene empresa ni grupo.
    # SET_NULL: si se borra la empresa/grupo, el usuario no se borra, solo pierde el vínculo.
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='users',
        verbose_name="Empresa"
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='users',
        verbose_name="Grupo"
    )

    # Campo de login (ver USERNAME_FIELD más abajo).
    username = models.CharField(max_length=25, unique=True, verbose_name="Nombre de usuario")
    # Un solo campo de nombre (no first_name/last_name separados): así lo pidió el negocio,
    # no hace falta partirlo para nada de la app.
    full_name = models.CharField(max_length=150, verbose_name="Nombre completo")
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")

    is_active = models.BooleanField(default=True, verbose_name="Activo")   # False = baja lógica (soft delete)

    # Único acceso "total" del sistema: es quien crea/edita/desactiva las Company. Deliberadamente
    # NO es is_superuser de Django (eso habilitaría /admin); es un flag propio que las vistas
    # consultan a mano (if request.user.is_platform_admin).
    is_platform_admin = models.BooleanField(default=False, verbose_name="Administrador de plataforma")

    date_joined = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de alta")

    # Conecta el manager custom: habilita User.objects.create_user(...) / create_platform_admin(...).
    objects = UserManager()

    USERNAME_FIELD = 'username'   # Campo con el que se autentica (authenticate(username=...))
    REQUIRED_FIELDS = []          # No hay más campos obligatorios además de username y password

    # Valida la regla empresa/grupo antes de guardar. El manager (full_clean() en create_user)
    # la dispara siempre; si se edita un User ya existente a mano hay que llamarla explícitamente.
    def clean(self):
        if self.is_platform_admin and (self.company_id or self.group_id):
            raise ValidationError("Un administrador de plataforma no debe tener empresa ni grupo asignados.")
        if not self.is_platform_admin and not self.company_id:
            raise ValidationError("El usuario debe pertenecer a una empresa.")

    # Texto que representa al usuario en el /admin y en cualquier print/log.
    def __str__(self):
        return self.username

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
