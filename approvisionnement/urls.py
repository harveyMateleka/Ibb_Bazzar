from django.urls import path

from . import views

app_name = 'approvisionnement'

urlpatterns = [
    path('', views.tableau_de_bord, name='dashboard'),
    path('entrees/nouvelle/', views.entree_stock, name='entree'),
    path('sorties/nouvelle/', views.sortie_stock, name='sortie'),
    path('mouvements/', views.historique, name='historique'),
    path('inventaires/', views.inventaire_liste, name='inventaires'),
    path('inventaires/nouveau/', views.inventaire_nouveau, name='inventaire_nouveau'),
    path('inventaires/<int:pk>/', views.inventaire_detail, name='inventaire_detail'),
    path('inventaires/<int:pk>/valider/', views.inventaire_valider, name='inventaire_valider'),
]
