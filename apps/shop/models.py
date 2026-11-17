import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Product(models.Model):
    """Un café. Sus presentaciones (molienda y peso) son las variantes."""

    name = models.CharField('nombre', max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True)
    summary = models.CharField('resumen', max_length=200)
    profile = models.CharField('perfil sensorial', max_length=240)
    cup = models.CharField('perfil de taza', max_length=40, help_text='Ejemplo: Balanceado')
    origin = models.CharField('origen', max_length=80)
    region = models.CharField('departamento de origen', max_length=40)
    farm = models.CharField('finca', max_length=80)
    altitude = models.CharField('altitud', max_length=40)
    variety = models.CharField('variedad', max_length=60)
    process = models.CharField('proceso', max_length=60)
    roast = models.CharField('tostión', max_length=40)
    is_published = models.BooleanField('publicado', default=False, db_index=True)
    created_at = models.DateTimeField('creado', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado', auto_now=True)

    class Meta:
        verbose_name = 'producto'
        verbose_name_plural = 'productos'
        ordering = ['name']

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    class Grind(models.TextChoices):
        WHOLE = 'grano', 'Grano'
        GROUND = 'molido', 'Molido'

    product = models.ForeignKey(Product, related_name='variants', on_delete=models.CASCADE)
    sku = models.CharField('SKU', max_length=40, unique=True)
    grind = models.CharField('molienda', max_length=10, choices=Grind.choices)
    grind_note = models.CharField('nota de molienda', max_length=120, blank=True)
    weight_grams = models.PositiveIntegerField('peso (g)', default=500)
    price = models.PositiveIntegerField('precio (COP)', help_text='En pesos, sin decimales.')
    stock = models.PositiveIntegerField(
        'existencias', null=True, blank=True, help_text='Vacío = sin control de inventario.'
    )
    image_front = models.ImageField('foto de frente', upload_to='products/', blank=True)
    image_back = models.ImageField('foto del reverso', upload_to='products/', blank=True)
    is_active = models.BooleanField('a la venta', default=True)

    class Meta:
        verbose_name = 'presentación'
        verbose_name_plural = 'presentaciones'
        ordering = ['product', 'grind']
        constraints = [
            models.UniqueConstraint(fields=['product', 'grind', 'weight_grams'], name='unique_presentation'),
        ]

    def __str__(self):
        return f'{self.product.name} · {self.get_grind_display()} · {self.weight_grams} g'

    @property
    def available(self):
        return self.is_active and (self.stock is None or self.stock > 0)

    def can_supply(self, quantity):
        return self.is_active and (self.stock is None or self.stock >= quantity)


def new_reference():
    """Referencia pública del pedido: imposible de adivinar, apta para Wompi."""
    return f'CL-{uuid.uuid4().hex[:20].upper()}'


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente de pago'
        APPROVED = 'approved', 'Pagado'
        DECLINED = 'declined', 'Rechazado'
        VOIDED = 'voided', 'Anulado'
        ERROR = 'error', 'Error en el pago'

    reference = models.CharField('referencia', max_length=32, unique=True, default=new_reference, editable=False)
    status = models.CharField('estado', max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)

    email = models.EmailField('correo')
    first_name = models.CharField('nombre', max_length=80)
    last_name = models.CharField('apellidos', max_length=80)
    document_type = models.CharField('tipo de documento', max_length=40)
    document_number = models.CharField('número de documento', max_length=30)
    phone = models.CharField('teléfono', max_length=20)
    address = models.CharField('dirección', max_length=160)
    address_extra = models.CharField('complemento', max_length=120, blank=True)
    department = models.CharField('departamento', max_length=60)
    city = models.CharField('ciudad o municipio', max_length=80)
    accepted_terms_at = models.DateTimeField('aceptó términos y tratamiento de datos')

    subtotal = models.PositiveIntegerField('subtotal (COP)')
    shipping = models.PositiveIntegerField('envío (COP)', default=0)
    total = models.PositiveIntegerField('total (COP)')

    wompi_transaction_id = models.CharField('transacción Wompi', max_length=60, blank=True)
    payment_method = models.CharField('medio de pago', max_length=40, blank=True)
    paid_at = models.DateTimeField('pagado', null=True, blank=True)
    created_at = models.DateTimeField('creado', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado', auto_now=True)

    class Meta:
        verbose_name = 'pedido'
        verbose_name_plural = 'pedidos'
        ordering = ['-created_at']

    def __str__(self):
        return self.reference

    @property
    def amount_in_cents(self):
        return self.total * 100


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, related_name='+', on_delete=models.PROTECT)
    # Copia de nombre y precio en el momento de la compra: el pedido no cambia si el catálogo cambia.
    name = models.CharField('producto', max_length=120)
    presentation = models.CharField('presentación', max_length=60)
    unit_price = models.PositiveIntegerField('precio unitario (COP)')
    quantity = models.PositiveSmallIntegerField('cantidad', validators=[MinValueValidator(1), MaxValueValidator(20)])
    line_total = models.PositiveIntegerField('total de la línea (COP)')

    class Meta:
        verbose_name = 'línea de pedido'
        verbose_name_plural = 'líneas de pedido'

    def __str__(self):
        return f'{self.quantity} × {self.name}'
