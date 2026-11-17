"""Carga el contenido inicial: categorías, métodos, variedades, recetas y artículos.

Es el mismo contenido de ejemplo del frontend (`src/services/mockData.js`), guardado en
`apps/content/data/contenido_inicial.json`. Todo queda publicado y sin fotografía: mientras
el administrador no suba una, el frontend muestra su foto local para ese contenido.

Solo crea lo que falta (busca por slug), así que no pisa cambios hechos desde el admin.
"""

import json
from pathlib import Path

from django.db import migrations

DATA_FILE = Path(__file__).resolve().parent.parent / 'data' / 'contenido_inicial.json'

DIFFICULTY = {'Fácil': 'facil', 'Media': 'media', 'Avanzada': 'avanzada'}
TOPIC = {
    'Historia': 'historia',
    'Origen': 'origen',
    'Regiones productoras': 'regiones',
    'Producción y procesamiento': 'procesamiento',
    'Curiosidades': 'curiosidades',
    'Cultura cafetera mundial': 'cultura',
    'Café en Colombia': 'colombia',
}


def seed(apps, schema_editor):
    Category = apps.get_model('content', 'Category')
    BrewMethod = apps.get_model('content', 'BrewMethod')
    MethodTool = apps.get_model('content', 'MethodTool')
    MethodStep = apps.get_model('content', 'MethodStep')
    Variety = apps.get_model('content', 'Variety')
    Recipe = apps.get_model('content', 'Recipe')
    Ingredient = apps.get_model('content', 'Ingredient')
    RecipeStep = apps.get_model('content', 'RecipeStep')
    Article = apps.get_model('content', 'Article')

    data = json.loads(DATA_FILE.read_text(encoding='utf-8'))

    categories = {}
    for item in data['categories']:
        categories[item['slug']], _ = Category.objects.get_or_create(
            slug=item['slug'], defaults={'name': item['name']}
        )

    methods = {}
    for order, item in enumerate(data['methods']):
        method, created = BrewMethod.objects.get_or_create(
            slug=item['slug'],
            defaults={
                'name': item['name'],
                'summary': item['summary'],
                'description': item['description'],
                'ratio': item['ratio'],
                'grind': item['grind'],
                'time': item['time'],
                'tips': item.get('tips', ''),
                'order': order,
                'is_published': True,
            },
        )
        methods[item['slug']] = method
        if created:
            MethodTool.objects.bulk_create(
                MethodTool(method=method, name=name, order=i) for i, name in enumerate(item['tools'])
            )
            MethodStep.objects.bulk_create(
                MethodStep(method=method, order=i, text=text)
                for i, text in enumerate(item['steps'], start=1)
            )

    for item in data['varieties']:
        Variety.objects.get_or_create(
            slug=item['slug'],
            defaults={
                'name': item['name'],
                'description': item['description'],
                'origin': item['origin'],
                'flavor': item['flavor'],
                'aroma': item['aroma'],
                'traits': '\n'.join(item['traits']),
                'is_published': True,
            },
        )

    for item in data['recipes']:
        coffee = item.get('coffee') or {}
        recipe, created = Recipe.objects.get_or_create(
            slug=item['slug'],
            defaults={
                'name': item['name'],
                'description': item['description'],
                'category': categories[item['category']],
                'method': methods[item['method']],
                'difficulty': DIFFICULTY[item['difficulty']],
                'prep_minutes': item['time'],
                'tips': item.get('tips', ''),
                'featured': item['featured'],
                'coffee_grams': coffee.get('grams'),
                'coffee_grind': coffee.get('grind', ''),
                'is_published': True,
            },
        )
        if created:
            Ingredient.objects.bulk_create(
                Ingredient(recipe=recipe, name=ing['name'], quantity=ing['quantity'], order=i)
                for i, ing in enumerate(item['ingredients'])
            )
            RecipeStep.objects.bulk_create(
                RecipeStep(recipe=recipe, order=i, text=text)
                for i, text in enumerate(item['steps'], start=1)
            )

    for order, item in enumerate(data['articles']):
        Article.objects.get_or_create(
            slug=item['slug'],
            defaults={
                'title': item['title'],
                'topic': TOPIC[item['topic']],
                'body': item['body'],
                'order': order,
                'is_published': True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('content', '0002_recipe_coffee_amount'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
