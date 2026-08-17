from django.urls import path

from . import views

app_name = 'boutique'

urlpatterns = [
    path('', views.tableau_de_bord, name='dashboard'),
    path('articles/', views.articles, name='articles'),
    path('ventes/', views.ventes, name='ventes'),
    path('ventes/nouvelle/', views.vente_nouvelle, name='vente_nouvelle'),
    path('ventes/<int:pk>/', views.vente_detail, name='vente_detail'),
    path('ventes/<int:pk>/valider/', views.vente_valider, name='vente_valider'),
    path('ventes/<int:pk>/annuler/', views.vente_annuler, name='vente_annuler'),
    path('ventes/<int:pk>/imprimer/', views.vente_imprimer, name='vente_imprimer'),
]
