import hashlib

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.shop import wompi
from apps.shop.models import Order, ProductVariant

CONTACT = {
    'email': 'prueba@example.com',
    'first_name': 'Prueba',
    'last_name': 'Local',
    'document_type': 'Cédula de ciudadanía',
    'document_number': '1000000000',
    'phone': '3000000000',
    'address': 'Calle 1 # 2-3',
    'department': 'Nariño',
    'city': 'San Pablo',
}

WOMPI = {
    'WOMPI_PUBLIC_KEY': 'pub_test_ejemplo',
    'WOMPI_INTEGRITY_SECRET': 'test_integrity_ejemplo',
    'WOMPI_EVENTS_SECRET': 'test_events_ejemplo',
    'FRONTEND_URL': 'http://localhost:5173',
}


def order_body(items=None, **extra):
    return {
        'contact': CONTACT,
        'items': [{'sku': 'LEG-MOLIDO-500', 'quantity': 2}] if items is None else items,
        'accept_terms': True,
        **extra,
    }


def wompi_event(order, status='APPROVED', amount=None, secret=WOMPI['WOMPI_EVENTS_SECRET']):
    transaction = {
        'id': 'tx-123',
        'status': status,
        'amount_in_cents': order.amount_in_cents if amount is None else amount,
        'reference': order.reference,
        'currency': 'COP',
        'payment_method_type': 'CARD',
    }
    timestamp = 1700000000
    raw = f"{transaction['id']}{transaction['status']}{transaction['amount_in_cents']}{timestamp}{secret}"
    return {
        'event': 'transaction.updated',
        'data': {'transaction': transaction},
        'signature': {
            'properties': ['transaction.id', 'transaction.status', 'transaction.amount_in_cents'],
            'checksum': hashlib.sha256(raw.encode()).hexdigest(),
        },
        'timestamp': timestamp,
    }


