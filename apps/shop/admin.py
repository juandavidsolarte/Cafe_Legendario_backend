from django.contrib import admin

from .models import Order, OrderItem, Product, ProductVariant


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'region', 'roast', 'is_published']
    list_filter = ['is_published']
    prepopulated_fields = {'slug': ['name']}
    inlines = [ProductVariantInline]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ['variant', 'name', 'presentation', 'unit_price', 'quantity', 'line_total']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Los pedidos se consultan, no se editan: el estado solo lo cambia el aviso de Wompi."""

    list_display = ['reference', 'status', 'total', 'city', 'created_at', 'paid_at']
    list_filter = ['status', 'department']
    search_fields = ['reference', 'email', 'document_number', 'wompi_transaction_id']
    date_hierarchy = 'created_at'
    inlines = [OrderItemInline]

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
