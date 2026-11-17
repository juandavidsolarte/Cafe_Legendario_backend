from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('products', views.ProductViewSet)

urlpatterns = [
    *router.urls,
    path('orders/', views.OrderCreateView.as_view(), name='order-create'),
    path('orders/<str:reference>/', views.OrderStatusView.as_view(), name='order-status'),
    path('payments/wompi/events/', views.WompiEventView.as_view(), name='wompi-events'),
]
