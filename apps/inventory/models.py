from django.db import models
from django.core.validators import MinValueValidator

# Producto = ítem del catálogo de una empresa. El campo stock es el saldo actual el detalle de entradas/salidas irá en un modelo aparte más adelante.
class ProductModel(models.Model):
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="products", verbose_name="Empresa")
    sku = models.CharField(max_length=50, verbose_name="SKU / Código")
    name = models.CharField(max_length=150, verbose_name="Nombre")
    brand = models.CharField(max_length=100, blank=True, verbose_name="Marca")
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Precio",)
    stock = models.PositiveIntegerField(default=0, verbose_name="Cantidad")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última modificación")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["name"]
        # El SKU es único DENTRO de una empresa, no globalmente.
        constraints = [models.UniqueConstraint(fields=["company", "sku"], name="unique_sku_per_company")]