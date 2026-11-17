from drf_spectacular.utils import extend_schema
from rest_framework import generics, status, viewsets
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import wompi
from .models import Order, Product
from .serializers import OrderCreateSerializer, OrderStatusSerializer, ProductSerializer
from .services import apply_wompi_transaction, create_order


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """Catálogo público: solo productos publicados."""

    queryset = Product.objects.filter(is_published=True).prefetch_related('variants')
    serializer_class = ProductSerializer
    lookup_field = 'slug'
    pagination_class = None


class OrderCreateView(APIView):
    """Crea un pedido pendiente de pago y devuelve los datos para pagar en Wompi."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'orders'

    @extend_schema(request=OrderCreateSerializer, responses={201: OrderStatusSerializer})
    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = create_order(serializer.validated_data['contact'], serializer.validated_data['items'])
        body = OrderStatusSerializer(order).data
        body['payment'] = wompi.checkout_data(order)
        return Response(body, status=status.HTTP_201_CREATED)


class OrderStatusView(generics.RetrieveAPIView):
    """Estado de un pedido por su referencia. No expone datos personales."""

    queryset = Order.objects.prefetch_related('items')
    serializer_class = OrderStatusSerializer
    lookup_field = 'reference'
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'order-status'


class WompiEventView(APIView):
    """Webhook de Wompi. Solo acepta avisos con la firma correcta."""

    throttle_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        payload = request.data
        if not wompi.event_is_authentic(payload):
            return Response({'detail': 'Firma inválida.'}, status=status.HTTP_401_UNAUTHORIZED)
        if payload.get('event') == 'transaction.updated':
            transaction_data = (payload.get('data') or {}).get('transaction') or {}
            apply_wompi_transaction(transaction_data)
        # Wompi reintenta si no recibe 200, así que los avisos que no aplican también se confirman.
        return Response({'received': True})
