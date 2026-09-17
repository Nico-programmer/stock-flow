from django.db import models

# Empresa = el negocio como razón/marca. Una empresa tiene N sucursales (Branch).
# El teléfono acá es el contacto general; las direcciones viven en cada sucursal.
class Company(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="Nombre de la empresa")   # único en todo el sistema
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")       # se setea solo al crear
    is_active = models.BooleanField(default=True, verbose_name="Activo")                         # baja lógica

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"

# Sucursal = local físico de una empresa. Acá va la dirección concreta.
class Branch(models.Model):
    # CASCADE: si se borra la empresa, se borran sus sucursales. related_name -> company.branches.all()
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="branches", verbose_name="Empresa")
    name = models.CharField(max_length=100, blank=True, verbose_name="Nombre de la sucursal")
    address = models.CharField(max_length=250, blank=True, verbose_name="Dirreción")
    is_active = models.BooleanField(default=True, verbose_name="Activo")   # baja lógica de la sucursal

    def __str__(self):
        return f'{self.company.name} - {self.name}'

    class Meta:
        verbose_name = "Sucursal"
        verbose_name_plural = "Sucursales"
        # El nombre de sucursal es único DENTRO de una empresa, no globalmente:
        # dos empresas distintas pueden tener ambas una sucursal "Centro".
        constraints = [models.UniqueConstraint(fields=['company', 'name'], name='unique_branch_name_per_company')]