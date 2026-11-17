from rest_framework import serializers

from .models import Order, OrderItem, Product, ProductVariant

MAX_UNITS_PER_LINE = 20
MAX_LINES = 10


class ProductVariantSerializer(serializers.ModelSerializer):
    grind = serializers.CharField(source='get_grind_display')
    weight = serializers.SerializerMethodField()
    available = serializers.BooleanField(read_only=True)

    class Meta:
        model = ProductVariant
        fields = ['sku', 'grind', 'grind_note', 'weight', 'price', 'available', 'image_front', 'image_back']

    def get_weight(self, obj) -> str:
        return f'{obj.weight_grams} g'


class ProductSerializer(serializers.ModelSerializer):
    variants = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'slug', 'name', 'summary', 'profile', 'cup', 'origin', 'region', 'farm',
            'altitude', 'variety', 'process', 'roast', 'variants',
        ]

    def get_variants(self, obj) -> list:
        active = [variant for variant in obj.variants.all() if variant.is_active]
        return ProductVariantSerializer(active, many=True, context=self.context).data


class OrderLineInputSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=40)
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_UNITS_PER_LINE)


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            'email', 'first_name', 'last_name', 'document_type', 'document_number', 'phone',
            'address', 'address_extra', 'department', 'city',
        ]


class OrderCreateSerializer(serializers.Serializer):
    """Entrada del pedido. El navegador solo dice qué quiere y cuánto: nunca precios."""

    contact = ContactSerializer()
    items = OrderLineInputSerializer(many=True, allow_empty=False, max_length=MAX_LINES)
    accept_terms = serializers.BooleanField()

    def validate_accept_terms(self, value):
        if not value:
            raise serializers.ValidationError('Debes aceptar los términos y el tratamiento de datos.')
        return value

    def validate_items(self, items):
        skus = [item['sku'] for item in items]
        if len(skus) != len(set(skus)):
            raise serializers.ValidationError('Hay productos repetidos en el pedido.')
        return items


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['name', 'presentation', 'unit_price', 'quantity', 'line_total']


class OrderStatusSerializer(serializers.ModelSerializer):
    """Vista pública de un pedido: estado y contenido, sin datos personales."""

    items = OrderItemSerializer(many=True, read_only=True)
    status_label = serializers.CharField(source='get_status_display')

    class Meta:
        model = Order
        fields = ['reference', 'status', 'status_label', 'subtotal', 'shipping', 'total', 'items', 'created_at']
