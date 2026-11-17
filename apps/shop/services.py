"""Reglas de negocio de los pedidos."""

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers

from .models import Order, OrderItem, ProductVariant

# Estado de la transacción en Wompi -> estado del pedido.
WOMPI_STATUS = {
    'APPROVED': Order.Status.APPROVED,
    'DECLINED': Order.Status.DECLINED,
    'VOIDED': Order.Status.VOIDED,
    'ERROR': Order.Status.ERROR,
}


@transaction.atomic
def create_order(contact, items):
    """Crea el pedido con precios leídos de la base de datos, nunca del cliente."""
    skus = [item['sku'] for item in items]
    variants = {
        variant.sku: variant
        for variant in ProductVariant.objects.select_related('product').filter(
            sku__in=skus, product__is_published=True
        )
    }
    lines = []
    for item in items:
        variant = variants.get(item['sku'])
        if variant is None or not variant.is_active:
            raise serializers.ValidationError({'items': f'El producto {item["sku"]} no está disponible.'})
        if not variant.can_supply(item['quantity']):
            raise serializers.ValidationError({'items': f'No hay suficientes unidades de {variant}.'})
        lines.append((variant, item['quantity']))

    subtotal = sum(variant.price * quantity for variant, quantity in lines)
    shipping = settings.SHOP_SHIPPING_COP
    order = Order.objects.create(
        **contact,
        accepted_terms_at=timezone.now(),
        subtotal=subtotal,
        shipping=shipping,
        total=subtotal + shipping,
    )
    OrderItem.objects.bulk_create(
        OrderItem(
            order=order,
            variant=variant,
            name=variant.product.name,
            presentation=f'{variant.get_grind_display()} / {variant.weight_grams} g',
            unit_price=variant.price,
            quantity=quantity,
            line_total=variant.price * quantity,
        )
        for variant, quantity in lines
    )
    return order


@transaction.atomic
def apply_wompi_transaction(data):
    """Actualiza el pedido con el resultado que informa Wompi.

    Devuelve el pedido, o None si el aviso no corresponde a un pedido válido.
    Es idempotente: un aviso repetido no descuenta inventario dos veces.
    """
    reference = data.get('reference')
    status = WOMPI_STATUS.get(data.get('status'))
    if not reference or status is None:
        return None
    order = Order.objects.select_for_update().filter(reference=reference).first()
    if order is None:
        return None
    # El monto y la moneda deben coincidir con lo que se cobró.
    if data.get('amount_in_cents') != order.amount_in_cents or data.get('currency') != 'COP':
        return None
    if order.status == Order.Status.APPROVED:
        return order

    order.status = status
    order.wompi_transaction_id = str(data.get('id') or '')[:60]
    order.payment_method = str(data.get('payment_method_type') or '')[:40]
    if status == Order.Status.APPROVED:
        order.paid_at = timezone.now()
        for item in order.items.select_related('variant'):
            if item.variant.stock is not None:
                ProductVariant.objects.filter(pk=item.variant_id, stock__gte=item.quantity).update(
                    stock=F('stock') - item.quantity
                )
    order.save(update_fields=['status', 'wompi_transaction_id', 'payment_method', 'paid_at', 'updated_at'])
    return order
