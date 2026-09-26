from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator


class Category(models.Model):
    """Global, igual que GroupTemplate: la administra solo el admin de plataforma y cada
    empresa la reutiliza al crear productos (no la crea cada empresa por su cuenta)."""
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"


class Product(models.Model):
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='products', verbose_name="Empresa")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products', verbose_name="Categoría")

    name = models.CharField(max_length=150, verbose_name="Nombre")
    sku = models.CharField(max_length=50, verbose_name="Código (SKU)")
    unit = models.CharField(max_length=30, default="unidad", verbose_name="Unidad")

    cost_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name="Precio de costo")
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)], verbose_name="Precio de venta")
    # 5 como piso: evita que quede en 0 (nunca alertaría bajo stock) o en un número tan chico
    # que no de tiempo a reabastecer (pedido explícito del negocio).
    min_stock = models.PositiveIntegerField(validators=[MinValueValidator(5)], verbose_name="Stock mínimo")

    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    def clean(self):
        if self.cost_price is not None and self.sale_price is not None and self.sale_price <= self.cost_price:
            raise ValidationError("El precio de venta debe ser mayor al precio de costo.")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        # El SKU es único DENTRO de una empresa, no globalmente (mismo criterio que Branch.name).
        constraints = [models.UniqueConstraint(fields=['company', 'sku'], name='unique_sku_per_company')]


class Stock(models.Model):
    """Existencia actual de un producto en una sucursal. Se actualiza al crear un Movement
    (ver inventory/views.py), no se recalcula sumando movimientos en cada lectura."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stocks', verbose_name="Producto")
    branch = models.ForeignKey('companies.Branch', on_delete=models.CASCADE, related_name='stocks', verbose_name="Sucursal")
    quantity = models.PositiveIntegerField(default=0, verbose_name="Cantidad")

    def __str__(self):
        return f'{self.product.name} · {self.branch.name}: {self.quantity}'

    class Meta:
        verbose_name = "Existencia"
        verbose_name_plural = "Existencias"
        constraints = [models.UniqueConstraint(fields=['product', 'branch'], name='unique_stock_per_product_branch')]


class Movement(models.Model):
    IN = 'IN'
    OUT = 'OUT'
    MOVEMENT_TYPES = [(IN, 'Entrada'), (OUT, 'Salida')]

    REASON_CHOICES = [
        ('compra', 'Compra'),
        ('venta', 'Venta'),
        ('ajuste', 'Ajuste'),
        ('merma', 'Merma'),
        ('devolucion', 'Devolución'),
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='movements', verbose_name="Empresa")
    branch = models.ForeignKey('companies.Branch', on_delete=models.CASCADE, related_name='movements', verbose_name="Sucursal")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='movements', verbose_name="Producto")
    # SET_NULL: si se borra el usuario, el historial de movimientos no debe perderse.
    user = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='movements', verbose_name="Usuario")

    movement_type = models.CharField(max_length=3, choices=MOVEMENT_TYPES, verbose_name="Tipo")
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, verbose_name="Motivo")
    quantity = models.PositiveIntegerField(verbose_name="Cantidad")
    note = models.CharField(max_length=250, blank=True, verbose_name="Nota")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")

    def clean(self):
        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError("La cantidad debe ser mayor a cero.")

    def __str__(self):
        return f'{self.get_movement_type_display()} · {self.product.name} ({self.quantity})'

    class Meta:
        verbose_name = "Movimiento"
        verbose_name_plural = "Movimientos"
        ordering = ['-created_at']
