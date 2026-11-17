# Café Legendario — Backend

API REST de solo lectura y panel de administración para la plataforma educativa Café Legendario.
El frontend vive en un repositorio aparte (`cafe-legendario-frontend`).

## Tecnologías

Python 3.12+, Django 6.1, Django REST Framework, drf-spectacular (Swagger), django-filter,
django-cors-headers, PostgreSQL en producción (SQLite en local), Gunicorn, WhiteNoise.

## Estructura

```
config/                 # settings, urls, wsgi/asgi
apps/content/
├── models.py           # Category, BrewMethod, MethodTool, MethodStep, Variety,
│                       # Recipe, Ingredient, RecipeStep, Article
├── serializers.py      # Serializers de listado y de detalle
├── filters.py          # Filtros de recetas (categoría, método, dificultad, destacada)
├── views.py            # ViewSets de solo lectura (solo contenido publicado)
├── urls.py             # Router de la API
├── admin.py            # Django Admin con acciones publicar / despublicar
└── tests/              # Pruebas con el framework de Django
```

## Puesta en marcha local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # y define DJANGO_SECRET_KEY
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

| URL | Contenido |
| --- | --- |
| http://localhost:8000/api/ | Raíz de la API |
| http://localhost:8000/api/docs/ | Swagger UI |
| http://localhost:8000/admin/ | Django Admin (requiere superusuario) |
| http://localhost:8000/health/ | Chequeo de salud para Render |

## Endpoints

Todos son `GET`. Cualquier otro método responde `405`.

| Endpoint | Filtros |
| --- | --- |
| `/api/categories/` | — |
| `/api/methods/`, `/api/methods/{slug}/` | — |
| `/api/varieties/`, `/api/varieties/{slug}/` | `search` |
| `/api/recipes/`, `/api/recipes/{slug}/` | `search`, `category`, `method`, `difficulty` (`facil`, `media`, `avanzada`), `featured`, `ordering`, `page` |
| `/api/articles/`, `/api/articles/{slug}/` | `topic` |

Solo se devuelve contenido con `is_published = True`. No se puede publicar un elemento sin fotografía.

## Pruebas

```bash
python manage.py test
```

## Docker

```bash
docker build -t cafe-legendario-backend .
docker run --env-file .env -p 8000:8000 cafe-legendario-backend
```

## Variables de entorno

| Variable | Descripción |
| --- | --- |
| `DJANGO_SECRET_KEY` | Obligatoria. Clave secreta de Django. |
| `DJANGO_DEBUG` | `True` solo en local. |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos, separados por coma. |
| `CORS_ALLOWED_ORIGINS` | URL del frontend (local y Vercel). |
| `DATABASE_URL` | Cadena de conexión PostgreSQL. Vacía = SQLite. |
| `CSRF_TRUSTED_ORIGINS` | Origen HTTPS del admin en producción. |

## Pendiente

- Almacenamiento persistente de imágenes en producción (disco de Render o bucket).
- GitHub Actions, despliegue en Render, Sentry, Grafana y Terraform (Fase 6).

## Tienda y pagos

La app `apps.shop` añade el catálogo, los pedidos y el pago con Wompi.

| Endpoint | Qué hace |
|---|---|
| `GET /api/products/` y `/api/products/<slug>/` | Catálogo publicado, con sus presentaciones (molienda). |
| `POST /api/orders/` | Crea un pedido pendiente. Recibe contacto, `items` (`sku`, `quantity`) y `accept_terms`. El total se calcula en el servidor. |
| `GET /api/orders/<referencia>/` | Estado del pedido. No devuelve datos personales. |
| `POST /api/payments/wompi/events/` | Webhook de Wompi. Solo acepta avisos con la firma correcta. |

La migración `0002_seed_legendario` carga Legendario Café en grano y molido (500 g, $ 38.000).

### Activar Wompi

1. En el panel de comercios de Wompi, sección Desarrolladores, copia la llave pública, el secreto de integridad y el secreto de eventos. Empieza con las de pruebas.
2. Ponlas en `.env` (o en las variables del hosting): `WOMPI_PUBLIC_KEY`, `WOMPI_INTEGRITY_SECRET`, `WOMPI_EVENTS_SECRET`.
3. Define `FRONTEND_URL` con la dirección pública del frontend.
4. En Wompi, registra como URL de eventos `https://<tu-backend>/api/payments/wompi/events/`.

Sin las llaves, los pedidos se registran pero la respuesta trae `payment: null` y el frontend muestra el pago como no disponible.

El servidor nunca recibe datos de tarjetas: el cliente paga en el formulario de Wompi. El pedido solo pasa a «Pagado» cuando llega el aviso firmado y el monto coincide.
