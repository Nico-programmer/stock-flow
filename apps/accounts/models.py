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


class GroupTemplate(models.Model):
    """
    Plantilla de grupo, GLOBAL (no pertenece a ninguna empresa): el admin de plataforma la arma
    una sola vez (ej. "Bodega", "Cajero") con sus accesos. Cada Group es solo un LINK entre una
    Company y una de estas plantillas (ver clase Group más abajo): no copia los valores, los
    referencia. Si se edita una plantilla, cambia para todas las empresas que la tengan asignada.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre de la plantilla")

    can_access_inventory = models.BooleanField(default=False, verbose_name="Inventario")
    can_access_movements = models.BooleanField(default=False, verbose_name="Movimientos (entradas y salidas)")
    can_access_users = models.BooleanField(default=False, verbose_name="Usuarios")
    can_access_reports = models.BooleanField(default=False, verbose_name="Reportes")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Plantilla de grupo"
        verbose_name_plural = "Plantillas de grupo"


class Group(models.Model):
    """
    Asigna una GroupTemplate a una Company: NO tiene nombre ni accesos propios, son solo un link.
    Se crea una vez por empresa/plantilla (ver companies/views.py create_companies, que asigna
    todas las plantillas a cada Company nueva) y desde ahí se elige por Empresa->Usuario->Grupo.
    Las properties de abajo (name, can_access_*) delegan al template, para que el resto del código
    (templates HTML incluidos) siga leyendo group.name / group.can_access_inventory sin cambios.
    """

    # CASCADE: si se borra la empresa, sus asignaciones de grupo ya no tienen sentido.
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='groups', verbose_name="Empresa")
    # CASCADE: si se borra la plantilla, las asignaciones que la usaban dejan de tener sentido.
    template = models.ForeignKey(GroupTemplate, on_delete=models.CASCADE, related_name='groups', verbose_name="Plantilla")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    @property
    def name(self):
        return self.template.name

    @property
    def can_access_inventory(self):
        return self.template.can_access_inventory

    @property
    def can_access_movements(self):
        return self.template.can_access_movements

    @property
    def can_access_users(self):
        return self.template.can_access_users

    @property
    def can_access_reports(self):
        return self.template.can_access_reports

    def __str__(self):
        return f'{self.template.name} · {self.company.name}'

    class Meta:
        verbose_name = "Grupo"
        verbose_name_plural = "Grupos"
        # Una empresa no puede tener la misma plantilla asignada dos veces.
        constraints = [models.UniqueConstraint(fields=['company', 'template'], name='unique_template_per_company')]


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
    # Sucursal a la que queda restringido el usuario. Null = usuario "de empresa": ve y opera
    # sobre todas las sucursales, sin importar la que tenga asignada cada movimiento/stock.
    branch = models.ForeignKey(
        'companies.Branch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='users',
        verbose_name="Sucursal"
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
        if self.is_platform_admin and (self.company_id or self.group_id or self.branch_id):
            raise ValidationError("Un administrador de plataforma no debe tener empresa, grupo ni sucursal asignados.")
        if not self.is_platform_admin and not self.company_id:
            raise ValidationError("El usuario debe pertenecer a una empresa.")
        if self.branch_id and self.branch.company_id != self.company_id:
            raise ValidationError("La sucursal debe pertenecer a la misma empresa del usuario.")

    # Texto que representa al usuario en el /admin y en cualquier print/log.
    def __str__(self):
        return self.username

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
