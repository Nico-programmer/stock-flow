from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError

# Producto = ítem del catálogo de una empresa. El campo stock es el saldo actual el detalle de entradas/salidas irá en un modelo aparte más adelante.
class ProductModel(models.Model):
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="products", verbose_name="Empresa")
    sku = models.CharField(max_length=50, verbose_name="SKU / Código")
    name = models.CharField(max_length=150, verbose_name="Nombre")
    brand = models.CharField(max_length=100, blank=True, verbose_name="Marca")
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Precio",)
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
        constraints = [
            models.UniqueConstraint(fields=["company", "sku"], name="unique_sku_per_company")
        ]

# Cuántas unidades hay de un producto en UNA sucursal. El precio vive en ProductModel (nivel empresa).
class BranchStock(models.Model):
    product = models.ForeignKey(ProductModel, on_delete=models.CASCADE, related_name="branch_stocks", verbose_name="Producto")
    branch = models.ForeignKey("companies.Branch", on_delete=models.CASCADE, related_name="product_stocks", verbose_name="Sucursal")

    stock = models.PositiveIntegerField(default=0, verbose_name="Cantidad")

    is_active = models.BooleanField(default=True, verbose_name="Activo en esta sucursal")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última modificación")

    def clean(self):
        # El producto y la sucursal tienen que ser de la misma empresa.
        if self.product_id and self.branch_id and self.product.company_id != self.branch.company_id:
            raise ValidationError("El producto y la sucursal no pertenecen a la misma empresa.")

    def __str__(self):
        return f'{self.product.name} - {self.branch.name}'

    class Meta:
        verbose_name = "Stock por sucursal"
        verbose_name_plural = "Stocks por sucursal"
        constraints = [
            # Una sola fila de stock por (producto, sucursal).
            models.UniqueConstraint(fields=["product", "branch"], name="unique_product_per_branch"),
        ]