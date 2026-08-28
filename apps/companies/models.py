from django.db import models

""" Company Model — the business entity, unique """
class Company(models.Model):
    name = models.CharField(max_length=150, verbose_name="Nombre de la empresa")
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"

""" Branch Model — each physical branch of a company """
class Branch(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="branches", verbose_name="Empresa")
    name = models.CharField(max_length=100, blank=True, verbose_name="Nombre de la sucursal")
    address = models.CharField(max_length=250, blank=True, verbose_name="Dirreción")
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    def __str__(self):
        return f'{self.company.name} - {self.name}'

    class Meta:
        verbose_name = "Sucursal"
        verbose_name_plural = "Sucursales"
        constraints = [models.UniqueConstraint(fields=['company', 'name'], name='unique_branch_name_per_company')]