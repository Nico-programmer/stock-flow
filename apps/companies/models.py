from django.db import models

""" Companies Model """
class Company(models.Model):
    name = models.CharField(max_length=150, verbose_name="Nombre de la empresa")
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    address = models.CharField(max_length=255, blank=True, verbose_name="dirección")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"