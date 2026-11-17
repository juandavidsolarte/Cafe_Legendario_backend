"""Integración con Wompi (Bancolombia).

El pago ocurre en el formulario de Wompi: los datos de la tarjeta nunca llegan a este servidor.
Aquí solo se firma la transacción y se verifica el aviso (webhook) con el resultado.

Las llaves se leen de variables de entorno. Sin ellas el pago queda desactivado.
"""

import hashlib
import hmac
from urllib.parse import urlencode

from django.conf import settings

CHECKOUT_URL = 'https://checkout.wompi.co/p/'
CURRENCY = 'COP'


def is_configured():
    return bool(settings.WOMPI_PUBLIC_KEY and settings.WOMPI_INTEGRITY_SECRET)


def integrity_signature(reference, amount_in_cents, currency=CURRENCY):
    """Firma de integridad: impide que el monto se altere en el navegador."""
    raw = f'{reference}{amount_in_cents}{currency}{settings.WOMPI_INTEGRITY_SECRET}'
    return hashlib.sha256(raw.encode()).hexdigest()


def checkout_data(order):
    """Datos para abrir el checkout de Wompi. No incluye datos personales."""
    if not is_configured():
        return None
    signature = integrity_signature(order.reference, order.amount_in_cents)
    redirect_url = f'{settings.FRONTEND_URL.rstrip("/")}/pedido/{order.reference}'
    params = {
        'public-key': settings.WOMPI_PUBLIC_KEY,
        'currency': CURRENCY,
        'amount-in-cents': order.amount_in_cents,
        'reference': order.reference,
        'signature:integrity': signature,
        'redirect-url': redirect_url,
    }
    return {
        'provider': 'wompi',
        'public_key': settings.WOMPI_PUBLIC_KEY,
        'currency': CURRENCY,
        'amount_in_cents': order.amount_in_cents,
        'reference': order.reference,
        'signature': signature,
        'redirect_url': redirect_url,
        'checkout_url': f'{CHECKOUT_URL}?{urlencode(params)}',
    }


def _dig(data, path):
    value = data
    for key in path.split('.'):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def event_is_authentic(payload):
    """Verifica que el aviso viene de Wompi.

    Wompi concatena los valores de `signature.properties`, el `timestamp` y el secreto
    de eventos, y envía el SHA-256 en `signature.checksum`.
    """
    secret = settings.WOMPI_EVENTS_SECRET
    if not secret or not isinstance(payload, dict):
        return False
    signature = payload.get('signature')
    timestamp = payload.get('timestamp')
    if not isinstance(signature, dict) or timestamp is None:
        return False
    properties = signature.get('properties')
    checksum = signature.get('checksum')
    if not isinstance(properties, list) or not isinstance(checksum, str):
        return False
    values = []
    for path in properties:
        value = _dig(payload.get('data') or {}, str(path))
        if value is None:
            return False
        values.append(str(value))
    raw = ''.join(values) + str(timestamp) + secret
    expected = hashlib.sha256(raw.encode()).hexdigest()
    return hmac.compare_digest(expected.lower(), checksum.lower())
