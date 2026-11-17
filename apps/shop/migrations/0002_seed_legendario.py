"""Carga el primer producto real: Legendario Café, en grano y molido, 500 g."""

from django.db import migrations


def seed(apps, schema_editor):
    Product = apps.get_model('shop', 'Product')
    ProductVariant = apps.get_model('shop', 'ProductVariant')
    product, _ = Product.objects.get_or_create(
        slug='legendario-cafe',
        defaults={
            'name': 'Legendario Café',
            'summary': 'Taza balanceada, con notas dulces a frutas y cítricos suaves.',
            'profile': 'Acidez media y brillante, cuerpo sedoso y final afrutado.',
            'cup': 'Balanceado',
            'origin': 'San Pablo, Nariño',
            'region': 'Nariño',
            'farm': 'Sol y Arte',
            'altitude': '1700 m s. n. m.',
            'variety': 'Arábica Caturra',
            'process': 'Lavado, secado solar',
            'roast': 'Media',
            'is_published': True,
        },
    )
    presentations = [
        ('LEG-GRANO-500', 'grano', 'Grano entero, para moler justo antes de preparar.'),
        ('LEG-MOLIDO-500', 'molido', 'Molienda media, lista para filtro, prensa o moka.'),
    ]
    for sku, grind, note in presentations:
        ProductVariant.objects.get_or_create(
            sku=sku,
            defaults={'product': product, 'grind': grind, 'grind_note': note, 'weight_grams': 500, 'price': 38000},
        )


def unseed(apps, schema_editor):
    apps.get_model('shop', 'Product').objects.filter(slug='legendario-cafe').delete()


class Migration(migrations.Migration):
    dependencies = [('shop', '0001_initial')]
    operations = [migrations.RunPython(seed, unseed)]
