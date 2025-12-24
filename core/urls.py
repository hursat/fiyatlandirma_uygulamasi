from django.urls import path
from . import views

urlpatterns = [
    path('', views.anasayfa, name='anasayfa'),
    path('karsilastirma/', views.tarife_karsilastirma, name='tarife_karsilastirma'),
]