class ShopTestCase(TestCase):
    def setUp(self):
        cache.clear()  # reinicia los límites de peticiones entre pruebas
        self.client = APIClient()

    def create_order(self, **kwargs):
        response = self.client.post('/api/orders/', order_body(**kwargs), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return Order.objects.get(reference=response.data['reference']), response


class CatalogTests(ShopTestCase):
    def test_lists_the_seeded_product_with_both_grinds(self):
        response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        product = response.data[0]
        self.assertEqual(product['slug'], 'legendario-cafe')
        self.assertEqual({v['sku'] for v in product['variants']}, {'LEG-GRANO-500', 'LEG-MOLIDO-500'})
        self.assertTrue(all(v['price'] == 38000 and v['weight'] == '500 g' for v in product['variants']))

    def test_inactive_variant_is_hidden(self):
        ProductVariant.objects.filter(sku='LEG-GRANO-500').update(is_active=False)
        product = self.client.get('/api/products/legendario-cafe/').data
        self.assertEqual([v['sku'] for v in product['variants']], ['LEG-MOLIDO-500'])


class OrderTests(ShopTestCase):
    def test_total_is_computed_on_the_server(self):
        # Un precio enviado por el cliente se ignora.
        order, response = self.create_order(
            items=[{'sku': 'LEG-MOLIDO-500', 'quantity': 2, 'price': 1}, {'sku': 'LEG-GRANO-500', 'quantity': 1}]
        )
        self.assertEqual(order.total, 38000 * 3)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(response.data['total'], 114000)

    def test_response_has_no_personal_data(self):
        _, response = self.create_order()
        self.assertNotIn('email', response.data)
        self.assertNotIn('document_number', str(response.data))

    def test_payment_is_off_without_wompi_keys(self):
        _, response = self.create_order()
        self.assertIsNone(response.data['payment'])

    @override_settings(**WOMPI)
    def test_payment_data_is_signed(self):
        order, response = self.create_order()
        payment = response.data['payment']
        expected = hashlib.sha256(
            f'{order.reference}{order.amount_in_cents}COPtest_integrity_ejemplo'.encode()
        ).hexdigest()
        self.assertEqual(payment['signature'], expected)
        self.assertEqual(payment['amount_in_cents'], 7600000)
        self.assertIn('checkout.wompi.co', payment['checkout_url'])
        self.assertIn(f'/pedido/{order.reference}', payment['redirect_url'])
        # Ni secretos ni datos personales viajan al navegador.
        self.assertNotIn('test_integrity_ejemplo', str(response.data))
        self.assertNotIn('example.com', payment['checkout_url'])

    def test_rejects_invalid_orders(self):
        cases = [
            order_body(accept_terms=False),
            order_body(items=[]),
            order_body(items=[{'sku': 'NO-EXISTE', 'quantity': 1}]),
            order_body(items=[{'sku': 'LEG-MOLIDO-500', 'quantity': 0}]),
            order_body(items=[{'sku': 'LEG-MOLIDO-500', 'quantity': 21}]),
            order_body(items=[{'sku': 'LEG-MOLIDO-500', 'quantity': 1}] * 2),
            {**order_body(), 'contact': {**CONTACT, 'email': 'no-es-correo'}},
        ]
        for body in cases:
            response = self.client.post('/api/orders/', body, format='json')
            self.assertEqual(response.status_code, 400, body)
        self.assertEqual(Order.objects.count(), 0)

    def test_rejects_order_above_stock(self):
        ProductVariant.objects.filter(sku='LEG-MOLIDO-500').update(stock=1)
        response = self.client.post('/api/orders/', order_body(), format='json')
        self.assertEqual(response.status_code, 400)

    def test_public_status_by_reference(self):
        order, _ = self.create_order()
        response = self.client.get(f'/api/orders/{order.reference}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'pending')
        self.assertNotIn('email', response.data)
        self.assertEqual(self.client.get('/api/orders/CL-NOEXISTE/').status_code, 404)


@override_settings(**WOMPI)
class WompiEventTests(ShopTestCase):
    url = '/api/payments/wompi/events/'

    def test_approved_event_marks_order_paid_and_discounts_stock(self):
        ProductVariant.objects.filter(sku='LEG-MOLIDO-500').update(stock=5)
        order, _ = self.create_order()
        response = self.client.post(self.url, wompi_event(order), format='json')
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.APPROVED)
        self.assertEqual(order.payment_method, 'CARD')
        self.assertIsNotNone(order.paid_at)
        self.assertEqual(ProductVariant.objects.get(sku='LEG-MOLIDO-500').stock, 3)

    def test_repeated_event_does_not_discount_twice(self):
        ProductVariant.objects.filter(sku='LEG-MOLIDO-500').update(stock=5)
        order, _ = self.create_order()
        for _ in range(2):
            self.client.post(self.url, wompi_event(order), format='json')
        self.assertEqual(ProductVariant.objects.get(sku='LEG-MOLIDO-500').stock, 3)

    def test_event_with_wrong_signature_is_rejected(self):
        order, _ = self.create_order()
        response = self.client.post(self.url, wompi_event(order, secret='otro-secreto'), format='json')
        self.assertEqual(response.status_code, 401)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_event_with_wrong_amount_does_not_pay_the_order(self):
        order, _ = self.create_order()
        response = self.client.post(self.url, wompi_event(order, amount=100), format='json')
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_declined_event(self):
        order, _ = self.create_order()
        self.client.post(self.url, wompi_event(order, status='DECLINED'), format='json')
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DECLINED)

    def test_approved_order_is_not_downgraded(self):
        order, _ = self.create_order()
        self.client.post(self.url, wompi_event(order), format='json')
        self.client.post(self.url, wompi_event(order, status='DECLINED'), format='json')
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.APPROVED)

    @override_settings(WOMPI_EVENTS_SECRET='')
    def test_events_are_rejected_without_secret(self):
        order, _ = self.create_order()
        self.assertEqual(self.client.post(self.url, wompi_event(order), format='json').status_code, 401)
        self.assertFalse(wompi.event_is_authentic({'signature': {}}))
